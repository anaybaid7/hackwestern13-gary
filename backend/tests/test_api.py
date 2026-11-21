"""The API against the contract. Run from backend/:  pytest"""
import datetime as dt

import app as backend
import rules
from conftest import EXAMPLES, PINNED_NOW, example, post, sniff


def test_fresh_backend_is_seeded_and_gary_naps(client):
    state = client.get("/api/state").json()
    assert state["gary"] == {"stage": "kid", "stage_index": 0, "xp": 0, "stage_xp": 0,
                             "next_stage_xp": 60, "napping": True, "welcome_back": False}
    assert state["quests_open"] == 3
    assert state["quest"]["id"] == "q-demo-bottle"
    assert [t["place"] for t in state["map"]] == [q["place"] for q in example("quests.json")["quests"]]
    assert not any(t["cleared"] for t in state["map"])


def test_example_events_produce_the_example_state(client):
    """The contract's own files agree with each other."""
    out = post(client, example("event.mood.json"), example("event.discovery.json"), example("event.miss.json"))
    assert out["accepted"] == 3 and out["duplicates"] == 0
    assert client.get("/api/state").json() == example("state.json")


def test_discovery_changes_xp_journal_and_map(client):
    out = post(client, example("event.discovery.json"))
    result = out["results"][0]
    assert result == {"id": example("event.discovery.json")["id"], "xp": 80,
                      "reaction": "quest_complete", "new": True, "quest_id": "q-harris-bench"}
    state = client.get("/api/state").json()
    assert state["gary"]["xp"] == 80 and state["gary"]["stage"] == "scrambler"
    assert state["journal"][0]["label"] == "bench" and state["journal"][0]["xp"] == 80
    assert state["guide"] == {"total": 79, "found": ["bench"]}
    cleared = [t["place"] for t in state["map"] if t["cleared"]]
    assert cleared == ["Harris Park"]


def test_same_event_twice_counts_once(client):
    ev = example("event.discovery.json")
    post(client, ev)
    again = post(client, ev)
    assert again["accepted"] == 0 and again["duplicates"] == 1
    assert client.get("/api/state").json()["gary"]["xp"] == 80


def test_outdoor_finds_earn_more_than_desk_items(client):
    out = post(client, sniff("dog"), sniff("cup"), sniff("dog"))
    assert [r["xp"] for r in out["results"]] == [rules.XP_NEW_OUTDOOR, rules.XP_NEW_INDOOR, rules.XP_REPEAT]
    assert [r["reaction"] for r in out["results"]] == ["new_discovery", "new_discovery", "seen_before"]


def test_friend_in_frame_doubles_the_sniff(client):
    out = post(client, sniff("dog", friend=True))
    assert out["results"][0]["xp"] == 2 * rules.XP_NEW_OUTDOOR
    herd = client.get("/api/state").json()["herd"]
    assert herd["shared"] == 1 and herd["badges"] == ["first-herd"]


def test_herd_quest_needs_a_friend(client):
    alone = post(client, sniff("backpack"))
    assert alone["results"][0]["quest_id"] is None
    together = post(client, sniff("backpack", friend=True))
    assert together["results"][0] | {"id": 0} == {"id": 0, "xp": 40, "reaction": "quest_complete",
                                                  "new": False, "quest_id": "q-demo-backpack"}


def test_demo_two_table_quests_reach_the_second_stage(client):
    post(client, sniff("bottle"), sniff("backpack", friend=True))
    gary = client.get("/api/state").json()["gary"]
    assert gary["xp"] == 60 and gary["stage"] == "scrambler"


def test_every_stage_is_reachable_solo(client):
    labels = [name for name, out in backend.OUTDOOR.items() if out]
    post(client, *[sniff(name) for name in labels])              # 33 outdoor finds, alone
    post(client, *[sniff(labels[0]) for _ in range(40)])          # and plenty of repeats
    assert client.get("/api/state").json()["gary"]["stage"] == "summit-elder"


def test_welcome_back_bonus_and_no_penalty(client):
    post(client, sniff("dog", ts="2026-11-20T05:00:00Z"))
    before = client.get("/api/state").json()["gary"]["xp"]
    out = post(client, sniff("dog", ts="2026-11-21T05:21:00Z"))   # a day later
    assert out["results"][0]["xp"] == rules.XP_REPEAT + rules.XP_WELCOME_BACK
    gary = client.get("/api/state").json()["gary"]
    assert gary["xp"] > before and gary["welcome_back"] is True and gary["napping"] is False


def test_gary_naps_when_it_has_been_quiet(client, monkeypatch):
    post(client, sniff("dog"))
    monkeypatch.setattr(backend, "now", lambda: PINNED_NOW + dt.timedelta(days=2))
    gary = client.get("/api/state").json()["gary"]
    assert gary["napping"] is True and gary["xp"] == rules.XP_NEW_OUTDOOR   # nothing was taken away


def test_quests_filter_and_finished_ones_drop_out(client):
    assert [q["id"] for q in client.get("/api/quests?time=long").json()["quests"]] == ["q-harris-bench"]
    post(client, sniff("bottle"))
    open_ids = [q["id"] for q in client.get("/api/quests").json()["quests"]]
    assert open_ids == ["q-demo-backpack", "q-harris-bench"]
    assert len(client.get("/api/quests?all=true").json()["quests"]) == 3


def test_scout_can_add_quests_and_bad_targets_are_refused(client):
    good = dict(example("quest.json"), id="q-new", place="Gibbons Park", target="dog", title="Find a dog")
    bad = dict(good, id="q-bad", target="mushroom")
    out = client.post("/api/quests", json={"quests": [good, bad]}).json()
    assert out["accepted"] == ["q-new"]
    assert out["rejected"][0]["id"] == "q-bad" and "mushroom" in out["rejected"][0]["why"]
    assert "Gibbons Park" in [t["place"] for t in client.get("/api/state").json()["map"]]


def test_scout_key_is_enforced_when_set(client, monkeypatch):
    monkeypatch.setenv("SCOUT_KEY", "s3cret")
    quest = dict(example("quest.json"), id="q-key")
    assert client.post("/api/quests", json=quest).status_code == 401
    assert client.post("/api/quests", json=quest, headers={"X-Scout-Key": "s3cret"}).status_code == 200


def test_mood_is_private(client):
    post(client, example("event.mood.json"))
    client.post("/api/mood", json={"phase": "after", "value": 4})
    assert "mood" not in str(client.get("/api/state").json()).lower()
    wellness = client.get("/api/wellness").json()
    assert wellness["private"] is True and [c["value"] for c in wellness["checkins"]] == [3, 4]
    assert client.post("/api/mood", json={"phase": "after", "value": 9}).status_code == 422


def test_replay_gives_the_same_state(client):
    events = [sniff("dog"), sniff("bottle"), sniff("backpack", friend=True), sniff("dog")]
    post(client, *events)
    first = client.get("/api/state").json()
    client.post("/api/dev/reset")
    post(client, *events)
    assert client.get("/api/state").json() == first


def test_bad_bodies_are_refused(client):
    assert client.post("/api/events", json={"events": [{"type": "discovery"}]}).status_code == 422
    assert client.post("/api/events", json={"events": [{"id": "x", "type": "discovery"}]}).status_code == 422
    assert client.post("/api/events", json="nope").status_code == 422
    assert EXAMPLES.exists()
