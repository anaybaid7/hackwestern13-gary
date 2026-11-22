"""In range: the page says you were within 1 km of a quest's place, and only
then does a sniff finish that quest. No position ever reaches the backend."""
import rules
import app as backend
from conftest import post, quest, sniff, state_of


def visit(client, quest_id, **extra):
    return client.post("/api/visit", json=dict({"quest_id": quest_id}, **extra))


def test_a_quest_finished_in_range_counts_and_is_marked(client, clock):
    clock.set("2026-11-21T05:00:00Z")
    assert visit(client, "q-demo-bottle").json() == {"ok": True}
    clock.set("2026-11-21T05:21:00Z")
    out = post(client, sniff("bottle", ts="2026-11-21T05:20:00Z"), there=False)
    assert out["results"][0]["reaction"] == "quest_complete" and out["results"][0]["xp"] == 20
    state = state_of(client)
    assert state["journal"][0]["been_there"] is True
    tile = next(t for t in state["map"] if t["quest_id"] == "q-demo-bottle")
    assert tile["visited"] is True


def test_out_of_range_the_sniff_is_an_ordinary_find_and_the_quest_stays_open(client):
    out = post(client, sniff("bottle"), there=False)
    assert out["results"][0] == {"id": out["results"][0]["id"], "xp": rules.XP_NEW_INDOOR,
                                 "reaction": "new_discovery", "new": True, "quest_id": None}
    state = state_of(client)
    assert state["journal"][0]["been_there"] is False and state["journal"][0]["quest_id"] is None
    assert "q-demo-bottle" in [q["id"] for q in client.get("/api/quests").json()["quests"]]


def test_a_quest_with_no_position_completes_anywhere(client):
    client.post("/api/quests", json=quest("q-free", "dog", "Somewhere"))
    out = post(client, sniff("dog"), there=False)
    assert out["results"][0]["reaction"] == "quest_complete" and out["results"][0]["quest_id"] == "q-free"


def test_a_visit_to_another_quest_or_too_long_ago_does_not_count(client, clock):
    clock.set("2026-11-21T01:00:00Z")
    visit(client, "q-demo-bottle")             # over 2 hours before the sniff
    visit(client, "q-harris-bench")            # a different quest
    clock.set("2026-11-21T05:21:00Z")          # the backend never dates a sniff in the future
    out = post(client, sniff("bottle", ts="2026-11-21T05:20:00Z"), there=False)
    assert out["results"][0]["quest_id"] is None


def test_a_visit_reported_just_after_the_sniff_still_counts(client, clock):
    post(client, sniff("bottle", ts="2026-11-21T05:20:00Z"), there=False)
    clock.set("2026-11-21T05:40:00Z")          # 20 minutes later: the page reports late
    visit(client, "q-demo-bottle")
    entry = state_of(client)["journal"][0]
    assert entry["quest_id"] == "q-demo-bottle" and entry["xp"] == 20 and entry["been_there"] is True


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


def test_the_latest_miss_is_in_the_state_so_the_page_can_say_move_closer(client):
    assert state_of(client)["last_miss"] is None
    post(client, {"id": "m-1", "ts": "2026-11-21T05:20:00Z", "type": "miss", "friend": False})
    assert state_of(client)["last_miss"] == {"id": "m-1", "ts": "2026-11-21T05:20:00Z"}
