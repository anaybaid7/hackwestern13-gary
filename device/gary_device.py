#!/usr/bin/env python3
"""
Gary the Goat - device loop for Linux, Raspberry Pi OS and macOS.

    camera frame -> on-device object detector -> quest match -> sound + log

Quick start
    python3 gary_device.py                        # webcam 0
    python3 gary_device.py --image test/pets.jpg  # no camera needed
    python3 gary_device.py --show                 # draw boxes in a window

While it runs
    Enter       "Ask Gary": he says what he sees right now
    q + Enter   quit
    From another program (Linux, macOS):  kill -USR1 $(cat gary.pid)  = Ask Gary

Files it reads
    models/ssd_mobilenet_v2_coco_quant_postprocess.tflite   the detector
    models/coco_labels.txt                                 class id -> name
    quests.tsv                                             id, label, points, text
    sounds/*.wav                                           created on first run

Files it writes
    finds.jsonl    one line per completed quest (append-only, survives power loss)
    latency.csv    per-frame timings, written on exit

Nothing here uploads images. Only labels are logged.
"""
import argparse
import collections
import datetime
import json
import math
import os
import shutil
import signal
import struct
import subprocess
import sys
import threading
import time
import wave

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    sys.exit("OpenCV is missing. Run: pip install opencv-python")


HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------
def _interpreter_class():
    """Return a TFLite Interpreter class from whichever package is installed."""
    try:
        from ai_edge_litert.interpreter import Interpreter
        return Interpreter
    except ImportError:
        pass
    try:
        from tflite_runtime.interpreter import Interpreter
        return Interpreter
    except ImportError:
        pass
    try:
        import tensorflow as tf
        return tf.lite.Interpreter
    except ImportError:
        sys.exit("No TFLite runtime found. Run: pip install ai-edge-litert")


class Detector:
    """SSD-style TFLite detector with the standard 4 outputs:
    boxes [1,N,4], classes [1,N], scores [1,N], count [1]."""

    def __init__(self, model_path, labels_path, threads=3):
        Interpreter = _interpreter_class()
        self.interp = Interpreter(model_path=model_path, num_threads=threads)
        self.interp.allocate_tensors()
        inp = self.interp.get_input_details()[0]
        self.in_index = inp["index"]
        _, self.in_h, self.in_w, _ = [int(v) for v in inp["shape"]]
        self.in_float = inp["dtype"] == np.float32
        outs = self.interp.get_output_details()
        if len(outs) < 4:
            sys.exit("Model does not have the 4 detection outputs this code expects.")
        self.out_boxes, self.out_classes, self.out_scores, self.out_count = [
            o["index"] for o in outs[:4]
        ]
        with open(labels_path, "r", encoding="utf-8") as f:
            self.labels = [line.strip() for line in f]

    def detect(self, frame_bgr, min_score=0.3):
        """Return [(label, score, (x0, y0, x1, y1))] with box values in 0..1."""
        img = cv2.resize(frame_bgr, (self.in_w, self.in_h))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if self.in_float:
            tensor = (img.astype(np.float32) - 127.5) / 127.5
        else:
            tensor = img
        self.interp.set_tensor(self.in_index, tensor[np.newaxis, ...])
        self.interp.invoke()
        boxes = self.interp.get_tensor(self.out_boxes)[0]
        classes = self.interp.get_tensor(self.out_classes)[0]
        scores = self.interp.get_tensor(self.out_scores)[0]
        count = int(self.interp.get_tensor(self.out_count)[0])
        found = []
        for i in range(min(count, len(scores))):
            score = float(scores[i])
            if score < min_score:
                continue
            cid = int(classes[i])
            label = self.labels[cid] if 0 <= cid < len(self.labels) else "id%d" % cid
            if label in ("n/a", ""):
                continue
            y0, x0, y1, x1 = [float(v) for v in boxes[i]]
            found.append((label, score, (x0, y0, x1, y1)))
        return found


# --------------------------------------------------------------------------
# Quests and the find log
# --------------------------------------------------------------------------
Quest = collections.namedtuple("Quest", "id label points text")


def load_quests(path):
    """quests.tsv: id <TAB> label <TAB> points <TAB> text. '#' starts a comment."""
    quests = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                print("skipping bad quest line:", line)
                continue
            text = parts[3] if len(parts) > 3 else "Find a " + parts[1]
            quests.append(Quest(parts[0].strip(), parts[1].strip().lower(), int(parts[2]), text.strip()))
    return quests


