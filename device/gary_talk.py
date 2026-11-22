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
import random
import urllib.error
import urllib.parse
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
TTS_SPEED = 1.2                  # ElevenLabs' fastest allowed; 1.08 sounded slow (21 Nov)
LISTEN_FOR = 7.0                 # seconds to wait for the question after "Go ahead"
FRESH = 3.0                      # seeing.json older than this: Gary is not looking
CONVERSATION_FOR = 120.0         # seconds Gary remembers the conversation (in memory only)
LABELS = os.path.join(HERE, "..", "contract", "labels.json")
# "Let me think" clips (make_voice.py), one picked at random, never the same twice running
THINKING = ("say_thinking", "say_thinking_2", "say_thinking_3", "say_thinking_4", "say_thinking_5")

GARY = """You are Gary, a pocket mountain goat who goes on walks with people in London, Ontario.
You are dry, curious, warm and a little cheeky. You love the outdoors and hate flat ground.
You speak out loud through a small speaker, so: one or two short sentences, at most 35 words,
plain words, no lists, no emoji, no markdown. Talk like a friend, with contractions (I'm,
that's, you've, can't), never stiff."""

RULES = """Rules for every answer:
- Facts must be true and well known. If you are not sure of a fact, say less, not more.
- Gary's camera only knows these names, so never claim more than that. For "bird", you may
  say what it could be ("maybe a blue jay or a chickadee") but never state the species.
- Never describe, judge or identify a person. A person in view is just "a friend".
- Nothing about health, diagnosis or medicine. Nothing unsafe: no climbing, no touching
  wild animals, no eating plants or mushrooms you find.
- If Gary sees nothing he can name and the question is about what is in view, say you
  cannot quite tell and ask them to move a little closer."""

HOW = """What Gary can do, and how to answer (as Gary, always):
- What is in view ("what am I looking at?", "what's that?"): name it and give ONE true,
  surprising fact about it, ideally one that fits London, Ontario or this season.
- Anything in the app, from "The app right now" below: his stage and XP and how far to the
  next stage, napping, today's quest (what, where, how long, the note on where to stand, who
  found it), the short and long options, today's finds, the field guide, places uncovered on
  the map, places reached, the Herd Cup (herds only: never rank a person), badges. Use those
  facts exactly; never invent quests, places, numbers or finds.
- Where they are: Gary does NOT know their exact position. Their phone keeps it to itself,
  on purpose (not the camera). Say what he does know: the city, the quest's place, the places they reached or
  uncovered. Never guess an address.
- A greeting ("good morning", "hi Gary"): greet back warmly, one short line about Gary today,
  then ask if they want a quest, short or long. Set listen to true.
- Asking for a quest or task ("give me a task", "a short one", "yes, long"): pick it with
  do = choose_quest. Short or long unclear: ask which, listen true, no do. Say the quest from
  the matching option in "The app right now" (title and place).
- Asking Gary to make one ("create a task for me", "make me a quest to find a duck at the
  pond"): do = create_quest. target must be one of THINGS GARY CAN FIND; if what they asked
  for is not there, say so and offer the closest one, no do. place: what they said, else
  "somewhere nearby". Public, safe places only. Then tell them it is added to their quests.
- How they feel, mood, check-ins: never read any out. Kindly point to the private You tab.
- Anything else: a short, true answer in Gary's voice.
Never say you did something that is not in do. No small talk about the weather, the dark or
the time of day unless asked."""

REPLY = """Reply with JSON only:
{"heard": "the words they said",
 "say": "Gary's spoken reply",
 "do": null, or {"action": "choose_quest", "time": "short" or "long"},
       or {"action": "create_quest", "target": "...", "place": "...", "time": "short" or "long", "herd": false},
 "listen": true if Gary asked them something and should wait for their answer, else false}"""

WAKE_PROMPT = """Listen to this short recording.
heard: write down exactly the words that were said, nothing else.
If the words start with a call to Gary ("Go Gary", "Hey Gary"...) followed by a question,
greeting or request, answer that part as below. Otherwise say is "" and do is null.
""" + REPLY

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


