#!/usr/bin/env python3
"""gary_talk.py - talk to Gary. Standard library only, like gary_io.py.

    "Go Gary"              ->  "Go ahead!"  ->  "What am I looking at?"
                           ->  "Ooh, let me think..."  ->  "That's a bird! Blue jays
                               stay all winter here, so keep an eye out for blue."

Or hold the button (gary_io.py) instead of saying "Go Gary". Or say it all in
one breath: "Go Gary, what am I looking at?".

How it works
    microphone  a recorder command streams 16 kHz mono PCM (the webcam's mic)
    listening   a loudness check cuts the sound into things said
    "Go Gary"   each short thing said goes to Gemini, which says whether it was
                "Go Gary" (and answers it, if a question came with it)
    the answer  Gemini hears the question and gets what Gary sees right now
                (seeing.json: labels only, never a picture) and answers in his
                voice; ElevenLabs speaks it
    while Gary waits for the answer he says "Ooh, let me think...", so it feels
    instant. While Gary speaks, the microphone is ignored, so he never hears
    himself.

Privacy: your voice is sent to Gemini only to answer you, and is never written
to disk or logged. Only Gary's labels go with it, never an image. Neither the
question nor its words are printed.

    # device/.env (ignored by Git): GEMINI_API_KEY=...  ELEVENLABS_API_KEY=...
    python3 gary_talk.py                     # listen with the default recorder
    python3 gary_talk.py --rec-cmd "arecord -q -D plughw:1,0 -f S16_LE -r 16000 -c 1 -t raw"
    python3 gary_talk.py --from-wav q.wav    # one recording instead of a microphone (testing)
    python3 gary_talk.py --ask "what is a goose?"   # typed question, spoken answer (testing)

Recorder: any command that writes raw signed 16-bit mono 16 kHz PCM to stdout.
Linux: arecord (above; `arecord -l` lists the webcam's card number). QNX: see
device/README.md; the default tries a few. The C270 has a built-in mic.
"""
import argparse
import base64
import datetime
import json
import math
import os
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
RATE = 16000
FRAME = 320                      # samples: 20 ms
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
GEMINI_MODEL = "gemini-3.1-flash-lite"   # 1 to 1.7 s with audio; 3.5-flash-lite took 4 to 7 s (21 Nov)
BACKUP_MODEL = "gemini-2.5-flash"         # 1.4 to 1.9 s; asked when the fast one is slow or busy
TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/%s/stream?output_format=pcm_%d"
TTS_MODEL = "eleven_flash_v2_5"  # the fastest voice; Gary's clips use eleven_v3, which is slower
DEFAULT_VOICE = "IGRoDkfYV2Frq7Ly0PRu"   # Maxim, as in make_voice.py
LISTEN_FOR = 7.0                 # seconds to wait for the question after "Go ahead"
FRESH = 3.0                      # seeing.json older than this: Gary is not looking

GARY = """You are Gary, a pocket mountain goat who goes on walks with people in London, Ontario.
You are dry, curious, warm and a little cheeky. You love the outdoors and hate flat ground.
You speak out loud through a small speaker, so: one or two short sentences, at most 35 words,
plain words, no lists, no emoji, no markdown."""

RULES = """Rules for every answer:
- Facts must be true and well known. If you are not sure of a fact, say less, not more.
- Gary's camera only knows these names, so never claim more than that. For "bird", you may
  say what it could be ("maybe a blue jay or a chickadee") but never state the species.
- Never describe, judge or identify a person. A person in view is just "a friend".
- Nothing about health, diagnosis or medicine. Nothing unsafe: no climbing, no touching
  wild animals, no eating plants or mushrooms you find.
- If Gary sees nothing he can name and the question is about what is in view, say you
  cannot quite tell and ask them to move a little closer."""

HOW = """How to answer: as Gary. If the question is about what is in view, name it and give ONE
true, surprising fact about it, ideally one that fits London, Ontario or this season. Fact first,
personality around it. No small talk about the weather, the dark or the time of day."""

WAKE_PROMPT = """Listen to this short recording.
1. heard: write down exactly the words that were said, nothing else.
2. answer: if the words start with a call to Gary ("Go Gary", "Hey Gary"...) followed by a
   question or request, write Gary's spoken answer to that question. Otherwise "".
Reply with JSON only: {"heard": "...", "answer": "..."}."""