class FindLog:
    """Append-only journal. State is rebuilt from it on every start, so pulling
    the power never loses a completed quest."""

    def __init__(self, path):
        self.path = path
        self.done = set()
        self.points = 0
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue  # a half-written last line after a power cut
                    self.done.add(rec.get("quest_id"))
                    self.points += int(rec.get("points", 0))

    def add(self, quest, label, score, friend, points):
        rec = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "quest_id": quest.id,
            "label": label,
            "score": round(score, 3),
            "friend": bool(friend),
            "points": int(points),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self.done.add(quest.id)
        self.points += int(points)
        return rec


class Stability:
    """A label only counts once it shows up in `need` of the last `window`
    frames. This removes one-frame flickers."""

    def __init__(self, window=5, need=3):
        self.window, self.need = window, need
        self.history = collections.deque(maxlen=window)

    def update(self, best_by_label):
        self.history.append(best_by_label)
        counts, best = {}, {}
        for frame in self.history:
            for label, score in frame.items():
                counts[label] = counts.get(label, 0) + 1
                best[label] = max(best.get(label, 0.0), score)
        return {label: best[label] for label, n in counts.items() if n >= self.need}


# --------------------------------------------------------------------------
# Sound
# --------------------------------------------------------------------------
def _tone(freqs, seconds_each=0.14, rate=22050, volume=0.5):
    samples = []
    for freq in freqs:
        n = int(rate * seconds_each)
        for i in range(n):
            env = min(1.0, i / (0.01 * rate)) * min(1.0, (n - i) / (0.04 * rate))
            samples.append(volume * env * math.sin(2 * math.pi * freq * i / rate))
    return rate, samples


def ensure_sounds(folder):
    """Create placeholder chimes so there is feedback before anyone records
    Gary's voice. Drop your own WAV files in with the same names to replace
    them, or add <label>.wav (for example bottle.wav) for spoken labels."""
    os.makedirs(folder, exist_ok=True)
    chimes = {
        "hello": [523, 659],
        "found": [659, 880, 1047],
        "friend": [880, 1047, 1319, 1568],
        "ask": [587],
        "nothing": [392, 330],
        "done": [523, 659, 784, 1047, 1319],
    }
    for name, freqs in chimes.items():
        path = os.path.join(folder, name + ".wav")
        if os.path.exists(path):
            continue
        rate, samples = _tone(freqs)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples))


class Speaker:
    def __init__(self, folder, command=None, mute=False):
        self.folder, self.mute = folder, mute
        self.cmd = None
        self.winsound = None
        self.lock = threading.Lock()
        if mute:
            return
        if command:
            self.cmd = command.split()
        elif os.name == "nt":
            try:
                import winsound
                self.winsound = winsound
            except ImportError:
                pass
        else:
            for candidate in (["mmrplay"], ["aplay", "-q"], ["afplay"], ["paplay"]):
                if shutil.which(candidate[0]):
                    self.cmd = candidate
                    break
        if not self.cmd and not self.winsound:
            print("No audio player found; feedback will be printed only.")

    def has(self, name):
        return os.path.exists(os.path.join(self.folder, name + ".wav"))

    def play(self, *names):
        """Play clips one after another without blocking the camera loop."""
        paths = [os.path.join(self.folder, n + ".wav") for n in names if self.has(n)]
        if self.mute or not paths:
            return
        threading.Thread(target=self._play_all, args=(paths,), daemon=True).start()

    def _play_all(self, paths):
        with self.lock:
            for path in paths:
                try:
                    if self.winsound:
                        self.winsound.PlaySound(path, self.winsound.SND_FILENAME)
                    elif self.cmd:
                        subprocess.run(self.cmd + [path], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=15)
                except Exception as exc:  # audio must never stop the loop
                    print("audio error:", exc)


# --------------------------------------------------------------------------
# Camera
# --------------------------------------------------------------------------
class Camera:
    """Reads frames on its own thread and keeps only the newest one, so the
    detector never works on a stale picture."""

    def __init__(self, index, width, height):
        source = int(index) if str(index).isdigit() else index
        self.is_file = not isinstance(source, int)
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            sys.exit("Could not open camera %s. Is the webcam plugged in?" % index)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.lock = threading.Lock()
        self.frame, self.stamp, self.seq = None, 0.0, 0
        self.running = True
        self.ended = False
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        misses = 0
        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                misses += 1
                if self.is_file and misses > 20:
                    self.ended = True  # a video file reached its end
                    return
                time.sleep(0.01)
                continue
            misses = 0
            with self.lock:
                self.frame, self.stamp, self.seq = frame, time.monotonic(), self.seq + 1
            if self.is_file:
                time.sleep(1 / 30.0)  # play files at camera speed

    def latest(self, after_seq, timeout=0.5):
        """Wait up to `timeout` seconds for a frame newer than `after_seq`.
        Returns (None, 0.0, after_seq) if none arrived, so the caller can still
        answer the Ask button and the quit key when the camera stalls."""
        deadline = time.monotonic() + timeout
        while self.running and time.monotonic() < deadline:
            with self.lock:
                if self.seq > after_seq and self.frame is not None:
                    return self.frame, self.stamp, self.seq
            time.sleep(0.002)
        return None, 0.0, after_seq

    def close(self):
        self.running = False
        time.sleep(0.05)
        self.cap.release()


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------
def draw(frame, detections):
    h, w = frame.shape[:2]
    for label, score, (x0, y0, x1, y1) in detections:
        p0, p1 = (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h))
        cv2.rectangle(frame, p0, p1, (60, 200, 60), 2)
        cv2.putText(frame, "%s %.0f%%" % (label, score * 100), (p0[0], max(15, p0[1] - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (60, 200, 60), 2)
    return frame


def percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct / 100.0 * (len(ordered) - 1))))]


