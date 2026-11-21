"""Private mood (#20): check-ins in, wellness view out, and nothing leaks."""
import json

import rules
from conftest import example, post, sniff, state_of

UTC = "Z"


def mood(client, phase, value):
    reply = client.post("/api/mood", json={"phase": phase, "value": value})
    assert reply.status_code == 200, reply.text


def wellness(client):
    return client.get("/api/wellness").json()


def test_a_fresh_wellness_view_is_empty_and_says_check_ins_are_optional(client):
    w = wellness(client)
    assert w["private"] is True
    assert w["checkins"] == [] and w["pairs"] == [] and w["outdoor"] == []
    assert w["outdoor_minutes"] == 0 and (w["finds"], w["solo"], w["shared"]) == (0, 0, 0)
    assert w["summary"] == "No before-and-after check-ins yet. They are always optional."


def test_the_contract_example_is_what_the_backend_returns(client, clock):
    post(client, example("event.mood.json"), example("event.discovery.json"), example("event.miss.json"))
    clock.set("2026-11-21T05:50:00Z")
    mood(client, "after", 4)
    assert wellness(client) == example("wellness.json")


def test_before_and_after_are_paired_within_one_outing(client, clock):
    clock.set("2026-11-21T14:00:00Z")
    mood(client, "before", 2)
    clock.set("2026-11-21T14:01:00Z")
    mood(client, "before", 3)              # changed their mind: the newer "before" counts
    clock.set("2026-11-21T15:00:00Z")
    mood(client, "after", 5)
    clock.set("2026-11-21T15:30:00Z")
    mood(client, "after", 1)               # an "after" with no "before": kept, not paired
    clock.set("2026-11-22T02:00:00Z")
    mood(client, "before", 4)
    clock.set("2026-11-23T02:00:00Z")
    mood(client, "after", 4)               # a day later: not the same outing
    w = wellness(client)
    assert [c["value"] for c in w["checkins"]] == [2, 3, 5, 1, 4, 4]
    assert all(c["source"] == "web" for c in w["checkins"])
    assert w["pairs"] == [{"day": "2026-11-21", "before": 3, "after": 5, "change": 2,
                           "before_ts": "2026-11-21T14:01:00Z", "after_ts": "2026-11-21T15:00:00Z", "minutes": 59}]


def test_a_mood_tap_on_the_device_counts_too(client, clock):
    clock.set("2026-11-21T16:00:00Z")
    out = post(client, {"id": "gary-01-1-m1", "ts": "2026-11-21T15:00:00Z", "type": "mood", "device": "gary-01",
                        "phase": "before", "value": 2})
    assert out["accepted"] == 1 and out["results"][0]["reaction"] == "mood" and out["results"][0]["xp"] == 0
    mood(client, "after", 3)
    w = wellness(client)
    assert [(c["phase"], c["value"], c["source"]) for c in w["checkins"]] == [("before", 2, "device"), ("after", 3, "web")]
    assert w["pairs"][0]["change"] == 1
    # the same device line again is not a second check-in
    post(client, {"id": "gary-01-1-m1", "ts": "2026-11-21T15:00:00Z", "type": "mood", "phase": "before", "value": 2})
    assert len(wellness(client)["checkins"]) == 2


def test_bad_check_ins_are_refused(client):
    for body in ({"phase": "during", "value": 3}, {"phase": "before", "value": 0}, {"phase": "after", "value": 6},
                 {"phase": "after", "value": "4"}, {"phase": "after", "value": 2.5}, {"phase": "after", "value": True},
                 {"value": 3}, {}):
        assert client.post("/api/mood", json=body).status_code == 422, body
    bad = {"id": "m-bad", "type": "mood", "phase": "before", "value": 9}
    assert client.post("/api/events", json={"events": [bad]}).status_code == 422
    assert wellness(client)["checkins"] == []


def test_mood_never_appears_in_the_state_or_in_any_shared_reply(client, clock):
    clock.set("2026-11-21T15:00:00Z")
    mood(client, "before", 1)
    post(client, {"id": "m-1", "ts": "2026-11-21T15:00:00Z", "type": "mood", "phase": "before", "value": 2},
         sniff("bench", friend=True, ts="2026-11-21T15:00:00Z"))
    clock.set("2026-11-21T15:40:00Z")
    mood(client, "after", 5)
    for path in ("/api/state", "/api/quests", "/api/quests?all=true", "/api/health"):
        text = json.dumps(client.get(path).json()).lower()
        for word in ("mood", "phase", "checkin", "wellness", "before", "after"):
            assert word not in text, "%s leaks %r" % (path, word)
    chosen = client.post("/api/quest/choose", json={"time": "short"}).json()
    assert "mood" not in json.dumps(chosen).lower()
    # the reply to the device's own upload says nothing about the mood either
    out = post(client, {"id": "m-2", "ts": "2026-11-21T15:41:00Z", "type": "mood", "phase": "after", "value": 4})
    assert out["results"] == [{"id": "m-2", "xp": 0, "reaction": "mood", "new": False, "quest_id": None}]


def test_outdoor_minutes_come_from_ten_minute_blocks_with_an_outdoor_find(client, clock):
    clock.set("2026-11-22T20:00:00Z")
    post(client,
         sniff("bench", ts="2026-11-21T15:01:00Z"),     # block 15:00
         sniff("dog", ts="2026-11-21T15:08:00Z"),       # the same block
         sniff("bird", ts="2026-11-21T15:12:00Z"),      # block 15:10
         sniff("cup", ts="2026-11-21T15:25:00Z"),       # indoor: does not count
         sniff("dog", ts="2026-11-21T15:45:00Z"),       # block 15:40. A repeat still means being outside
         sniff("kite", friend=True, ts="2026-11-22T03:30:00Z"),   # 10:30 pm Saturday in London, Ontario: still Saturday
         sniff("bicycle", ts="2026-11-22T15:00:00Z"))   # Sunday
    w = wellness(client)
    assert w["outdoor"] == [{"day": "2026-11-21", "minutes": 40}, {"day": "2026-11-22", "minutes": 10}]
    assert w["outdoor_minutes"] == 50
    assert "estimate" in w["outdoor_note"].lower()
    assert (w["finds"], w["solo"], w["shared"]) == (7, 6, 1)
    # the store's own query and the plain Python sum agree
    import app as backend
    assert rules.outdoor_by_day(backend.store.events(), backend.OUTDOOR, backend.TZ) == w["outdoor"]


def pairs(*changes):
    return [{"change": c} for c in changes]


def test_the_summary_reports_what_was_said_and_never_claims_a_cause():
    assert rules.mood_summary(pairs(1)) == "You reported feeling better after your outing."
    assert rules.mood_summary(pairs(0)) == "You reported feeling about the same after your outing."
    assert rules.mood_summary(pairs(-2)) == "You reported feeling lower after your outing."
    assert rules.mood_summary(pairs(1, 2, 0)) == "You reported feeling better after 2 of 3 outings."
    assert rules.mood_summary(pairs(0, 0)) == "You reported feeling about the same after 2 outings."
    assert rules.mood_summary(pairs(-1, 0, -1)) == "You reported feeling lower after 2 of 3 outings."
    for case in (pairs(), pairs(1), pairs(-1), pairs(1, 1, -1), pairs(0, 0), pairs(-1, -1)):
        text = rules.mood_summary(case).lower()
        assert text.startswith(("you reported", "no before-and-after"))
        for claim in ("because", "fixed", "improved", "caused", "made you", "boost", "cure", "thanks to", "should"):
            assert claim not in text, text