# "Go Gary" and its cousins, at the very start of what was said. Checked in code, not by
# Gemini, so talking ABOUT Gary ("Gary is a good name") never wakes him.
WAKE_WORDS = ("go", "hey", "hi", "yo", "okay", "ok", "oi")
GARY_SPELLINGS = ("gary", "garry", "gerry", "gary's", "garey", "geri")


def wake_split(heard):
    """-> (woke, words after the call). "Go Gary, what's that?" -> (True, "what's that")."""
    words = "".join(c.lower() if c.isalnum() or c in "' " else " " for c in str(heard or "")).split()
    for i in range(min(2, len(words))):          # allow one word first: "uh, go Gary"
        if (i + 1 < len(words) and words[i] in WAKE_WORDS and words[i + 1] in GARY_SPELLINGS):
            return True, " ".join(words[i + 2:])
    return False, ""


def now_context(seeing, today=None):
    """What Gary knows right now, for Gemini: the labels in view and the season."""
    today = today or datetime.datetime.now()
    labels = sorted((seeing or {}).get("labels", {}).items(), key=lambda kv: -kv[1])
    view = ", ".join("%s (%.0f%%)" % (k, v * 100) for k, v in labels) or "nothing he can name"
    friend = " A friend is in the frame." if (seeing or {}).get("friend") else ""
    return "Right now Gary's camera sees: %s.%s It is %s, %s, in London, Ontario." % (
        view, friend, today.strftime("%B"), "morning" if today.hour < 12 else "afternoon" if today.hour < 18 else "evening")