def main():
    ap = argparse.ArgumentParser(description="Gary the Goat device loop")
    ap.add_argument("--camera", default="0", help="webcam index (default 0), or a video file or stream URL")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--image", help="run on one image file instead of the camera")
    ap.add_argument("--save-debug", help="with --image: save an annotated copy here")
    ap.add_argument("--model", default=os.path.join(HERE, "models", "ssd_mobilenet_v2_coco_quant_postprocess.tflite"))
    ap.add_argument("--labels", default=os.path.join(HERE, "models", "coco_labels.txt"))
    ap.add_argument("--quests", default=os.path.join(HERE, "quests.tsv"))
    ap.add_argument("--log", default=os.path.join(HERE, "finds.jsonl"))
    ap.add_argument("--sounds", default=os.path.join(HERE, "sounds"))
    ap.add_argument("--audio-cmd", help='player command, for example "aplay -q -D plughw:2,0"')
    ap.add_argument("--mute", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.5, help="minimum confidence (default 0.5)")
    ap.add_argument("--window", type=int, default=5, help="frames remembered (default 5)")
    ap.add_argument("--need", type=int, default=3, help="frames needed to confirm (default 3)")
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--friend-label", default="person")
    ap.add_argument("--button-gpio", type=int, help="Raspberry Pi OS only: GPIO pin of the Ask button")
    ap.add_argument("--show", action="store_true", help="show a window with boxes")
    ap.add_argument("--reset", action="store_true", help="forget completed quests and start over")
    args = ap.parse_args()

    detector = Detector(args.model, args.labels, args.threads)
    quests = load_quests(args.quests)
    if args.reset and os.path.exists(args.log):
        os.rename(args.log, args.log + "." + time.strftime("%Y%m%d-%H%M%S") + ".bak")
    log = FindLog(args.log)
    ensure_sounds(args.sounds)
    speaker = Speaker(args.sounds, args.audio_cmd, args.mute)
    stable = Stability(args.window, args.need)

    known = set(detector.labels)
    for q in quests:
        if q.label not in known:
            print("WARNING: quest %s wants '%s', which this model cannot see." % (q.id, q.label))

    print("Gary is awake. Model input %dx%d. %d quests, %d already done, %d points."
          % (detector.in_w, detector.in_h, len(quests), sum(q.id in log.done for q in quests), log.points))
    for q in quests:
        print("  [%s] %s  (%s, %d pts)" % ("x" if q.id in log.done else " ", q.text, q.label, q.points))
    speaker.play("hello")

    ask = threading.Event()
    stop = threading.Event()

    def keys():
        for line in sys.stdin:
            if line.strip().lower() == "q":
                stop.set()
                return
            ask.set()

    pid_path = os.path.join(HERE, "gary.pid")
    if not args.image:
        threading.Thread(target=keys, daemon=True).start()
        if hasattr(signal, "SIGUSR1"):  # kill -USR1 <pid> = Ask Gary (a hardware button can use this)
            signal.signal(signal.SIGUSR1, lambda *_: ask.set())
            with open(pid_path, "w", encoding="utf-8") as f:
                f.write("%d\n" % os.getpid())
        if args.button_gpio is not None:
            try:
                from gpiozero import Button
                button = Button(args.button_gpio)
                button.when_pressed = ask.set
                print("Ask button on GPIO", args.button_gpio)
            except Exception as exc:
                print("Button not available:", exc)

    camera = None
    if args.image:
        still = cv2.imread(args.image)
        if still is None:
            sys.exit("Could not read image " + args.image)
    else:
        camera = Camera(args.camera, args.width, args.height)

    # Per-frame (frame_to_decision_ms, model_ms). "Frame" is the frame reaching this
    # program; time inside the camera and the USB link is not included.
    # Only the most recent KEEP_TIMINGS are kept, so a long run does not grow.
    KEEP_TIMINGS = 200000
    timings, dropped = [], 0
    last_report = time.monotonic()
    frames_since = 0
    seq = 0
    frame_budget = args.window if args.image else None
    confirmed, detections, frame = {}, [], None

    def answer_ask():
        if not ask.is_set():
            return
        ask.clear()
        seen = sorted(confirmed.items(), key=lambda kv: -kv[1])[:3]
        if seen:
            print("\nGary sees: " + ", ".join("%s (%.0f%%)" % (l, s * 100) for l, s in seen))
            speaker.play("ask", *[l.replace(" ", "_") for l, _ in seen])
        else:
            print("\nGary sees nothing he can name.")
            speaker.play("nothing")

    try:
        while not stop.is_set():
            if args.image:
                if frame_budget == 0:
                    break
                frame_budget -= 1
                frame, stamp = still.copy(), time.monotonic()
            else:
                frame, stamp, seq = camera.latest(seq)
                if frame is None:
                    if camera.ended:
                        break
                    answer_ask()  # keep the button alive while the camera stalls
                    continue

            t0 = time.monotonic()
            detections = detector.detect(frame, min_score=min(0.3, args.threshold))
            infer_ms = (time.monotonic() - t0) * 1000.0

            best = {}
            for label, score, _ in detections:
                if score >= args.threshold:
                    best[label] = max(best.get(label, 0.0), score)
            confirmed = stable.update(best)

            friend_here = args.friend_label in confirmed
            for q in quests:
                if q.id in log.done or q.label not in confirmed:
                    continue
                friend = friend_here and q.label != args.friend_label
                points = q.points * (2 if friend else 1)
                log.add(q, q.label, confirmed[q.label], friend, points)
                print("\nFOUND: %s  (+%d points%s)  total %d"
                      % (q.text, points, ", friend bonus" if friend else "", log.points))
                clips = ["friend" if friend else "found"]
                if speaker.has(q.label.replace(" ", "_")):
                    clips.append(q.label.replace(" ", "_"))
                if all(x.id in log.done for x in quests):
                    clips.append("done")
                    print("All of today's quests are done. Gary is very pleased.")
                speaker.play(*clips)

            timings.append(((time.monotonic() - stamp) * 1000.0, infer_ms))
            frames_since += 1

            answer_ask()

            if args.show:
                try:
                    cv2.imshow("Gary", draw(frame.copy(), detections))
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                except cv2.error:
                    print("No display available; continuing without --show.")
                    args.show = False

            now = time.monotonic()
            if now - last_report >= 5.0 and not args.image:
                recent = timings[-frames_since:]
                lat = [t[0] for t in recent]
                inf = [t[1] for t in recent]
                print("%.1f fps | model %.0f ms | frame-to-decision p50 %.0f ms, p95 %.0f ms, max %.0f ms | sees: %s"
                      % (frames_since / (now - last_report), sum(inf) / len(inf),
                         percentile(lat, 50), percentile(lat, 95), max(lat),
                         ", ".join(sorted(confirmed)) or "-"))
                last_report, frames_since = now, 0
                if len(timings) > KEEP_TIMINGS:
                    cut = len(timings) - KEEP_TIMINGS // 2
                    del timings[:cut]
                    dropped += cut
    except KeyboardInterrupt:
        pass
    finally:
        if camera:
            camera.close()
        if not args.image and os.path.exists(pid_path):
            os.remove(pid_path)

    if args.image:
        print("\nDetections in %s:" % args.image)
        for label, score, box in sorted(detections, key=lambda d: -d[1]):
            print("  %-14s %.0f%%  box %s" % (label, score * 100, tuple(round(v, 2) for v in box)))
        print("Confirmed after %d frames: %s" % (args.window, ", ".join(sorted(confirmed)) or "-"))
        if args.save_debug and frame is not None:
            cv2.imwrite(args.save_debug, draw(frame.copy(), detections))
            print("Annotated image saved to", args.save_debug)

    if timings:
        inf = [t[1] for t in timings]
        lat = [t[0] for t in timings]
        print("\n%d frames. Model: mean %.0f ms. Frame-to-decision: p50 %.0f ms, p95 %.0f ms, max %.0f ms."
              % (dropped + len(timings), sum(inf) / len(inf), percentile(lat, 50), percentile(lat, 95), max(lat)))
        with open(os.path.join(HERE, "latency.csv"), "w", encoding="utf-8") as f:
            f.write("frame,frame_to_decision_ms,model_ms\n")
            for i, (a, b) in enumerate(timings):
                f.write("%d,%.2f,%.2f\n" % (dropped + i, a, b))
    print("Points: %d. Quests done: %d of %d." % (log.points, sum(q.id in log.done for q in quests), len(quests)))
    time.sleep(0.3)  # let the last sound start


if __name__ == "__main__":
    main()