def read_seeing(path, fresh=FRESH, clock=time.time, opener=urllib.request.urlopen):
    """seeing.json, if Gary wrote it in the last few seconds. Else None.
    `path` may be a URL (the backend's /api/seeing), so talk can run on a laptop."""
    try:
        if path.startswith(("http://", "https://")):
            with opener(path, timeout=2) as r:
                data = json.load(r)
        else:
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
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 400}}
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


def reply_of(text):
    """Gemini's JSON reply -> {"heard", "say", "do", "listen"}, cleaned and safe to use."""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        data = {"say": text}  # plain words: still something Gary can say
    if not isinstance(data, dict):
        data = {}
    do = data.get("do") if isinstance(data.get("do"), dict) else None
    if do and do.get("action") not in ("choose_quest", "create_quest"):
        do = None
    return {"heard": str(data.get("heard") or ""), "say": clean(data.get("say") or data.get("answer")),
            "do": do, "listen": data.get("listen") is True}


def as_reply(answer_or_reply):
    """A plain string (older callers, tests) or a reply dict -> a reply dict."""
    if isinstance(answer_or_reply, dict):
        return answer_or_reply
    return {"heard": "", "say": clean(answer_or_reply), "do": None, "listen": False}


def context(seeing, app_text="", history=()):
    """Everything Gary knows for one answer."""
    parts = [GARY, RULES, HOW, now_context(seeing)]
    if app_text:
        parts.append(app_text)
    if history:
        parts.append("The conversation so far (oldest first):\n" + "\n".join(
            "They said: %s\nGary said: %s" % (h, s) for h, s in history))
    return "\n\n".join(parts)


def is_wake(pcm, key, seeing, opener=urllib.request.urlopen, app_text="", history=()):
    """-> (woke, reply). reply has something to say when a question came with "Go Gary"."""
    raw = gemini([audio_part(pcm), {"text": context(seeing, app_text, history) + "\n\n" + WAKE_PROMPT}],
                 key, as_json=True, opener=opener)
    reply = reply_of(raw)
    woke, rest = wake_split(reply["heard"])
    if not woke:
        return False, None
    # Only a real question after "Go Gary" gets an answer; "Go Gary" alone gets "Go ahead".
    if len(rest.split()) < 2 or not reply["say"]:
        return True, None
    return True, reply


def answer(question, key, seeing, opener=urllib.request.urlopen, app_text="", history=()):
    """question: PCM of the spoken question, or text. -> a reply dict."""
    ask = ("Answer what the person just said to you." if isinstance(question, bytes)
           else "The person said to you: %s" % question)
    parts = ([audio_part(question)] if isinstance(question, bytes) else []) + [
        {"text": context(seeing, app_text, history) + "\n\n" + ask + "\n\n" + REPLY}]
    reply = reply_of(gemini(parts, key, as_json=True, opener=opener))
    if not reply["heard"] and not isinstance(question, bytes):
        reply["heard"] = str(question)
    return reply


