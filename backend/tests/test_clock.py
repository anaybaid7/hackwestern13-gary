"""Time: a device with a wrong clock, naps in demo mode, the local day."""
import app as backend
import rules
from conftest import post, sniff, state_of


def test_a_device_with_a_wrong_clock_is_put_right(client, clock):
    """A Pi that boots with no network may think it is 2025. sync.py sends what
    its clock reads at upload time; the difference from ours is the error."""
    clock.set("2026-11-21T15:00:00Z")
    # The Pi's clock is 400 days behind. The sniff was 20 minutes before the upload.
    out = post(client, sniff("bench", ts="2025-10-17T14:40:00Z"), there=False, sent_at="2025-10-17T15:00:00.250Z")
    assert out["accepted"] == 1
    state = state_of(client)
    entry = state["journal"][0]
    assert entry["ts"] == "2026-11-21T14:39:59Z" or entry["ts"] == "2026-11-21T14:40:00Z", entry["ts"]
    assert state["gary"]["napping"] is False, "the sniff was 20 minutes ago, so Gary is awake"
    assert backend.store.events()[0]["device_ts"] == "2025-10-17T14:40:00Z", "what the device wrote is kept"
    # it counts for this week's wellness day, not for a day a year ago
    assert client.get("/api/wellness").json()["outdoor"] == [{"day": "2026-11-21", "minutes": 10}]


def test_a_clock_that_is_right_is_left_alone(client, clock):
    clock.set("2026-11-21T15:00:00Z")
    post(client, sniff("bench", ts="2026-11-21T14:40:00Z"), there=False, sent_at="2026-11-21T14:59:59.400Z")   # 0.6 s apart
    post(client, sniff("dog", ts="2026-11-20T09:00:00Z"), there=False)            # no sent_at: an offline day-old sniff
    events = backend.store.events()
    assert [e["ts"] for e in events] == ["2026-11-21T14:40:00Z", "2026-11-20T09:00:00Z"]
    assert all("device_ts" not in e for e in events)


def test_an_event_is_never_dated_in_the_future(client, clock):
    clock.set("2026-11-21T15:00:00Z")
    post(client, sniff("bench", ts="2031-01-01T00:00:00Z"),          # a clock far ahead
         dict(sniff("dog"), ts="not a time"), dict(sniff("bird"), ts=None), there=False)
    events = backend.store.events()
    assert [e["ts"] for e in events] == ["2026-11-21T15:00:00Z"] * 3
    assert events[0]["device_ts"] == "2031-01-01T00:00:00Z" and events[1]["device_ts"] == "not a time"
    assert state_of(client)["gary"]["napping"] is False


def test_demo_mode_naps_after_seconds_and_welcomes_back(client, clock, monkeypatch):
    monkeypatch.setenv("GARY_NAP_SECONDS", "60")
    clock.set("2026-11-21T15:00:00Z")
    post(client, sniff("dog", ts="2026-11-21T15:00:00Z"), there=False)
    clock.forward(seconds=59)
    assert state_of(client)["gary"]["napping"] is False
    clock.forward(seconds=2)
    gary = state_of(client)["gary"]
    assert gary["napping"] is True and gary["xp"] == rules.XP_NEW_OUTDOOR, "a nap takes nothing away"
    out = post(client, sniff("dog", ts="2026-11-21T15:01:01Z"), there=False)
    assert out["results"][0]["xp"] == rules.XP_REPEAT + rules.XP_WELCOME_BACK
    gary = state_of(client)["gary"]
    assert gary["welcome_back"] is True and gary["napping"] is False


def test_a_quest_with_no_day_gets_the_local_day(client, clock):
    clock.set("2026-11-22T03:00:00Z")          # 10 pm Saturday in London, Ontario
    quest = {"id": "q-late", "title": "Find a dog", "place": "Gibbons Park", "time": "short", "target": "dog", "xp": 20}
    assert client.post("/api/quests", json=quest).json()["accepted"] == ["q-late"]
    stored = [q for q in client.get("/api/quests").json()["quests"] if q["id"] == "q-late"][0]
    assert stored["day"] == "2026-11-21"
    assert backend.TZ_NAME == "America/Toronto"


def test_only_known_event_types_are_taken_and_a_batch_counts_each_id_once(client):
    assert client.post("/api/events", json={"events": [{"id": "x", "type": "choice", "time": "long"}]}).status_code == 422
    assert client.post("/api/events", json={"events": [{"id": "x", "type": "teleport"}]}).status_code == 422
    one = sniff("dog")
    out = post(client, one, dict(one), sniff("cup"))
    assert out["accepted"] == 2 and out["duplicates"] == 1
    assert len(out["results"]) == 3 and out["results"][0] == out["results"][1]
    assert state_of(client)["gary"]["xp"] == rules.XP_NEW_OUTDOOR + rules.XP_NEW_INDOOR