def read_seeing(path, fresh=FRESH, clock=time.time):
    """seeing.json, if Gary wrote it in the last few seconds. Else None."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or clock() - float(data.get("ts", 0)) > fresh:
        return None
    return data


# --------------------------------------------------------------------------
# Listening: cut a stream of sound into the things said
# --------------------------------------------------------------------------
def rms(frame):
    """Loudness of 16-bit little-endian PCM (audioop is gone from Python 3.13)."""
    n = len(frame) // 2
    if not n:
        return 0.0
    samples = struct.unpack("<%dh" % n, frame[:n * 2])
    return math.sqrt(sum(s * s for s in samples) / n)


class Utterances:
    """Feed 20 ms frames; get back each thing said, as PCM bytes.

    Speech starts when the sound is well above the room's own noise for a few
    frames, and ends after a short silence. The noise level is learned as it
    goes, so a loud hall and a quiet trail both work."""

    def __init__(self, start_frames=4, end_silence=0.6, pre_roll=0.3, longest=8.0, shortest=0.3,
                 min_level=350.0, ratio=3.0):
        self.start_frames, self.ratio, self.min_level = start_frames, ratio, min_level
        self.end_frames = int(end_silence * 1000 / 20)
        self.pre = int(pre_roll * 1000 / 20)
        self.longest, self.shortest = int(longest * 1000 / 20), int(shortest * 1000 / 20)
        self.noise = None
        self.history, self.loud, self.speech, self.quiet = [], 0, None, 0

    def threshold(self):
        return max(self.min_level, (self.noise or 0.0) * self.ratio)

    def feed(self, frame):
        level = rms(frame)
        if self.speech is None:
            # Learn the room: a slow average of the frames that are not speech.
            self.noise = level if self.noise is None else 0.98 * self.noise + 0.02 * level
            self.history = (self.history + [frame])[-self.pre - self.start_frames:]
            self.loud = self.loud + 1 if level > self.threshold() else 0
            if self.loud >= self.start_frames:
                self.speech, self.quiet = list(self.history), 0
            return None
        self.speech.append(frame)
        self.quiet = self.quiet + 1 if level <= self.threshold() else 0
        if self.quiet >= self.end_frames or len(self.speech) >= self.longest:
            said, self.speech, self.history, self.loud = self.speech, None, [], 0
            if len(said) - self.quiet < self.shortest:
                return None  # a cough or a bump
            return b"".join(said)
        return None

    def reset(self):
        self.speech, self.history, self.loud, self.quiet = None, [], 0, 0


def as_wav(pcm, rate=RATE):
    """PCM bytes -> the bytes of a WAV file, in memory (never on disk)."""
    import io
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return out.getvalue()


# --------------------------------------------------------------------------
# Gemini and ElevenLabs
# --------------------------------------------------------------------------
class TalkError(Exception):
    pass


def gemini(parts, key, model=None, as_json=False, opener=urllib.request.urlopen, timeout=None):
    """Gemini, quickly: the fast model with a short wait, then the backup model.
    parts: text and inline audio. Returns the reply text."""
    if model or timeout:
        return gemini_once(parts, key, model or os.environ.get("GARY_TALK_MODEL") or GEMINI_MODEL,
                           as_json, opener, timeout or 12)
    first = os.environ.get("GARY_TALK_MODEL") or GEMINI_MODEL
    try:
        return gemini_once(parts, key, first, as_json, opener, 5)
    except TalkError as exc:
        if "HTTP 4" in str(exc) and "HTTP 429" not in str(exc):
            raise  # our request or key is wrong: the backup would say the same
        return gemini_once(parts, key, BACKUP_MODEL, as_json, opener, 8)


def gemini_once(parts, key, name, as_json, opener, timeout):
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 160}}
    if as_json:
        body["generationConfig"]["responseMimeType"] = "application/json"
    req = urllib.request.Request(GEMINI_URL % name, data=json.dumps(body).encode("utf-8"),
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with opener(req, timeout=timeout) as reply:
            data = json.loads(reply.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except urllib.error.HTTPError as exc:
        raise TalkError("Gemini answered HTTP %d" % exc.code)
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise TalkError("Gemini: %s" % exc)


def audio_part(pcm):
    return {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(as_wav(pcm)).decode("ascii")}}


def clean(answer, longest=320):
    """Gemini's text as Gary will say it: one paragraph, no markdown, not too long."""
    text = " ".join(str(answer or "").replace("*", "").replace("#", "").split())
    if len(text) > longest:
        cut = text[:longest]
        text = cut[:max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? ")) + 1] or cut
    return text


def is_wake(pcm, key, seeing, opener=urllib.request.urlopen):
    """-> (woke, answer). The answer is non-empty when a question came with "Go Gary"."""
    reply = gemini([audio_part(pcm), {"text": "\n\n".join([GARY, RULES, HOW, now_context(seeing), WAKE_PROMPT])}],
                   key, as_json=True, opener=opener)
    try:
        data = json.loads(reply)
    except ValueError:
        return False, ""
    if not isinstance(data, dict):
        return False, ""
    woke, rest = wake_split(data.get("heard"))
    if not woke:
        return False, ""
    # Only a real question after "Go Gary" gets the answer; "Go Gary" alone gets "Go ahead".
    return True, clean(data.get("answer")) if len(rest.split()) >= 2 else ""


def answer(question, key, seeing, opener=urllib.request.urlopen):
    """question: PCM of the spoken question, or text. -> Gary's spoken answer."""
    ask = {"text": ("Answer what the person just asked you. " if isinstance(question, bytes)
                    else "The person asked you: %s. " % question) + HOW}
    parts = ([audio_part(question)] if isinstance(question, bytes) else []) + [
        {"text": "\n\n".join([GARY, RULES, now_context(seeing)])}, ask]
    return clean(gemini(parts, key, opener=opener))


def tts(text, key, voice=None, opener=urllib.request.urlopen):
    """Gary's answer -> 16 kHz PCM, from ElevenLabs' fastest voice model."""
    voice = voice or os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE
    body = json.dumps({"text": text, "model_id": os.environ.get("GARY_TALK_TTS_MODEL") or TTS_MODEL,
                       "voice_settings": {"stability": 0.35, "similarity_boost": 0.75, "style": 0.4, "speed": 1.08}})
    req = urllib.request.Request(TTS_URL % (voice, RATE), data=body.encode("utf-8"),
                                 headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        with opener(req, timeout=15) as reply:
            return reply.read()
    except urllib.error.HTTPError as exc:
        raise TalkError("ElevenLabs answered HTTP %d" % exc.code)
    except OSError as exc:
        raise TalkError("ElevenLabs: %s" % exc)


# --------------------------------------------------------------------------
# Speaking
# --------------------------------------------------------------------------
class Mouth:
    """Plays clips from sounds/ and answers made on the fly, one at a time.
    `speaking` is set while anything plays, so the ears ignore Gary himself."""

    def __init__(self, sounds, command=None):
        self.sounds = sounds
        self.speaking = threading.Event()
        self.lock = threading.Lock()
        self.cmd, self.winsound = None, None
        if command:
            self.cmd = command.split()
        elif os.name == "nt":
            import winsound
            self.winsound = winsound
        else:
            for candidate in (["mmrplay"], ["aplay", "-q"], ["afplay"], ["paplay"]):
                if shutil.which(candidate[0]):
                    self.cmd = candidate
                    break
        self.tmp = tempfile.mkdtemp(prefix="gary-talk-")

    def clip(self, name):
        path = os.path.join(self.sounds, name + ".wav")
        return path if os.path.exists(path) else None

    def play_file(self, path):
        with self.lock:
            self.speaking.set()
            try:
                if self.winsound:
                    self.winsound.PlaySound(path, self.winsound.SND_FILENAME)
                elif self.cmd:
                    subprocess.run(self.cmd + [path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            except Exception as exc:  # sound must never stop the ears
                print("audio error:", exc)
            finally:
                time.sleep(0.25)  # the room's echo of Gary's last word
                self.speaking.clear()

    def say_clip(self, name):
        path = self.clip(name)
        if path:
            self.play_file(path)

    def say_pcm(self, pcm):
        path = os.path.join(self.tmp, "answer.wav")  # Gary's voice, not yours
        with open(path, "wb") as f:
            f.write(as_wav(pcm))
        self.play_file(path)


# --------------------------------------------------------------------------
# The conversation
# --------------------------------------------------------------------------
class Talk:
    IDLE, LISTENING = "idle", "listening"

    def __init__(self, mouth, gemini_key, eleven_key, seeing_path, say=print,
                 ask_answer=answer, ask_wake=is_wake, speak=tts, clock=time.monotonic):
        self.mouth, self.say = mouth, say
        self.gemini_key, self.eleven_key, self.seeing_path = gemini_key, eleven_key, seeing_path
        self.ask_answer, self.ask_wake, self.speak, self.clock = ask_answer, ask_wake, speak, clock
        self.state, self.until = self.IDLE, 0.0
        self.busy = threading.Lock()

    def wake(self):
        """"Go Gary" heard, or the button held: say "Go ahead" and listen."""
        self.say("talk: listening")
        self.mouth.say_clip("say_go_ahead")
        self.state, self.until = self.LISTENING, self.clock() + LISTEN_FOR

    def tick(self):
        if self.state == self.LISTENING and self.clock() > self.until:
            self.say("talk: nothing asked, back to waiting for \"Go Gary\"")
            self.state = self.IDLE

    def heard(self, pcm):
        """One thing said (PCM). Returns what Gary did, for the log and the tests."""
        if not self.busy.acquire(blocking=False):
            return "busy"
        try:
            seeing = read_seeing(self.seeing_path)
            if self.state == self.LISTENING:
                self.state = self.IDLE
                return self.respond(pcm, seeing)
            if len(pcm) > 6 * RATE * 2:
                return "ignored"  # too long to be "Go Gary": someone talking nearby
            t0 = self.clock()
            woke, reply = self.ask_wake(pcm, self.gemini_key, seeing)
            if not woke:
                return "ignored"
            self.say("talk: \"Go Gary\" (%.1f s)" % (self.clock() - t0))
            if reply:
                return self.speak_answer(reply, t0)
            self.wake()
            return "woke"
        except TalkError as exc:
            self.say("talk: %s" % exc)
            return "error"
        finally:
            self.busy.release()

    def respond(self, question, seeing):
        """Answer a question (PCM or text), with "let me think" while Gemini works."""
        t0 = self.clock()
        thinking = threading.Thread(target=self.mouth.say_clip, args=("say_thinking",), daemon=True)
        thinking.start()
        try:
            reply = self.ask_answer(question, self.gemini_key, seeing)
            return self.speak_answer(reply, t0, thinking)
        except TalkError as exc:
            self.say("talk: %s" % exc)
            thinking.join()
            self.mouth.say_clip("say_ears")
            return "error"

    def speak_answer(self, reply, t0, thinking=None):
        if not reply:
            raise TalkError("Gemini gave no answer")
        pcm = self.speak(reply, self.eleven_key)
        if thinking is not None:
            thinking.join()
        self.say("Gary: %s  [%.1f s to speak]" % (reply, self.clock() - t0))
        self.mouth.say_pcm(pcm)
        return "answered"


def default_recorder():
    """A recorder command for this machine, or None."""
    if shutil.which("arecord"):
        return ["arecord", "-q", "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw"]
    if shutil.which("sox"):
        return ["sox", "-q", "-d", "-t", "raw", "-r", str(RATE), "-e", "signed", "-b", "16", "-c", "1", "-"]
    if shutil.which("ffmpeg") and os.name == "nt":
        return None  # needs the microphone's name: pass --rec-cmd
    return None


def frames_from_wav(path):
    with wave.open(path) as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, RATE):
            sys.exit("%s must be 16-bit mono %d Hz" % (path, RATE))
        pcm = w.readframes(w.getnframes())
    pcm += b"\x00\x00" * RATE  # a second of silence, so the last thing said ends
    for i in range(0, len(pcm) - FRAME * 2 + 1, FRAME * 2):
        yield pcm[i:i + FRAME * 2]


def frames_from_command(cmd):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        while True:
            chunk = proc.stdout.read(FRAME * 2)
            if len(chunk) < FRAME * 2:
                break
            yield chunk
    finally:
        proc.kill()
        proc.wait()


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Talk to Gary: say \"Go Gary\", then ask.")
    ap.add_argument("--dir", default=HERE, help="the device folder (seeing.json, sounds/, .env)")
    ap.add_argument("--rec-cmd", default=os.environ.get("GARY_TALK_REC") or None,
                    help="recorder writing raw 16-bit mono 16 kHz PCM to stdout (or GARY_TALK_REC in gary.env)")
    ap.add_argument("--audio-cmd", help='player command, for example "aplay -q -D plughw:2,0"')
    ap.add_argument("--from-wav", help="listen to this WAV file instead of a microphone (testing)")
    ap.add_argument("--ask", help="a typed question: Gary answers it out loud, then exits (testing)")
    args = ap.parse_args(argv)

    load_env(os.path.join(args.dir, ".env"))
    load_env(os.path.join(args.dir, "..", "scout", ".env"))  # the laptop keeps the Gemini key there
    gkey, ekey = os.environ.get("GEMINI_API_KEY"), os.environ.get("ELEVENLABS_API_KEY")
    if not gkey or not ekey:
        sys.exit("Put GEMINI_API_KEY and ELEVENLABS_API_KEY in device/.env (ignored by Git).")
    mouth = Mouth(os.path.join(args.dir, "sounds"), args.audio_cmd)
    talk = Talk(mouth, gkey, ekey, os.path.join(args.dir, "seeing.json"))

    if args.ask:
        print(talk.respond(args.ask, read_seeing(talk.seeing_path)))
        return

    pid_path = os.path.join(args.dir, "gary_talk.pid")
    with open(pid_path, "w") as f:
        f.write("%d\n" % os.getpid())
    if hasattr(signal, "SIGUSR2"):  # gary_io.py sends it when the button is held
        signal.signal(signal.SIGUSR2, lambda *_: threading.Thread(target=talk.wake, daemon=True).start())

    if args.from_wav:
        frames = frames_from_wav(args.from_wav)
    else:
        cmd = shlex.split(args.rec_cmd) if args.rec_cmd else default_recorder()
        if not cmd:
            sys.exit("No recorder found. Set GARY_TALK_REC in gary.env, or pass --rec-cmd (see the top of this file).")
        frames = frames_from_command(cmd)

    ears = Utterances()
    print("Gary is listening. Say \"Go Gary\".")
    try:
        for frame in frames:
            talk.tick()
            if mouth.speaking.is_set() or talk.busy.locked():
                ears.reset()  # never answer Gary's own voice
                continue
            said = ears.feed(frame)
            if said:
                if args.from_wav:
                    talk.heard(said)  # in order, so a test file plays like a conversation
                else:
                    threading.Thread(target=talk.heard, args=(said,), daemon=True).start()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            os.remove(pid_path)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