# --------------------------------------------------------------------------
# The app: what Gary may say about it, and the two things he may do in it
# --------------------------------------------------------------------------
def read_things(path=LABELS):
    """The names Gary can find outdoors: a quest's target must be one of them."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return sorted(x["name"] for x in data["labels"] if x.get("outdoor") and x["name"] != data.get("friend"))
    except (OSError, ValueError, KeyError, TypeError):
        return ["bench", "bicycle", "bird", "dog", "duck", "flower", "goose", "squirrel", "tree"]


def app_context(state, things=()):
    """The backend's /api/state, as a few plain lines for Gemini. Mood is never in it."""
    if not state:
        return "The app right now: not reachable. Say so if they ask about quests or progress."
    lines = ["The app right now:"]
    g = state.get("gary") or {}
    stage = str(g.get("stage") or "kid").replace("-", " ").title()
    lines.append("- Gary is a %s with %s XP%s.%s%s" % (
        stage, g.get("xp", 0),
        ", %s XP to the next stage" % (g["next_stage_xp"] - g.get("xp", 0)) if g.get("next_stage_xp") else ", the top stage",
        " He is napping (no guilt: a quiet spell)." if g.get("napping") else "",
        " The person just came back after a break." if g.get("welcome_back") else ""))

    def quest_line(q):
        found = " Found by the scout on %s." % urllib.parse.urlparse(q["source_url"]).netloc if (
            q.get("source") == "tinyfish" and q.get("source_url")) else ""
        return '"%s" at %s, %s (about %s min), find a %s, %s XP%s.%s%s' % (
            q.get("title"), q.get("place"), q.get("time"), q.get("minutes", "?"), q.get("target"), q.get("xp"),
            ", needs a friend in the frame" if q.get("herd") else "",
            " Where to stand: %s" % q["note"] if q.get("note") else "", found)
    q = state.get("quest")
    lines.append("- Today's quest: %s" % (quest_line(q) if q else "none open."))
    for time_ in ("short", "long"):
        o = (state.get("quest_options") or {}).get(time_)
        lines.append("- If they pick %s: %s" % (time_, quest_line(o) if o else "no %s quest is open." % time_))
    lines.append("- Open quests: %s." % state.get("quests_open", "?"))
    journal = state.get("journal") or []
    if journal:
        lines.append("- Latest finds: %s." % ", ".join(
            "%s%s%s" % (e.get("label"), " (new)" if e.get("new") else "", " (finished a quest)" if e.get("quest_id") else "")
            for e in journal[:5]))
    guide = state.get("guide") or {}
    if guide:
        lines.append("- Field guide: %d of %s found%s." % (
            len(guide.get("found") or []), guide.get("total", "?"),
            " (%s)" % ", ".join((guide.get("found") or [])[:8]) if guide.get("found") else ""))
    tiles = state.get("map") or []
    uncovered = [t["place"] for t in tiles if t.get("cleared")]
    reached = [t["place"] for t in tiles if t.get("visited")]
    lines.append("- Map: %s uncovered%s. Places reached (the phone said they were there): %s." % (
        len(uncovered), " (%s)" % ", ".join(uncovered[:6]) if uncovered else "", ", ".join(reached[:6]) or "none yet"))
    cup = (state.get("herd") or {}).get("cup") or {}
    if cup:
        lines.append("- Herd Cup this week: your herd is %s of %s herds%s." % (
            cup.get("rank", "?"), cup.get("herds", "?"), " (the rival herds are demo data)" if cup.get("demo") else ""))
    badges = (state.get("herd") or {}).get("badges") or []
    if badges:
        lines.append("- Badges: %s." % ", ".join(badges))
    if things:
        lines.append("THINGS GARY CAN FIND (a made quest's target must be one): %s." % ", ".join(things))
    return "\n".join(lines)


