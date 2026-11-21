#!/usr/bin/env python3
"""make_examples.py - write the contract's example files from the real backend.

The examples in contract/examples/ are what the web page and its mock mode are
built against, so they must be what the backend really returns. This script
runs the backend in memory with the clock pinned, plays a fixed set of calls,
and writes the replies.

    python3 scripts/make_examples.py           rewrite state.json, wellness.json and story.json
    python3 scripts/make_examples.py --check   exit 1 if any of them is out of date

Run it after any change to backend/rules.py, and commit the result.
backend/tests checks that the files are current.
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "contract" / "examples"
os.environ["DATABASE_URL"] = ""          # always the in-memory store
for name in ("SCOUT_KEY", "GARY_ADMIN_KEY", "GARY_NAP_SECONDS", "GARY_SEED", "GARY_TZ"):
    os.environ[name] = ""
os.environ["GARY_TZ"] = "America/Toronto"
os.environ.pop("GARY_NAP_SECONDS")
os.environ.pop("GARY_SEED")
sys.path.insert(0, str(ROOT / "backend"))

import app as backend  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def read(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def at(text):
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def sniff(n, ts, label, friend=False, quest_id=None, score=0.93, latency_ms=41.0):
    """A discovery the way the device writes it."""
    return {"id": "gary-01-%d-%d" % (int(at(ts).timestamp() * 1000), n), "ts": ts, "type": "discovery",
            "device": "gary-01", "label": label, "score": score, "friend": friend, "new": True,
            "quest_id": quest_id, "latency_ms": latency_ms}


# The story the web page's mock mode plays, one step per press of "Next".
# Each step: a title, a line about it, the time, and the call that is made.
STORY = [
    ("Saturday morning", "Gary is napping. That costs nothing. The scout has left three quests from live London pages.",
     "2026-11-21T15:00:00Z", None),
    ("A private check-in", "Before heading out: how are you feeling, 1 to 5? Only you ever see this.",
     "2026-11-21T15:01:00Z", ("POST", "/api/mood", {"phase": "before", "value": 3})),
    ("Pick a short quest", "Short or long is the only choice. Gary takes the next quest the scout found today.",
     "2026-11-21T15:02:00Z", ("POST", "/api/quest/choose", {"time": "short"})),
    ("At Springbank Park: the Sniff Test", "One press. Gary's on-device model names a bicycle, the quest is done and the fog lifts.",
     "2026-11-21T15:25:00Z",
     ("POST", "/api/events", {"events": [sniff(1, "2026-11-21T15:25:00Z", "bicycle",
                                               quest_id="q-2026-11-21-springbank-park-bicycle", score=0.91, latency_ms=38.0)]})),
    ("Something on the way", "A fire hydrant. No quest asked for it, so it goes in the field guide.",
     "2026-11-21T15:27:00Z",
     ("POST", "/api/events", {"events": [sniff(2, "2026-11-21T15:27:00Z", "fire hydrant", score=0.84, latency_ms=44.5)]})),
    ("A friend steps into the frame", "Herd Mode. The co-op quest completes, the sniff counts double, and your herd climbs the Herd Cup.",
     "2026-11-21T15:40:00Z",
     ("POST", "/api/events", {"events": [sniff(3, "2026-11-21T15:40:00Z", "dog", friend=True,
                                               quest_id="q-2026-11-21-gibbons-park-dog", score=0.96, latency_ms=36.0)]})),
    ("Home again: the second check-in", "After the walk: 1 to 5 again. The wellness view reports what you said, nothing more.",
     "2026-11-21T16:05:00Z", ("POST", "/api/mood", {"phase": "after", "value": 4})),
    ("Sunday morning", "A night has passed. Gary is napping again. Nothing was taken away.",
     "2026-11-22T14:00:00Z", None),
    ("Pick a long quest", "A longer walk today.",
     "2026-11-22T14:10:00Z", ("POST", "/api/quest/choose", {"time": "long"})),
    ("Welcome back", "A bench by the river at Harris Park. The first sniff after a nap earns a small welcome-back bonus.",
     "2026-11-22T14:40:00Z",
     ("POST", "/api/events", {"events": [sniff(4, "2026-11-22T14:40:00Z", "bench",
                                               quest_id="q-harris-bench", score=0.93, latency_ms=41.0)]})),
]


def build():
    """-> {file name: content} for every generated example."""
    clock = [at("2026-11-21T05:22:00Z")]
    backend.now = lambda: clock[0]
    client = TestClient(backend.app)

    def call(method, path, body=None):
        reply = client.request(method, path, json=body)
        assert reply.status_code == 200, (method, path, reply.status_code, reply.text)
        return reply.json()

    out = {}

    # state.json: a fresh backend, then the three example events.
    backend.store.reset()
    events = [read("event.mood.json"), read("event.discovery.json"), read("event.miss.json")]
    call("POST", "/api/events", {"events": events})
    out["state.json"] = call("GET", "/api/state")

    # wellness.json: the same, plus one "after" check-in half an hour later.
    clock[0] = at("2026-11-21T05:50:00Z")
    call("POST", "/api/mood", {"phase": "after", "value": 4})
    out["wellness.json"] = call("GET", "/api/wellness")

    # story.json: a fresh backend, the scout's quests, then the story step by step.
    backend.store.reset()
    clock[0] = at(STORY[0][2])
    posted = call("POST", "/api/quests", {"quests": read("quests.scout.json")["quests"]})
    assert not posted["rejected"], posted
    steps = []
    for title, note, when, request in STORY:
        clock[0] = at(when)
        if request:
            call(*request)
        steps.append({
            "title": title, "note": note, "now": when,
            "request": {"method": request[0], "path": request[1], "body": request[2]} if request else None,
            "state": call("GET", "/api/state"),
            "wellness": call("GET", "/api/wellness"),
        })
    out["story.json"] = {
        "_note": "Generated by scripts/make_examples.py from the real backend. Do not edit by hand. "
                 "The web page's mock mode plays these steps in order.",
        "steps": steps,
    }
    backend.store.reset()
    return out


def as_text(content):
    return json.dumps(content, indent=2, ensure_ascii=False) + "\n"


def main():
    check = "--check" in sys.argv[1:]
    stale = []
    for name, content in build().items():
        path, text = EXAMPLES / name, as_text(content)
        if path.exists() and path.read_text(encoding="utf-8") == text:
            continue
        stale.append(name)
        if not check:
            path.write_text(text, encoding="utf-8")
            print("wrote contract/examples/%s" % name)
    if check and stale:
        print("Out of date: %s. Run: python3 scripts/make_examples.py" % ", ".join(stale))
        return 1
    if not stale:
        print("contract/examples is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
