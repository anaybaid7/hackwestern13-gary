"""Scout tests. No API key and no network needed.

    python3 scout/tests/test_scout.py      # plain Python
    pytest scout                           # or with pytest
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCOUT = os.path.dirname(HERE)
ROOT = os.path.dirname(SCOUT)
sys.path.insert(0, SCOUT)

import scout  # noqa: E402

ALLOWED = scout.load_labels()
SOURCE = {"name": "test", "url": "https://example.org/parks", "time": "short"}

# The stream shape documented by TinyFish: "data: " lines, each a JSON event.
STREAM = [
    b'data: {"type":"STARTED","run_id":"run_123","timestamp":"2026-11-21T06:00:00Z"}\n',
    b"\n",
    b'data: {"type":"STREAMING_URL","run_id":"run_123","streaming_url":"https://example.org/live/run_123","timestamp":"2026-11-21T06:00:01Z"}\n',
    b'data: {"type":"PROGRESS","run_id":"run_123","purpose":"Reading the list of parks","timestamp":"2026-11-21T06:00:05Z"}\n',
    b'data: {"type":"HEARTBEAT","timestamp":"2026-11-21T06:00:10Z"}\n',
    b": a comment line\n",
    b'data: {"type":"COMPLETE","run_id":"run_123","status":"COMPLETED","result":{"places":[{"name":"Harris Park","about":"Riverside park"}]},"timestamp":"2026-11-21T06:00:20Z"}\n',
    b'data: {"type":"PROGRESS","purpose":"never reached"}\n',
]


def sample_places():
    with open(os.path.join(SCOUT, "sample_result.json"), "r", encoding="utf-8") as f:
        return scout.find_places(json.load(f))


def test_stream_is_read_to_the_complete_event():
    seen = []
    final = scout.parse_sse(STREAM, seen.append)
    assert final["status"] == "COMPLETED" and final["run_id"] == "run_123"
    assert final["streaming_url"] == "https://example.org/live/run_123"
    assert final["result"]["places"][0]["name"] == "Harris Park"
    assert [e["type"] for e in seen] == ["STARTED", "STREAMING_URL", "PROGRESS", "HEARTBEAT", "COMPLETE"]


def test_stream_without_a_complete_event_gives_none():
    assert scout.parse_sse(STREAM[:4]) is None


def test_places_are_found_in_different_reply_shapes():
    places = [{"name": "A"}, {"name": "B"}]
    assert scout.find_places({"places": places}) == places
    assert scout.find_places(places) == places
    assert scout.find_places({"data": {"items": places}}) == places
    assert scout.find_places(json.dumps({"places": places})) == places
    assert scout.find_places({"error": "nothing here"}) == []
    assert scout.find_places("not json") == []


def test_quests_match_the_contract():
    quests = scout.build_quests(sample_places(), SOURCE, "2026-11-21", ALLOWED, limit=4)
    with open(os.path.join(ROOT, "contract", "examples", "quest.json"), "r", encoding="utf-8") as f:
        example = json.load(f)
    assert len(quests) == 4
    for quest in quests:
        assert set(quest) == set(example), "same fields as contract/examples/quest.json"
        assert quest["target"] in ALLOWED, "Gary must be able to recognise the target outdoors"
        assert quest["time"] in ("short", "long")
        assert quest["xp"] == (40 if quest["time"] == "long" else 20)
        assert quest["source"] == "tinyfish" and quest["source_url"]
        assert quest["place"] in quest["title"]
    assert len({q["id"] for q in quests}) == 4


def test_targets_and_lengths_follow_the_place():
    quests = {q["place"]: q for q in scout.build_quests(sample_places(), SOURCE, "2026-11-21", ALLOWED, limit=4)}
    assert quests["Harris Park"]["target"] == "bicycle"       # "paved path"
    assert quests["Springbank Park"]["target"] == "bench"     # "gardens and picnic areas"
    assert quests["Kains Woods"]["target"] == "bird"          # "wooded hiking trail"
    assert quests["Kains Woods"]["time"] == "long" and quests["Harris Park"]["time"] == "short"


def test_every_third_quest_is_a_herd_quest():
    quests = scout.build_quests(sample_places(), SOURCE, "2026-11-21", ALLOWED, limit=4)
    assert [q["herd"] for q in quests] == [False, False, True, False]
    assert quests[2]["title"].endswith(", with a friend")


def test_duplicates_blanks_and_the_limit():
    places = [{"name": "Harris Park"}, {"name": "harris park"}, {"name": ""}, {"about": "no name"},
              {"name": "Gibbons Park"}, {"name": "Springbank Park"}, {"name": "Victoria Park"}]
    quests = scout.build_quests(places, SOURCE, "2026-11-21", ALLOWED, limit=3)
    assert [q["place"] for q in quests] == ["Harris Park", "Gibbons Park", "Springbank Park"]


def test_a_place_with_no_clues_still_gets_a_valid_target():
    quests = scout.build_quests([{"name": "Somewhere"}, {"name": "Elsewhere"}], SOURCE, "2026-11-21", ALLOWED)
    assert [q["target"] for q in quests] == ["bench", "bird"]


def test_sources_file_is_well_formed():
    with open(os.path.join(SCOUT, "sources.json"), "r", encoding="utf-8") as f:
        sources = json.load(f)
    assert sources, "at least one source"
    for source in sources:
        assert source["url"].startswith("https://") and source["goal"] and source["name"]
        assert "JSON" in source["goal"] and "places" in source["goal"]


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        fn()
        print("ok  ", name)
    print("%d tests passed" % len(tests))
