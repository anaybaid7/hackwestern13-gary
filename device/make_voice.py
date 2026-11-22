#!/usr/bin/env python3
"""make_voice.py - make Gary's spoken clips with ElevenLabs, once, on a laptop.

Gary never calls ElevenLabs himself. This script writes WAV files into
sounds/, and both versions of Gary (gary_device.py and qnx/gary_qnx.cpp) play
them from there: instantly, with no network, and no key on the Pi. A clip that
is missing falls back to the chimes, so Gary is never silent.

    # device/.env (ignored by Git):
    #   ELEVENLABS_API_KEY=sk_...
    #   ELEVENLABS_VOICE_ID=...        optional, default Maxim
    python3 make_voice.py --dry-run    # print every line, call nothing
    python3 make_voice.py              # make the clips that are missing
    python3 make_voice.py --force      # make them all again (a new voice, new lines)
                                       # then set VOICE_RATE back to 1 in web/src/sound.js
    python3 make_voice.py --only say_bottle say_found_bottle

The clips, and when Gary plays them (voice_clips() in gary_device.py):
    say_hello              at start
    say_nothing            nothing he can name: "can you move closer?"
    say_found_<label>      the quest's thing: "You found the water bottle!"
    say_not_it + say_<l>   something else while a quest is open
    say_<label> + say_new  a first find, with no quest open
    say_need_friend        the quest's thing, but the quest needs a friend
    say_herd               a friend is in the frame
    say_done              every quest is finished
    say_meet_*             the page's hello for a new person (not played by the device)
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
LABELS = os.path.join(HERE, "..", "contract", "labels.json")
URL = "https://api.elevenlabs.io/v1/text-to-speech/%s?output_format=pcm_%d"
DEFAULT_VOICE = "IGRoDkfYV2Frq7Ly0PRu"   # Maxim
DEFAULT_MODEL = "eleven_v3"   # reads the [excited]-style cues below; set ELEVENLABS_MODEL to change
# How Gary sounds. eleven_v3 takes stability 0.0 (creative), 0.5 (natural) or
# 1.0 (robust) and its intonation from the cues. Older models take the rest:
# lower stability = more rise and fall, style = more character, speed 0.7-1.2.
V3_SETTINGS = {"stability": 0.5}
VOICE_SETTINGS = {"stability": 0.3, "similarity_boost": 0.75, "style": 0.45, "use_speaker_boost": True, "speed": 1.12}

# How Gary says each kind of line: eleven_v3 audio tags. Other models would
# read a tag out loud, so for them the tags are left off.
CUES = {
    "say_hello": "[cheerful] Hi! I'm Gary. [playfully] Press my button, and I'll take a sniff.",
    "say_nothing": "[thoughtful] Hmm... [curious] I can't quite tell. Can you move a little closer?",
    "say_not_it": "[playfully] Ooh, close! [lighthearted] But that's not what we're looking for.",
    "say_new": "[excited] Ooh, a new one for the journal!",
    "say_need_friend": "[excited] That's the one! [warmly] But this quest needs a friend in the frame.",
    "say_herd": "[delighted] Herd Mode! [warmly] I love the company.",
    "say_done": "[proud] That's every quest for today. [laughs] Amazing work!",
    "say_go_ahead": "[cheerful] Go ahead!",
    "say_thinking": "[curious] Ooh, let me think...",
    "say_ears": "[thoughtful] Hmm, my ears are a bit fuzzy. [playfully] Try me again?",
    # the page's hello for a new person (web/src/components/Welcome.jsx)
    "say_meet_wake": "[yawns] Baa! [cheerful] I'm Gary, your pocket goat. [warmly] I belong outside: trails, parks, hills. [playfully] Come with me?",
    "say_meet_sniff": "[lighthearted] On a walk, point me at things. [playfully] Press my button to sniff.",
    "say_meet_quest": "[curious] I find quests on real trails near you. [warmly] Pick a walk.",
    "say_meet_walk": "[excited] Off we go! [warmly] Every walk lifts the fog.",
    "say_meet_feel": "[gently] Before we head out: how do you feel?",
    "say_meet_felt": "[warmly] Thanks. I ask again after. [gently] Only you see it.",
    "say_meet_go": "[lighthearted] No streaks, no guilt. A break is just a nap. [excited] Let's get outside!",
}
PREFIX_CUES = (("say_found_", "[excited] "), ("say_", "[curious] "))


def performed(clip, text, model):
    """The text sent to ElevenLabs: with eleven_v3's cues, or as it is for other models."""
    if not model.startswith("eleven_v3"):
        return text
    if clip in CUES:
        return CUES[clip]
    return next(cue for prefix, cue in PREFIX_CUES if clip.startswith(prefix)) + text
RATE = 16000                             # plenty for a small speaker; keeps the clips small

# How a label is said out loud, where the label itself reads badly.
SPOKEN = {"bottle": "water bottle", "tv": "TV", "cell phone": "phone", "hair drier": "hair dryer",
          "sports ball": "ball", "dining table": "table", "potted plant": "plant", "remote": "remote control",
          "mouse": "computer mouse", "street lamp": "street lamp"}
PLURAL = {"skis", "scissors"}            # "those are scissors", not "that's a scissors"

