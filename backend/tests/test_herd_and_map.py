"""The fog-of-war map (#18) and Herd Mode with the Herd Cup (#19)."""
import rules
from conftest import post, quest, sniff, state_of


def test_a_tile_is_a_real_place_and_remembers_what_was_found(client):
    state = state_of(client)
    assert [t["place"] for t in state["map"]] == ["Hack Western, your table", "Hack Western, the next table", "Harris Park"]
    assert all(t["cleared"] is False and t["cleared_at"] is None and t["finds"] == [] for t in state["map"])

    post(client, sniff("bench", friend=True, ts="2026-11-21T05:20:00Z"))
    tile = state_of(client)["map"][2]
    assert tile == {"place": "Harris Park", "quest_id": "q-harris-bench", "cleared": True,
                    "cleared_at": "2026-11-21T05:20:00Z",
                    "finds": [{"label": "bench", "ts": "2026-11-21T05:20:00Z", "friend": True,
                               "quest_id": "q-harris-bench"}],
                    "lat": 42.9862, "lng": -81.2563, "visited": True}


def test_free_sniffs_fill_the_field_guide_but_clear_no_tile(client):
    post(client, sniff("dog"), sniff("bird"), sniff("cup"))
    state = state_of(client)
    assert not any(t["cleared"] for t in state["map"])
    assert state["guide"] == {"total": 90, "found": ["dog", "bird", "cup"]}
    assert all(entry["place"] is None for entry in state["journal"])


def test_two_spellings_of_one_place_are_one_tile(client):
    client.post("/api/quests", json={"quests": [quest("q-1", "dog", "Gibbons Park"),
                                               quest("q-2", "bird", "  gibbons   PARK ")]})
    places = [t["place"] for t in state_of(client)["map"]]
    assert places.count("Gibbons Park") == 1 and len(places) == 4
    post(client, sniff("bird"))                      # the second quest at that place
    tile = [t for t in state_of(client)["map"] if t["place"] == "Gibbons Park"][0]
    assert tile["cleared"] and tile["quest_id"] == "q-1" and tile["finds"][0]["quest_id"] == "q-2"


def test_the_map_keeps_the_newest_25_places_in_a_fixed_order(client):
    client.post("/api/quests", json={"quests": [quest("q-%02d" % i, "dog", "Place %02d" % i) for i in range(30)]})
    first = [t["place"] for t in state_of(client)["map"]]
    assert len(first) == rules.MAP_TILES == 25
    assert first[0] == "Place 05" and first[-1] == "Place 29", "the seed places and the oldest five have dropped off"
    assert [t["place"] for t in state_of(client)["map"]] == first, "the same on every read"


# --- Herd Mode ----------------------------------------------------------------
def test_a_fresh_herd_is_ranked_but_never_last(client):
    cup = state_of(client)["herd"]["cup"]
    assert cup["week"] == "2026-W47" and cup["demo"] is True
    assert cup["herds"] == 6 and cup["rank"] == 5, "a tie at zero goes to you, so there is always a herd below"
    assert [row["herd"] for row in cup["table"]] == ["Cliff Hangers", "The Bleat Goes On", "Summit Else", "Your herd"]
    assert cup["table"][-1] == {"herd": "Your herd", "score": 0, "quests": 0, "places": 0, "you": True}
    assert cup["ahead"] == {"herd": "Kid You Not", "score": 1, "gap": 1}
    assert cup["rank"] < cup["herds"], "last place is never shown"


def test_the_cup_counts_what_the_herd_did_together(client):
    # a free find with a friend: double XP and a badge, but no cup points
    post(client, sniff("dog", friend=True))
    herd = state_of(client)["herd"]
    assert herd["shared"] == 1 and herd["badges"] == ["first-herd"]
    assert herd["cup"]["rank"] == 5 and herd["cup"]["table"][-1]["score"] == 0

    # a quest alone: nothing for the herd
    post(client, sniff("bottle"))
    assert state_of(client)["herd"]["cup"]["table"][-1]["score"] == 0

    # a quest finished together, at a place not yet uncovered: one for the quest, one for the place
    post(client, sniff("backpack", friend=True))
    herd = state_of(client)["herd"]
    assert herd["badges"] == ["first-herd", "herd-quest"]
    cup = herd["cup"]
    assert cup["rank"] == 3, "passes Kid You Not, and a tie with Summit Else goes to you"
    assert cup["table"] == [{"herd": "Cliff Hangers", "score": 6}, {"herd": "The Bleat Goes On", "score": 4},
                            {"herd": "Your herd", "score": 2, "quests": 1, "places": 1, "you": True}]
    assert cup["ahead"] == {"herd": "The Bleat Goes On", "score": 4, "gap": 2}


def test_the_cup_can_be_won_and_shows_only_herds(client):
    client.post("/api/quests", json={"quests": [quest("q-%d" % i, "dog", "Park %d" % i) for i in range(3)]})
    post(client, sniff("backpack", friend=True), sniff("bench", friend=True),
         *[sniff("dog", friend=True) for _ in range(3)])
    herd = state_of(client)["herd"]
    cup = herd["cup"]
    assert cup["rank"] == 1 and cup["ahead"] is None
    assert cup["table"][0] == {"herd": "Your herd", "score": 10, "quests": 5, "places": 5, "you": True}
    assert len(cup["table"]) == 3
    assert herd["badges"] == ["first-herd", "herd-quest", "herd-of-five", "trail-mates"]
    # Herds are ranked. People never are: no row is a person, and nothing ranks the player alone.
    assert all(set(row) <= {"herd", "score", "quests", "places", "you"} for row in cup["table"])
    assert "leaderboard" not in str(herd).lower() and "players" not in str(herd).lower()


def test_the_cup_starts_again_every_monday_and_nothing_is_taken_away(client, clock):
    post(client, sniff("backpack", friend=True, ts="2026-11-21T05:20:00Z"))     # Saturday, week 47
    before = state_of(client)
    assert before["herd"]["cup"]["table"][-1]["score"] == 2

    clock.set("2026-11-23T15:00:00Z")                                          # Monday morning in London, Ontario
    after = state_of(client)
    assert after["herd"]["cup"]["week"] == "2026-W48"
    assert after["herd"]["cup"]["table"][-1]["score"] == 0, "a new week, a clean table"
    # ...but everything earned is kept
    assert after["gary"]["xp"] == before["gary"]["xp"]
    assert after["herd"]["badges"] == before["herd"]["badges"] and after["herd"]["shared"] == 1
    assert [t["cleared"] for t in after["map"]] == [t["cleared"] for t in before["map"]]


def test_weeks_turn_over_at_local_midnight_not_utc(client, clock):
    # Sunday 22 Nov, 9 pm in London, Ontario is already Monday in UTC. It is still week 47 here.
    clock.set("2026-11-23T02:00:00Z")
    post(client, sniff("backpack", friend=True, ts="2026-11-23T01:55:00Z"))
    cup = state_of(client)["herd"]["cup"]
    assert cup["week"] == "2026-W47" and cup["table"][-1]["score"] == 2