class App:
    """The backend, as Gary uses it: its state (refreshed in the background, so
    answers never wait for it), picking a quest, and making one."""

    def __init__(self, api, scout_key=None, opener=urllib.request.urlopen, clock=time.time):
        self.api = (api or "").rstrip("/")
        self.scout_key, self.opener, self.clock = scout_key, opener, clock
        self.state, self.at = None, 0.0
        self.things = read_things()

    def _call(self, path, body=None, headers=None, timeout=3):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.api + path, data=data, headers=dict(
            {"Content-Type": "application/json"} if body is not None else {}, **(headers or {})))
        try:
            with self.opener(req, timeout=timeout) as reply:
                return json.loads(reply.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise TalkError("the app answered HTTP %d" % exc.code)
        except (OSError, ValueError) as exc:
            raise TalkError("the app: %s" % exc)

    def refresh(self):
        if not self.api:
            return None
        try:
            self.state, self.at = self._call("/api/state", timeout=2), self.clock()
        except TalkError:
            pass
        return self.state

    def start(self, every=5.0):
        def loop():
            while True:
                self.refresh()
                time.sleep(every)
        threading.Thread(target=loop, daemon=True).start()

    def text(self):
        if self.api and self.clock() - self.at > 20:
            self.refresh()  # stale: one quick look before answering
        return app_context(self.state, self.things) if self.api else ""

    def choose(self, time_):
        """Make a short or long quest the active one. -> that quest, or None."""
        got = self._call("/api/quest/choose", {"time": time_})
        if isinstance(got.get("state"), dict):
            self.state, self.at = got["state"], self.clock()
        return got.get("quest")

    def create(self, target, place, time_, herd=False, today=None):
        """Add a quest Gary was asked to make. -> the quest. Source "gary": never "tinyfish"."""
        target = str(target or "").strip().lower()
        if target not in self.things:
            raise TalkError("Gary cannot find a %r" % target)
        place = " ".join(str(place or "somewhere nearby").split())[:60] or "somewhere nearby"
        is_long = time_ == "long"
        day = (today or datetime.date.today()).isoformat()
        spoken = {"bottle": "water bottle"}.get(target, target)
        quest = {"id": "gary-%s-%s-%s" % (day, target.replace(" ", "-"), base64.b32encode(os.urandom(5)).decode().lower()[:6]),
                 "title": "Find a %s at %s%s" % (spoken, place, ", with a friend" if herd else ""),
                 "place": place, "time": "long" if is_long else "short", "minutes": 40 if is_long else 15,
                 "target": target, "xp": 40 if is_long else 20, "herd": bool(herd),
                 "note": "Gary made this one when you asked. Stay on public paths.",
                 "source": "gary", "source_url": None, "day": day}
        headers = {"X-Scout-Key": self.scout_key} if self.scout_key else {}
        got = self._call("/api/quests", {"quests": [quest]}, headers)
        if quest["id"] not in (got.get("accepted") or []):
            why = (got.get("rejected") or [{}])[0].get("why", "not accepted")
            raise TalkError("the app refused the quest: %s" % why)
        self.refresh()
        return quest


def tts(text, key, voice=None, opener=urllib.request.urlopen):
    """Gary's answer -> 16 kHz PCM, from ElevenLabs' fastest voice model."""
    voice = voice or os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE
    body = json.dumps({"text": text, "model_id": os.environ.get("GARY_TALK_TTS_MODEL") or TTS_MODEL,
                       "voice_settings": {"stability": 0.35, "similarity_boost": 0.75, "style": 0.4, "speed": TTS_SPEED}})
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
                 ask_answer=answer, ask_wake=is_wake, speak=tts, clock=time.monotonic, app=None):
        self.mouth, self.say = mouth, say
        self.gemini_key, self.eleven_key, self.seeing_path = gemini_key, eleven_key, seeing_path
        self.ask_answer, self.ask_wake, self.speak, self.clock = ask_answer, ask_wake, speak, clock
        self.app = app
        self.state, self.until = self.IDLE, 0.0
        self.busy = threading.Lock()
        # The conversation, in memory only: (what they said, what Gary said). Never written down.
        self.history, self.last_word = [], 0.0
        self.last_thinking = None

    def wake(self):
        """"Go Gary" heard, or the button held: say "Go ahead" and listen."""
        self.say("talk: listening")
        self.mouth.say_clip("say_go_ahead")
        self.listen()

    def listen(self):
        self.state, self.until = self.LISTENING, self.clock() + LISTEN_FOR

    def tick(self):
        if self.state == self.LISTENING and self.clock() > self.until:
            self.say("talk: nothing asked, back to waiting for \"Go Gary\"")
            self.state = self.IDLE
        if self.history and self.clock() - self.last_word > CONVERSATION_FOR:
            self.history = []  # a new conversation starts fresh

    def remembered(self):
        if self.history and self.clock() - self.last_word > CONVERSATION_FOR:
            self.history = []
        return tuple(self.history[-4:])

    def app_text(self):
        return self.app.text() if self.app else ""

    def call(self, fn, *args):
        """Ask Gemini through `fn`, with the app and the conversation when it takes them."""
        try:
            return fn(*args, app_text=self.app_text(), history=self.remembered())
        except TypeError:
            return fn(*args)  # a stand-in (tests) that takes only the basics

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
            woke, reply = self.call(self.ask_wake, pcm, self.gemini_key, seeing)
            if not woke:
                return "ignored"
            self.say("talk: \"Go Gary\" (%.1f s)" % (self.clock() - t0))
            if reply:
                return self.speak_answer(as_reply(reply), t0)
            self.wake()
            return "woke"
        except TalkError as exc:
            self.say("talk: %s" % exc)
            return "error"
        finally:
            self.busy.release()

    def thinking_clip(self):
        """One of the "let me think" lines, never the same one twice running."""
        have = [c for c in THINKING if self.mouth.clip(c)] if hasattr(self.mouth, "clip") else list(THINKING[:1])
        choices = [c for c in have if c != self.last_thinking] or have
        self.last_thinking = random.choice(choices) if choices else None
        return self.last_thinking

    def respond(self, question, seeing):
        """Answer what was said (PCM or text), with "let me think" while Gemini works."""
        t0 = self.clock()
        clip = self.thinking_clip()
        thinking = threading.Thread(target=self.mouth.say_clip, args=(clip,), daemon=True)
        if clip:
            thinking.start()
        try:
            reply = as_reply(self.call(self.ask_answer, question, self.gemini_key, seeing))
            return self.speak_answer(reply, t0, thinking if clip else None)
        except TalkError as exc:
            self.say("talk: %s" % exc)
            if clip:
                thinking.join()
            self.mouth.say_clip("say_ears")
            return "error"

    def act(self, reply):
        """Do what the reply asks in the app. Returns what Gary should say."""
        do, said = reply.get("do"), reply["say"]
        if not do:
            return said
        if not self.app or not self.app.api:
            self.say("talk: no app address, so nothing was %s" % do.get("action"))
            return "I can't reach the app from here, so I couldn't do that one. Try the buttons on the page?"
        try:
            if do["action"] == "choose_quest":
                time_ = "long" if do.get("time") == "long" else "short"
                quest = self.app.choose(time_)
                if not quest:
                    return "No %s quests are open right now. Want a %s one instead?" % (
                        time_, "long" if time_ == "short" else "short")
                self.say("talk: picked %s" % quest.get("id"))
                if quest.get("title") and quest["title"].lower() not in said.lower():
                    said = "Here's one: %s, at %s." % (quest["title"], quest.get("place"))
                return said
            if do["action"] == "create_quest":
                quest = self.app.create(do.get("target"), do.get("place"), do.get("time"), do.get("herd") is True)
                self.say("talk: made %s" % quest["id"])
                return said or "Done! %s. It's in your quests." % quest["title"]
        except TalkError as exc:
            self.say("talk: %s" % exc)
            return "Hmm, the app wouldn't let me do that one just now."
        return said

    def speak_answer(self, reply, t0, thinking=None):
        reply = as_reply(reply)
        if not reply["say"] and not reply.get("do"):
            raise TalkError("Gemini gave no answer")
        said = self.act(reply)
        pcm = self.speak(said, self.eleven_key)
        if thinking is not None:
            thinking.join()
        self.say("Gary: %s  [%.1f s to speak]" % (said, self.clock() - t0))
        self.mouth.say_pcm(pcm)
        self.history.append((reply.get("heard") or "(something)", said))
        self.history = self.history[-6:]
        self.last_word = self.clock()
        if reply.get("listen"):
            self.listen()  # he asked them something: no "Go Gary" needed for the answer
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
    ap.add_argument("--seeing", help="what Gary sees: a file, or a URL such as http://localhost:8800/api/seeing "
                    "(talk on a laptop, Gary on the Pi). Default: seeing.json in --dir")
    ap.add_argument("--api", help="the backend, for quests and progress (default: GARY_API, or the --seeing address)")
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
    api = args.api or os.environ.get("GARY_API") or ""
    if not api and (args.seeing or "").startswith(("http://", "https://")):
        api = args.seeing.split("/api/")[0]
    app = App(api, os.environ.get("SCOUT_KEY"))
    print("Gary's app: %s" % (api or "none (set GARY_API or --api to answer about quests)"))
    talk = Talk(mouth, gkey, ekey, args.seeing or os.path.join(args.dir, "seeing.json"), app=app)

    if args.ask:
        app.refresh()
        print(talk.respond(args.ask, read_seeing(talk.seeing_path)))
        return
    app.start()

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
