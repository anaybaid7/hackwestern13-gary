#!/usr/bin/env python3
"""
Gary the Goat - device loop for Linux, Raspberry Pi OS and macOS.
(The QNX version is qnx/gary_qnx.cpp. Both read and write the same files.)

    camera -> on-device object detector -> SNIFF TEST -> journal + sound

The camera and the model run all the time, so Gary always knows what is in
view. Nothing is recorded until someone presses the button. That press is the
Sniff Test: Gary names what he sees, writes it in his journal, and reacts.
A friend in the frame marks the find as Herd Mode.

Quick start
    python3 gary_device.py                        # webcam 0, Enter = sniff
    python3 gary_device.py --image test/pets.jpg  # no camera needed
    python3 gary_device.py --show                 # draw boxes in a window

While it runs
    Enter       Sniff Test
    q + Enter   quit
    From another program (Linux, macOS):
        kill -USR1 $(cat gary.pid)   Sniff Test (this is how a hardware button is wired in)
        kill -HUP  $(cat gary.pid)   reload quests.tsv (sync.py does this)

Files it reads
    models/gary_detector.tflite     the detector: YOLOv8s on Open Images (models/make_model.py)
    models/gary_labels.txt       class id -> name
    models/ssd_mobilenet_v2_coco_quant_postprocess.tflite + coco_labels.txt   the old one, still works
    quests.tsv                                             id, target, xp, text, [herd]
                                                           (written by sync.py; until it exists,
                                                           the seed quests in quests.seed.tsv)
    sounds/*.wav                                           created on first run

Files it writes
    journal.jsonl  one line per sniff (append-only, survives power loss).
                   This is the device's whole output. sync.py uploads it.
                   Each line is an Event from contract/README.md.
    latency.csv    per-frame timings, written on exit (gary_numbers.py reads it)

The device records facts only. XP, stages and the map belong to the backend.
No image is ever stored or uploaded. Only labels are written down.
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


def decode_yolo(out, labels, min_score, iou=0.5):
    """YOLO output [4+K, A] (or [A, 4+K]): cx, cy, w, h in 0..1, then one score
    per class. Returns [(label, score, (x0, y0, x1, y1))], overlaps merged."""
    if out.shape[0] != len(labels) + 4:
        out = out.T
    scores = out[4:]
    cls = scores.argmax(0)
    best = scores[cls, np.arange(scores.shape[1])]
    keep = np.flatnonzero(best >= min_score)
    if keep.size == 0:
        return []
    cx, cy, w, h = out[:4, keep]
    boxes = np.stack([cx - w / 2, cy - h / 2, w, h], 1)
    found = []
    for c in np.unique(cls[keep]):  # merge overlaps within one kind of thing only
        mine = np.flatnonzero(cls[keep] == c)
        for j in np.array(cv2.dnn.NMSBoxes(boxes[mine].tolist(), best[keep][mine].tolist(), min_score, iou)).flatten():
            x, y, bw, bh = boxes[mine[j]]
            found.append((labels[c], float(best[keep][mine[j]]), (float(x), float(y), float(x + bw), float(y + bh))))
    return sorted(found, key=lambda f: -f[1])


class Detector:
    """A TFLite detector of either kind:
    SSD, with the standard 4 outputs: boxes [1,N,4], classes [1,N], scores [1,N], count [1]
    YOLO (models/make_model.py), with one output [1, 4+K, A], input NHWC or NCHW."""

    def __init__(self, model_path, labels_path, threads=3):
        Interpreter = _interpreter_class()
        self.interp = Interpreter(model_path=model_path, num_threads=threads)
        self.interp.allocate_tensors()
        inp = self.interp.get_input_details()[0]
        self.in_index = inp["index"]
        shape = [int(v) for v in inp["shape"]]
        self.nchw = shape[1] == 3
        self.in_h, self.in_w = shape[2:4] if self.nchw else shape[1:3]
        self.in_float = inp["dtype"] == np.float32
        outs = self.interp.get_output_details()
        with open(labels_path, "r", encoding="utf-8") as f:
            self.labels = [line.strip() for line in f]
        self.yolo = len(outs) == 1
        if self.yolo:
            self.out = outs[0]["index"]
            if len(self.labels) + 4 not in [int(v) for v in outs[0]["shape"]]:
                sys.exit("The labels file does not match the model: %d names for output %s."
                         % (len(self.labels), list(outs[0]["shape"])))
        elif len(outs) < 4:
            sys.exit("Model does not have the 4 detection outputs this code expects.")
        else:
            self.out_boxes, self.out_classes, self.out_scores, self.out_count = [
                o["index"] for o in outs[:4]
            ]

    def detect(self, frame_bgr, min_score=0.3):
        """Return [(label, score, (x0, y0, x1, y1))] with box values in 0..1."""
        img = cv2.resize(frame_bgr, (self.in_w, self.in_h))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if not self.in_float:
            tensor = img
        elif self.yolo:
            tensor = img.astype(np.float32) / 255.0
        else:
            tensor = (img.astype(np.float32) - 127.5) / 127.5
        if self.nchw:
            tensor = tensor.transpose(2, 0, 1)
        self.interp.set_tensor(self.in_index, np.ascontiguousarray(tensor[np.newaxis, ...]))
        self.interp.invoke()
        if self.yolo:
            return [f for f in decode_yolo(self.interp.get_tensor(self.out)[0], self.labels, min_score)
                    if f[0] not in ("n/a", "")]
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
# Quests and the journal
# --------------------------------------------------------------------------
Quest = collections.namedtuple("Quest", "id label xp text herd")


def quests_file(explicit=None):
    """quests.tsv is written by sync.py. Until it exists, use the seed quests."""
    if explicit:
        return explicit
    synced = os.path.join(HERE, "quests.tsv")
    return synced if os.path.exists(synced) else os.path.join(HERE, "quests.seed.tsv")


def load_quests(path):
    """quests.tsv: id <TAB> target <TAB> xp <TAB> text [<TAB> herd].
    '#' starts a comment. A quest marked "herd" needs a friend in the frame.
    A missing file means no quests yet; sniffing still works."""
    quests = []
    if not os.path.exists(path):
        return quests
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                print("skipping bad quest line (use TABs between columns):", line)
                continue
            try:
                xp = int(parts[2])
            except ValueError:
                xp = 0
            text = parts[3] if len(parts) > 3 else "Find a " + parts[1]
            herd = len(parts) > 4 and parts[4].strip().lower() == "herd"
            quests.append(Quest(parts[0].strip(), parts[1].strip().lower(), xp, text.strip(), herd))
    return quests


def choose_quest(quests, done, things, friend):
    """Which open quest does this sniff belong to?

    quests  the quests, in file order (sync.py puts the active one first)
    done    ids of quests already completed
    things  {label: score} of what Gary is sure he sees, friend excluded
    friend  a person is in frame

    Returns (quest, completed). `quest` is the open quest whose target is in
    view, or None. `completed` is that quest if this sniff finishes it, or
    None: a herd quest only completes with a friend in frame. A quest that can
    be finished right now is preferred over a herd quest that cannot. Among
    equals the surest target wins, then the earlier line of the file.
    The backend makes the same choice from the same facts (backend/rules.py).
    """
    in_view = [q for q in quests if q.id not in done and q.label in things]
    doable = [q for q in in_view if friend or not q.herd]
    pool = doable or in_view
    if not pool:
        return None, None
    quest = max(pool, key=lambda q: things[q.label])
    return quest, (quest if doable else None)


class Journal:
    """Append-only event log, one JSON object per line.

    It is the device's only output. sync.py uploads it, and a button or buzzer
    script can watch it. State is rebuilt from it on every start, so pulling
    the power loses nothing."""

    def __init__(self, path, device):
        self.path, self.device = path, device
        self.discovered = set()  # labels Gary has sniffed before
        self.done = set()        # quest ids already completed
        self.seq = 0
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue  # a half-written last line after a power cut
                    if not isinstance(rec, dict) or rec.get("type") != "discovery":
                        continue
                    if rec.get("label"):
                        self.discovered.add(rec["label"])
                    if rec.get("quest_id"):
                        self.done.add(rec["quest_id"])
            self._close_torn_line()

    def _close_torn_line(self):
        """If the power went mid-write, the file ends without a newline. End
        that line now, so the next event starts on a line of its own."""
        with open(self.path, "rb+") as f:
            f.seek(0, os.SEEK_END)
            if f.tell() == 0:
                return
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                f.write(b"\n")
                f.flush()
                os.fsync(f.fileno())

    def add(self, kind, **fields):
        self.seq += 1
        now = datetime.datetime.now(datetime.timezone.utc)
        rec = {
            "id": "%s-%d-%d" % (self.device, int(now.timestamp() * 1000), self.seq),
            "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "type": kind,
            "device": self.device,
        }
        rec.update(fields)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
            f.flush()
            os.fsync(f.fileno())  # on disk before Gary reacts
        if kind == "discovery":
            self.discovered.add(rec["label"])
            if rec.get("quest_id"):
                self.done.add(rec["quest_id"])
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
        "new": [659, 880, 1047],              # a new discovery
        "again": [587],                       # Gary has seen one before
        "quest": [523, 659, 784, 1047],       # quest complete
        "herd": [880, 1047, 1319, 1568],      # a friend is in the frame
        "nothing": [392, 330],                # nothing he can name
        "done": [523, 659, 784, 1047, 1319],  # every quest finished
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
    ap.add_argument("--model", default=os.path.join(HERE, "models", "gary_detector.tflite"))
    ap.add_argument("--labels", default=os.path.join(HERE, "models", "gary_labels.txt"))
    ap.add_argument("--quests", help="quests file (default: quests.tsv, or quests.seed.tsv until sync.py has run)")
    ap.add_argument("--log", default=os.path.join(HERE, "journal.jsonl"), help="the journal")
    ap.add_argument("--device", default="gary-01", help="name written into every journal line")
    ap.add_argument("--sounds", default=os.path.join(HERE, "sounds"))
    ap.add_argument("--audio-cmd", help='player command, for example "aplay -q -D plughw:2,0"')
    ap.add_argument("--mute", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.5, help="minimum confidence (default 0.5)")
    ap.add_argument("--window", type=int, default=5, help="frames remembered (default 5)")
    ap.add_argument("--need", type=int, default=3, help="frames needed to confirm (default 3)")
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--friend-label", default="person")
    ap.add_argument("--button-gpio", type=int, help="Raspberry Pi OS only: GPIO pin of the Sniff button")
    ap.add_argument("--show", action="store_true", help="show a window with boxes")
    ap.add_argument("--reset", action="store_true", help="set the journal aside and start over")
    args = ap.parse_args()

    detector = Detector(args.model, args.labels, args.threads)
    quests = load_quests(quests_file(args.quests))
    if args.reset and os.path.exists(args.log):
        os.rename(args.log, args.log + "." + time.strftime("%Y%m%d-%H%M%S") + ".bak")
    journal = Journal(args.log, args.device)
    ensure_sounds(args.sounds)
    speaker = Speaker(args.sounds, args.audio_cmd, args.mute)
    stable = Stability(args.window, args.need)

    known = set(detector.labels)
    for q in quests:
        if q.label not in known:
            print("WARNING: quest %s wants '%s', which this model cannot see." % (q.id, q.label))

    print("Gary is awake. Model input %dx%d. %d quests, %d done. %d kinds of thing in the journal."
          % (detector.in_w, detector.in_h, len(quests), sum(q.id in journal.done for q in quests),
             len(journal.discovered)))
    for q in quests:
        print("  [%s] %s  (%s%s)" % ("x" if q.id in journal.done else " ", q.text, q.label,
                                     ", needs a friend" if q.herd else ""))
    if not args.image:
        print("Press Enter to sniff. q + Enter quits.")
    speaker.play("hello")

    ask = threading.Event()
    stop = threading.Event()
    reload_quests = threading.Event()
    pressed_at = [0.0]

    def press(*_):
        """The button: Enter, the GPIO button, or kill -USR1 from another program."""
        pressed_at[0] = time.monotonic()
        ask.set()

    def keys():
        for line in sys.stdin:
            if line.strip().lower() == "q":
                stop.set()
                return
            press()

    pid_path = os.path.join(HERE, "gary.pid")
    if not args.image:
        threading.Thread(target=keys, daemon=True).start()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())  # stop_gary.sh: finish cleanly
        if hasattr(signal, "SIGUSR1"):  # kill -USR1 = Sniff Test, kill -HUP = reload quests.tsv
            signal.signal(signal.SIGUSR1, press)
            signal.signal(signal.SIGHUP, lambda *_: reload_quests.set())
            with open(pid_path, "w", encoding="utf-8") as f:
                f.write("%d\n" % os.getpid())
        if args.button_gpio is not None:
            try:
                from gpiozero import Button
                button = Button(args.button_gpio)
                button.when_pressed = press
                print("Sniff button on GPIO", args.button_gpio)
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
    started = time.monotonic()
    last_report = started
    frames_since = 0
    seq = 0
    frame_budget = args.window if args.image else None
    confirmed, detections, frame = {}, [], None

    sniff_ms, counts = [], {"discovery": 0, "new": 0, "miss": 0}

    def sniff(at):
        """The Sniff Test: name what is in view right now and write it down."""
        friend = args.friend_label in confirmed
        things = {l: s for l, s in confirmed.items() if l != args.friend_label}

        def latency():
            return round((time.monotonic() - at) * 1000.0, 1)

        if not things:
            rec = journal.add("miss", friend=friend, latency_ms=latency())
            counts["miss"] += 1
            sniff_ms.append(rec["latency_ms"])
            print("\nSNIFF: nothing Gary can name%s.  [%s ms]"
                  % (" (he does see a friend)" if friend else "", rec["latency_ms"]))
            speaker.play("nothing")
            return

        # An open quest's target wins if it is in view; otherwise the surest thing.
        quest, completed = choose_quest(quests, journal.done, things, friend)
        label = quest.label if quest else max(things, key=things.get)
        new = label not in journal.discovered
        rec = journal.add("discovery", label=label, score=round(things[label], 3), friend=friend, new=new,
                          quest_id=completed.id if completed else None, latency_ms=latency())
        counts["discovery"] += 1
        counts["new"] += int(new)
        sniff_ms.append(rec["latency_ms"])

        line, clips = "\nSNIFF: %s (%.0f%%)." % (label, things[label] * 100), []
        if completed:
            line += " Quest complete: %s." % completed.text
            clips.append("quest")
        elif new:
            line += " New discovery."
            clips.append("new")
        else:
            line += " Gary has seen one before."
            clips.append("again")
        if friend:
            line += " Herd Mode: a friend is in frame."
            clips.append("herd")
        elif quest and quest.herd:
            line += " That quest needs a friend in frame."
        if speaker.has(label.replace(" ", "_")):
            clips.append(label.replace(" ", "_"))  # a spoken label, if someone recorded one
        if completed and all(q.id in journal.done for q in quests):
            line += " All of today's quests are done."
            clips.append("done")
        print(line + "  [%s ms]" % rec["latency_ms"])
        speaker.play(*clips)

    def handle_sniff():
        if reload_quests.is_set():
            reload_quests.clear()
            quests[:] = load_quests(quests_file(args.quests))
            print("\nQuests reloaded: %d, %d done." % (len(quests), sum(q.id in journal.done for q in quests)))
        if ask.is_set():
            ask.clear()
            sniff(pressed_at[0])

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
                    handle_sniff()  # keep the button alive while the camera stalls
                    continue

            t0 = time.monotonic()
            detections = detector.detect(frame, min_score=min(0.3, args.threshold))
            infer_ms = (time.monotonic() - t0) * 1000.0

            best = {}
            for label, score, _ in detections:
                if score >= args.threshold:
                    best[label] = max(best.get(label, 0.0), score)
            confirmed = stable.update(best)

            decided = time.monotonic()
            timings.append(((decided - stamp) * 1000.0, infer_ms, (decided - started) * 1000.0))
            frames_since += 1

            handle_sniff()

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
        sniff(time.monotonic())  # one Sniff Test on the picture, written to the journal
        if args.save_debug and frame is not None:
            cv2.imwrite(args.save_debug, draw(frame.copy(), detections))
            print("Annotated image saved to", args.save_debug)

    if timings:
        inf = [t[1] for t in timings]
        lat = [t[0] for t in timings]
        seconds = max(1e-3, (timings[-1][2] - timings[0][2]) / 1000.0)
        print("\n%d frames, %.1f per second. Model: mean %.0f ms. Frame-to-decision: p50 %.0f ms, p95 %.0f ms, max %.0f ms."
              % (dropped + len(timings), (len(timings) - 1) / seconds if len(timings) > 1 else 0.0,
                 sum(inf) / len(inf), percentile(lat, 50), percentile(lat, 95), max(lat)))
        # t_ms is the time since Gary started. gary_numbers.py turns this file into
        # the table for the judges (issue #14).
        with open(os.path.join(HERE, "latency.csv"), "w", encoding="utf-8") as f:
            f.write("frame,frame_to_decision_ms,model_ms,t_ms\n")
            for i, (a, b, t) in enumerate(timings):
                f.write("%d,%.2f,%.2f,%.1f\n" % (dropped + i, a, b, t))
    if sniff_ms:
        print("Sniffs: %d (%d discoveries, %d new, %d misses). Answered in p50 %.0f ms, max %.0f ms."
              % (len(sniff_ms), counts["discovery"], counts["new"], counts["miss"],
                 percentile(sniff_ms, 50), max(sniff_ms)))
    print("Quests done: %d of %d." % (sum(q.id in journal.done for q in quests), len(quests)))
    time.sleep(0.3)  # let the last sound start


if __name__ == "__main__":
    main()
