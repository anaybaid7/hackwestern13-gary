"""Talk to Gary from the web page: one thing said in, Gary's spoken reply out.

The page listens (the browser has the microphone and the speaker the Pi
lacks), hears "Go Gary" itself, and sends only the question here. The brain
is device/gary_talk.py, so the page and the laptop say the same things:
Gemini answers with what he sees and what the app says, ElevenLabs speaks it.
The keys stay on this server. Nothing said is stored or logged.

The page keeps the conversation (the last few lines) and sends it each
time, so this side keeps no state.
"""
import base64
import binascii
import os
import sys
from pathlib import Path

MAX_AUDIO = 600_000  # base64 characters: about 9 s of 16 kHz speech
TALK_DIR = Path(os.environ.get("GARY_TALK_DIR") or Path(__file__).resolve().parent.parent / "device")

try:
    sys.path.insert(0, str(TALK_DIR))
    import gary_talk as brain
except ImportError:  # gary_talk.py is not deployed beside this backend
    brain = None


def load_keys(environ=os.environ):
    """The keys gary_talk.py uses, from its own .env files, unless already set."""
    if brain and not environ.get("GARY_NO_ENV_FILE"):
        brain.load_env(str(TALK_DIR / ".env"))
        brain.load_env(str(TALK_DIR.parent / "scout" / ".env"))  # the laptop keeps the Gemini key there


def keys(environ=os.environ):
    return environ.get("GEMINI_API_KEY"), environ.get("ELEVENLABS_API_KEY")


def enabled(environ=os.environ):
    return bool(brain) and all(keys(environ))


class App:
    """The app, as act() in gary_talk.py uses it, but in this process."""
    api = "here"

    def __init__(self, state, choose, post_quest, things):
        self.state, self._choose, self._post, self.things = state, choose, post_quest, things

    def text(self):
        return brain.app_context(self.state, self.things)

    def choose(self, time_):
        return self._choose(time_)

    def create(self, target, place, time_, herd=False):
        quest = brain.make_quest(target, place, time_, herd, self.things)
        why = self._post(quest)
        if why:
            raise brain.TalkError("the app refused the quest: %s" % why)
        return quest


def history_of(raw):
    """The page's conversation: up to four [what they said, what Gary said]."""
    out = []
    for pair in raw if isinstance(raw, list) else []:
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            out.append((str(pair[0])[:300], str(pair[1])[:400]))
    return tuple(out[-4:])


def text_of(text):
    """A question the browser transcribed itself, one line, or None."""
    if not isinstance(text, str):
        return None
    return " ".join(text.split())[:300] or None


def pcm_of(audio):
    """A base64 WAV of 16 kHz mono 16-bit speech -> its PCM, or None."""
    if not isinstance(audio, str) or not audio or len(audio) > MAX_AUDIO:
        return None
    try:
        raw = base64.b64decode(audio, validate=True)
    except (binascii.Error, ValueError):
        return None
    import io
    import wave
    try:
        with wave.open(io.BytesIO(raw)) as w:
            if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, brain.RATE):
                return None
            return w.readframes(w.getnframes())
    except (wave.Error, EOFError):
        return None


def turn(question, history, seeing, app, gemini_key, eleven_key, answer=None, speak=None):
    """The question (PCM, or text) -> {"say", "heard", "listen", "audio": Gary's
    reply as a base64 WAV}. The page heard "Go Gary" itself before sending it."""
    answer, speak = answer or brain.answer, speak or brain.tts
    reply = brain.as_reply(answer(question, gemini_key, seeing, app_text=app.text(), history=history))
    if not reply["say"] and not reply.get("do"):
        raise brain.TalkError("Gemini gave no answer")
    said = brain.act(reply, app, say=lambda *_: None)
    audio = base64.b64encode(brain.as_wav(speak(said, eleven_key))).decode("ascii")
    # GARY_TALK_STRICT=on (a loud room): even the answer to Gary's own question needs "Go Gary"
    listen = bool(reply.get("listen")) and os.environ.get("GARY_TALK_STRICT") != "on"
    return {"heard": reply.get("heard") or "", "say": said, "listen": listen, "audio": audio}