FIXED = {
    "say_hello": "Hi! I'm Gary. Press my button, and I'll take a sniff.",
    "say_nothing": "Hmm... I can't quite tell. Can you move a little closer?",
    "say_not_it": "Ooh, close! But that's not what we're looking for.",
    "say_new": "Ooh, a new one for the journal!",
    "say_need_friend": "That's the one! But this quest needs a friend in the frame.",
    "say_herd": "Herd Mode! I love the company.",
    "say_done": "That's every quest for today. Amazing work!",
    # Talking to Gary (gary_talk.py)
    "say_go_ahead": "Go ahead!",
    "say_thinking": "Ooh, let me think...",
    "say_ears": "Hmm, my ears are a bit fuzzy. Try me again?",
    # the page's hello for a new person: the same words as LINES in web/src/components/Welcome.jsx
    "say_meet_wake": "Baa! I'm Gary, your pocket goat. I belong outside: trails, parks, hills. Come with me?",
    "say_meet_sniff": "On a walk, point me at things. Press my button to sniff.",
    "say_meet_quest": "I find quests on real trails near you. Pick a walk.",
    "say_meet_walk": "Off we go. Every walk lifts the fog.",
    "say_meet_feel": "Before we head out: how do you feel?",
    "say_meet_felt": "Thanks. I ask again after. Only you see it.",
    "say_meet_go": "No streaks, no guilt. A break is just a nap. Let's get outside!",
}


def clip_name(label):
    """The file-name form of a label, the same as clip_name() in gary_qnx.cpp."""
    return label.replace(" ", "_")


def spoken(label):
    return SPOKEN.get(label, label)


def thats(label):
    """'That's a bird.' / 'That's an apple.' / 'Those are scissors.'"""
    name = spoken(label)
    if label in PLURAL:
        return "Those are %s!" % name
    return "That's %s %s!" % ("an" if name[0].lower() in "aeiou" else "a", name)


def read_labels(path=LABELS):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [x["name"] for x in data["labels"] if x["name"] != data.get("friend")]


def lines(labels):
    """{clip name: what Gary says}, for every clip."""
    out = dict(FIXED)
    for label in labels:
        out["say_" + clip_name(label)] = thats(label)
        out["say_found_" + clip_name(label)] = "Yes! You found the %s!" % spoken(label)
    return out


def load_env(path, environ=None):
    """Read KEY=value lines without replacing settings already in the shell."""
    environ = os.environ if environ is None else environ
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def write_wav(path, pcm, rate=RATE):
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    os.replace(tmp, path)  # never leave half a clip for Gary to play


def speak(text, key, voice, model=DEFAULT_MODEL, opener=urllib.request.urlopen, tries=3):
    """One line -> raw 16-bit mono PCM at RATE."""
    model = os.environ.get("ELEVENLABS_MODEL") or model
    body = json.dumps({"text": text, "model_id": model,
                       "voice_settings": V3_SETTINGS if model.startswith("eleven_v3") else VOICE_SETTINGS}).encode("utf-8")
    req = urllib.request.Request(URL % (voice, RATE), data=body,
                                 headers={"xi-api-key": key, "Content-Type": "application/json"})
    for attempt in range(tries):
        try:
            with opener(req, timeout=30) as reply:
                return reply.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt + 1 < tries:
                time.sleep(2 * (attempt + 1))
                continue
            hints = {401: "the key was not accepted", 403: "the key may not use Text to Speech",
                     404: "there is no voice %s" % voice, 429: "too many requests, or no credits left"}
            raise SystemExit("ElevenLabs answered HTTP %d: %s" % (exc.code, hints.get(exc.code, "see elevenlabs.io/docs")))
        except OSError as exc:  # a dropped or slow connection: try again, then stop cleanly
            if attempt + 1 < tries:
                time.sleep(2 * (attempt + 1))
                continue
            raise SystemExit("Could not reach ElevenLabs (%s). Run it again: it skips the clips already made." % exc)
    raise SystemExit("ElevenLabs did not answer")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make Gary's spoken clips with ElevenLabs.")
    ap.add_argument("--sounds", default=os.path.join(HERE, "sounds"))
    ap.add_argument("--dry-run", action="store_true", help="print the lines, call nothing")
    ap.add_argument("--force", action="store_true", help="make clips that already exist again")
    ap.add_argument("--only", nargs="+", metavar="CLIP", help="only these clips, for example say_bottle")
    args = ap.parse_args(argv)

    todo = lines(read_labels())
    if args.only:
        unknown = [c for c in args.only if c not in todo]
        if unknown:
            raise SystemExit("No such clip: %s" % ", ".join(unknown))
        todo = {c: todo[c] for c in args.only}
    if not args.force:
        todo = {c: t for c, t in todo.items() if not os.path.exists(os.path.join(args.sounds, c + ".wav"))}

    model = os.environ.get("ELEVENLABS_MODEL") or DEFAULT_MODEL
    todo = {clip: performed(clip, text, model) for clip, text in todo.items()}
    if args.dry_run:
        for clip, text in todo.items():
            print("%-28s %s" % (clip, text))
        print("%d clips, %d characters. Dry run: nothing was made." % (len(todo), sum(map(len, todo.values()))))
        return

    load_env(os.path.join(HERE, ".env"))
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise SystemExit("Put ELEVENLABS_API_KEY=... in device/.env (it is ignored by Git), or export it.")
    voice = os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE
    os.makedirs(args.sounds, exist_ok=True)
    for n, (clip, text) in enumerate(todo.items(), 1):
        write_wav(os.path.join(args.sounds, clip + ".wav"), speak(text, key, voice))
        print("[%d/%d] %-26s %s" % (n, len(todo), clip, text))
    print("%d clips made in %s." % (len(todo), args.sounds))


if __name__ == "__main__":
    sys.exit(main())
