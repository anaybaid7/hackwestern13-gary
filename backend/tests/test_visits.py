"""Been there: the page says you were at a quest's place, and finishing that
quest near then earns a bonus. No position ever reaches the backend."""
import rules
import app as backend
from conftest import post, quest, sniff, state_of


def visit(client, quest_id, **extra):
    return client.post("/api/visit", json=dict({"quest_id": quest_id}, **extra))


def test_a_quest_finished_after_a_visit_earns_the_bonus(client, clock):
    clock.set("2026-11-21T05:00:00Z")
    assert visit(client, "q-demo-bottle").json() == {"ok": True}
    clock.set("2026-11-21T05:21:00Z")
    out = post(client, sniff("bottle", ts="2026-11-21T05:20:00Z"))
    assert out["results"][0]["xp"] == 20 + rules.XP_BEEN_THERE
    state = state_of(client)
    assert state["journal"][0]["been_there"] is True
    tile = next(t for t in state["map"] if t["quest_id"] == "q-demo-bottle")
    assert tile["visited"] is True


def test_no_visit_means_no_bonus_and_the_quest_still_counts(client):
    out = post(client, sniff("bottle"))
    assert out["results"][0] == {"id": out["results"][0]["id"], "xp": 20, "reaction": "quest_complete",
                                 "new": True, "quest_id": "q-demo-bottle"}
    assert state_of(client)["journal"][0]["been_there"] is False


def test_a_visit_to_another_quest_or_too_long_ago_does_not_count(client, clock):
    clock.set("2026-11-21T01:00:00Z")
    visit(client, "q-demo-bottle")             # over 2 hours before the sniff
    visit(client, "q-harris-bench")            # a different quest
    clock.set("2026-11-21T05:21:00Z")          # the backend never dates a sniff in the future
    out = post(client, sniff("bottle", ts="2026-11-21T05:20:00Z"))
    assert out["results"][0]["xp"] == 20


def test_a_visit_reported_just_after_the_sniff_still_counts(client, clock):
    post(client, sniff("bottle", ts="2026-11-21T05:20:00Z"))
    clock.set("2026-11-21T05:40:00Z")          # 20 minutes later
    visit(client, "q-demo-bottle")
    assert state_of(client)["journal"][0]["xp"] == 20 + rules.XP_BEEN_THERE


def test_the_bonus_is_not_doubled_by_a_friend(client, clock):
    clock.set("2026-11-21T05:10:00Z")
    visit(client, "q-demo-backpack")
    clock.set("2026-11-21T05:21:00Z")
    out = post(client, sniff("backpack", friend=True, ts="2026-11-21T05:20:00Z"))
    assert out["results"][0]["xp"] == 20 * rules.FRIEND_MULTIPLIER + rules.XP_BEEN_THERE


def test_a_visit_keeps_only_the_quest_id_and_refuses_an_unknown_quest(client):
    assert visit(client, "q-nowhere").status_code == 422
    visit(client, "q-demo-bottle", lat=42.98, lng=-81.25, accuracy=12)
    kept = [ev for ev in backend.store.events() if ev["type"] == "visit"]
    assert len(kept) == 1 and set(kept[0]) == {"id", "ts", "type", "quest_id"}


def test_a_quest_keeps_real_coordinates_and_drops_anything_else(client):
    client.post("/api/quests", json={"quests": [
        quest("q-a", "bench", "Kilally Meadows", lat=42.9849, lng=-81.2585),
        quest("q-b", "bench", "Gibbons Park", lat=420, lng="east"),
        quest("q-c", "bench", "Springbank Park", lat=True, lng=None),
    ]})
    by_id = {q["id"]: q for q in client.get("/api/quests").json()["quests"]}
    assert (by_id["q-a"]["lat"], by_id["q-a"]["lng"]) == (42.9849, -81.2585)
    assert (by_id["q-b"]["lat"], by_id["q-b"]["lng"]) == (None, None)
    assert (by_id["q-c"]["lat"], by_id["q-c"]["lng"]) == (None, None)
    tile = next(t for t in state_of(client)["map"] if t["quest_id"] == "q-a")
    assert (tile["lat"], tile["lng"], tile["visited"]) == (42.9849, -81.2585, False)


def test_tidbits_are_kept_as_plain_lines_three_at_most(client):
    client.post("/api/quests", json={"quests": [
        quest("q-t", "tree", "Sifton Bog", tidbits=["A rare peat bog.", "Line\nbreak", 7, "", "three", "four"]),
        quest("q-n", "tree", "Warbler Woods", tidbits="not a list"),
    ]})
    by_id = {q["id"]: q for q in client.get("/api/quests").json()["quests"]}
    assert by_id["q-t"]["tidbits"] == ["A rare peat bog.", "Line break", "three"]
    assert by_id["q-n"]["tidbits"] == []
