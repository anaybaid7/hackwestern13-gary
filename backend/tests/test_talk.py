"""Talking to Gary from the web page: POST /api/talk, with Gemini and ElevenLabs faked."""
import base64

import talk

SPEECH = b"\x10\x00" * 16000  # one second


def wav64(pcm=SPEECH, rate=16000):
    import io
    import wave
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return base64.b64encode(out.getvalue()).decode()


class FakeApp:
    api = "here"

    def __init__(self):
        self.chosen = []

    def text(self):
        return "The app right now: a kid."

    def choose(self, time_):
        self.chosen.append(time_)
        return {"id": "q1", "title": "Find a bench", "place": "Harris Park"}


def run(listening, wake=None, answer=None, pcm=SPEECH, app=None):
    return talk.turn(pcm, listening, (), None, app or FakeApp(), "g", "e",
                     wake=wake, answer=answer, speak=lambda text, key: b"\x00\x00" * 10)


def test_only_go_gary_wakes_him():
    assert run(False, wake=lambda *a, **k: (False, None)) == {"woke": False}
    alone = run(False, wake=lambda *a, **k: (True, None))
    assert alone == {"woke": True, "heard": "", "say": "", "listen": True}


def test_a_question_with_go_gary_is_answered_out_loud():
    reply = {"heard": "go gary what is that", "say": "A bench. Sit, I won't.", "do": None, "listen": False}
    out = run(False, wake=lambda *a, **k: (True, reply))
    assert out["say"] == "A bench. Sit, I won't." and out["listen"] is False
    assert base64.b64decode(out["audio"])[:4] == b"RIFF"


def test_while_listening_anything_said_is_answered_and_can_pick_a_quest():
    app = FakeApp()
    reply = {"heard": "a short one", "say": "Here you go.", "do": {"action": "choose_quest", "time": "short"},
             "listen": False}
    out = run(True, answer=lambda *a, **k: reply, app=app)
    assert app.chosen == ["short"] and "Find a bench" in out["say"]


def test_long_chatter_nearby_is_not_sent_to_gemini():
    def never(*a, **k):
        raise AssertionError("asked Gemini")
    assert run(False, wake=never, pcm=b"\x00\x00" * 16000 * 7) == {"woke": False}


def test_audio_must_be_a_short_16k_mono_wav():
    assert talk.pcm_of(wav64()) == SPEECH
    assert talk.pcm_of(wav64(rate=48000)) is None
    assert talk.pcm_of("not base64!") is None
    assert talk.pcm_of("A" * (talk.MAX_AUDIO + 4)) is None


def test_the_history_is_trimmed_to_four_pairs():
    sent = [["hi", "hello"]] * 6 + ["junk", ["x" * 900, "y"]]
    got = talk.history_of(sent)
    assert len(got) == 4 and got[-1] == ("x" * 300, "y")


def test_without_keys_talking_is_off(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client.get("/api/talk").json() == {"enabled": False}
    assert client.post("/api/talk", json={"audio": wav64()}).status_code == 503


def test_with_keys_a_turn_runs_and_bad_audio_is_refused(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "e")
    monkeypatch.setattr(talk.brain, "is_wake", lambda *a, **k: (False, None))
    assert client.get("/api/talk").json() == {"enabled": True}
    assert client.post("/api/talk", json={"audio": "nope"}).status_code == 422
    assert client.post("/api/talk", json={"audio": wav64(), "listening": False}).json() == {"woke": False}


def test_strict_mode_never_takes_the_next_voice_as_an_answer(monkeypatch):
    reply = {"heard": "go gary hi", "say": "Hi! Short or long?", "do": None, "listen": True}
    assert run(False, wake=lambda *a, **k: (True, reply))["listen"] is True
    monkeypatch.setenv("GARY_TALK_STRICT", "on")
    assert run(False, wake=lambda *a, **k: (True, reply))["listen"] is False
    assert run(False, wake=lambda *a, **k: (True, None))["listen"] is True, '"Go Gary" alone still waits for the question'


def test_a_question_the_browser_transcribed_is_answered_as_text(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "e")
    asked = []
    monkeypatch.setattr(talk.brain, "answer", lambda q, *a, **k: asked.append(q) or
                        {"heard": q, "say": "A goose. Loud, proud.", "do": None, "listen": False})
    monkeypatch.setattr(talk.brain, "tts", lambda text, key: b"\x00\x00" * 10)
    out = client.post("/api/talk", json={"text": "  what is   a goose? ", "listening": False}).json()
    assert asked == ["what is a goose?"] and out["say"] == "A goose. Loud, proud."
    assert talk.text_of("x" * 900) == "x" * 300 and talk.text_of("   ") is None and talk.text_of(5) is None
