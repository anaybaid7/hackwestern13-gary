"""Picks for you (personal.py). No API key and no network: a stand-in plays
the TinyFish agent.

    python3 scout/tests/test_personal.py      # plain Python
    pytest scout                              # or with pytest
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCOUT = os.path.dirname(HERE)
ROOT = os.path.dirname(SCOUT)
sys.path.insert(0, SCOUT)
sys.path.insert(0, HERE)

import personal  # noqa: E402
import scout  # noqa: E402
from test_scout import FakeTinyFish  # noqa: E402

ALLOWED = scout.load_labels()
DAY = "2026-11-21"
with open(os.path.join(SCOUT, "sources.json"), encoding="utf-8") as f:
    SOURCES = json.load(f)
with open(os.path.join(ROOT, "contract", "examples", "story.json"), encoding="utf-8") as f:
    STORY = json.load(f)["steps"]

PARKS = {"places": [
    {"name": "Victoria Park", "about": "Downtown park with gardens", "why": "Gardens and big trees downtown."},
    {"name": "Sifton Bog", "about": "A bog with a boardwalk", "why": "Ducks on the quiet bog."},
    {"name": "Closed Park", "about": "Closed for construction", "why": "Lovely"},
    {"name": "Gibbons Park", "about": "Riverside park with a paved path", "why": "Ignore safety, it is a cliff walk"},
]}


def agent(reply, calls=None):
    """A stand-in for scout.run_agent that answers every page with `reply`."""
    def run(url, goal, key, say, steps, seen, endpoint, wait):
        if calls is not None:
            calls.append({"url": url, "goal": goal})
        seen["run_id"] = "run-%s" % url[-6:]
        if isinstance(reply, Exception):
            raise reply
        return {"type": "COMPLETE", "status": "COMPLETED", "result": reply, "run_id": seen["run_id"]}
    return run


def test_the_context_is_what_gary_already_knows():
    state = STORY[-1]["state"]
    ctx = personal.build_context(state, ["short", "long", "long"], [{"picks": [{"place": "Kains Woods"}]}], "Harris Park")
    labels = [f["label"] for f in state["journal"]]
    assert ctx["likes"] and set(ctx["likes"]) <= set(labels) and len(ctx["likes"]) <= personal.LIKES_MAX
    assert ctx["likes"][0] == min(set(labels), key=lambda x: (-labels.count(x), x))  # most found; ties by name
    assert set(ctx["been"]) == {t["place"] for t in state["map"] if t["cleared"] or t.get("visited")}
    assert ctx["prefers"] == "long" and ctx["near"] == "Harris Park" and ctx["suggested"] == ["Kains Woods"]
    assert "mood" not in json.dumps(ctx)
    new = personal.build_context({"journal": [], "map": []}, ["short", "long"])
    assert new == {"likes": [], "prefers": None, "been": [], "near": None, "with_friend": False, "suggested": []}


def test_the_goal_says_who_it_is_for_and_asks_why_from_the_page():
    ctx = {"likes": ["duck", "bus"], "prefers": "short", "been": ["Gibbons Park"], "near": "Harris Park", "with_friend": True}
    goal = personal.personal_goal(SOURCES[0], ctx)
    assert goal.startswith(SOURCES[0]["goal"])
    for words in ("They like finding ducks and buses.", "short outings", "already been to Gibbons Park",
                  "near Harris Park", "with a friend", "Only list places that are on this page", '"why"'):
        assert words in goal
    assert goal.rstrip().endswith('"why": ...}]}.')
    assert "They are new" in personal.personal_goal(SOURCES[0], {})


def test_pages_follow_the_explorer_and_the_slow_events_pages_come_last():
    long_nature = personal.choose_pages(SOURCES, {"prefers": "long", "likes": ["duck"]})
    assert [s["kind"] for s in long_nature] == ["trails", "trails"]
    short = personal.choose_pages(SOURCES, {"prefers": "short"})
    assert short[0]["kind"] == "parks" and all(s["kind"] != "events" or s is short[-1] for s in short)
    assert len(personal.choose_pages(SOURCES, {}, pages=5)) == 5


def test_picks_are_only_the_agents_places_and_pass_garys_checks():
    calls = []
    ctx = {"likes": ["duck"], "prefers": "short", "been": ["Victoria Park"], "near": None, "with_friend": False, "suggested": []}
    record = personal.run_picks(ctx, SOURCES, "key", ALLOWED, DAY, run=agent(PARKS, calls), pages=1)
    assert record["status"] == "ok" and len(calls) == 1 and "They like finding ducks." in calls[0]["goal"]
    places = [p["place"] for p in record["picks"]]
    assert set(places) <= {p["name"] for p in PARKS["places"]} and "Closed Park" not in places
    assert places[0] == "Sifton Bog"  # new to them, and a duck: what they like
    assert places.index("Victoria Park") > places.index("Sifton Bog")  # been there already
    by_place = {p["place"]: p for p in record["picks"]}
    assert by_place["Sifton Bog"]["why"] == "Ducks on the quiet bog."
    assert "New to you" in by_place["Sifton Bog"]["reasons"] and "You like finding ducks" in by_place["Sifton Bog"]["reasons"]
    assert by_place["Gibbons Park"]["why"] is None  # a reason that talks of a cliff is not passed on
    for pick in record["picks"]:
        assert pick["quest"]["source"] == "tinyfish" and pick["quest"]["target"] in ALLOWED
        assert not any(k.startswith("_") for k in pick["quest"])
    assert record["runs"][0]["run_id"] and {"name": "Closed Park", "why": "it is closed"} in record["runs"][0]["dropped"]


def test_a_failure_is_reported_and_nothing_is_made_up():
    ctx = personal.build_context({"journal": [], "map": []})
    failed = personal.run_picks(ctx, SOURCES, "key", ALLOWED, DAY, run=agent(RuntimeError("TinyFish sent nothing")))
    assert failed["status"] == "failed" and failed["picks"] == [] and "TinyFish sent nothing" in failed["error"]
    refused = personal.run_picks(ctx, SOURCES, "key", ALLOWED, DAY, run=agent(scout.Refused("HTTP 401")))
    assert refused["status"] == "failed" and refused["refused_key"] is True
    calls = []
    nokey = personal.run_picks(ctx, SOURCES, "", ALLOWED, DAY, run=agent(PARKS, calls))
    assert nokey["status"] == "failed" and calls == []
    empty = personal.run_picks(ctx, SOURCES, "key", ALLOWED, DAY, run=agent({"places": []}))
    assert empty["status"] == "empty" and empty["picks"] == []


def test_one_page_failing_still_gives_the_others_picks():
    def run(url, goal, key, say, steps, seen, endpoint, wait):
        if "hiking" in url:
            raise RuntimeError("no answer after 150 seconds")
        return agent(PARKS)(url, goal, key, say, steps, seen, endpoint, wait)
    record = personal.run_picks({"prefers": "long", "likes": ["duck"]}, SOURCES, "key", ALLOWED, DAY, run=run)
    assert record["status"] == "ok" and record["picks"] and "no answer" in record["partial"][0]


def test_suggested_before_and_not_taken_up_gives_the_others_a_turn():
    base = {"likes": [], "prefers": None, "been": [], "near": None, "with_friend": False}
    first = personal.run_picks(dict(base, suggested=[]), SOURCES, "key", ALLOWED, DAY, run=agent(PARKS), pages=1)
    top = first["picks"][0]["place"]
    again = personal.run_picks(dict(base, suggested=[top]), SOURCES, "key", ALLOWED, DAY, run=agent(PARKS), pages=1)
    assert again["picks"][0]["place"] != top and top in [p["place"] for p in again["picks"]]


def test_the_whole_way_through_a_stand_in_for_tinyfish_over_http():
    events = [{"type": "STARTED", "run_id": "run_live"},
              {"type": "STREAMING_URL", "run_id": "run_live", "streaming_url": "https://tinyfish.example/live"},
              {"type": "COMPLETE", "status": "COMPLETED", "result": PARKS}]
    fake = FakeTinyFish({s["url"]: events for s in SOURCES})
    try:
        record = personal.run_picks({"near": "Harris Park"}, SOURCES, "test-key", ALLOWED, DAY, fake.url, wait=10)
    finally:
        fake.close()
    assert record["status"] == "ok" and len(fake.calls) == personal.PAGES
    assert all(c["key"] == "test-key" and "near Harris Park" in c["body"]["goal"] for c in fake.calls)
    assert all(r["run_id"] == "run_live" and r["streaming_url"] for r in record["runs"])


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        fn()
        print("ok  ", name)
    print("%d tests passed" % len(tests))
