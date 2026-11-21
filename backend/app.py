"""Gary's backend: a small API in front of rules.py.

Run it from this folder:

    pip install -r requirements.txt
    uvicorn app:app --reload --port 8000

Then open http://localhost:8000/docs to try every endpoint in the browser.

Phase 1 keeps everything in memory, so a restart starts fresh. Postgres on
Tiger Data replaces Store in Phase 3 (issue #16). The shapes are in contract/.
"""
import datetime as dt
import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from fastapi import Body, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import rules

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contract"
FRIEND, OUTDOOR = rules.load_labels(CONTRACT / "labels.json")

QUEST_REQUIRED = ("id", "title", "place", "time", "target", "xp")


def now():
    """Server time. Tests replace this to pin the clock."""
    return dt.datetime.now(dt.timezone.utc)


def nap_seconds():
    return float(os.environ.get("GARY_NAP_SECONDS", rules.NAP_SECONDS))


class Store:
    """Everything the backend remembers. In memory for Phase 1."""

    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.events = []        # every event, in arrival order
        self.event_ids = set()  # so the same upload twice counts once
        self.moods = []         # private. Never part of /api/state
        self.quests = []        # oldest first
        seed = Path(os.environ.get("GARY_SEED", CONTRACT / "examples" / "quests.json"))
        if seed.exists():
            for quest in json.loads(seed.read_text(encoding="utf-8")).get("quests", []):
                self.put_quest(quest)

    def put_quest(self, quest):
        for i, old in enumerate(self.quests):
            if old["id"] == quest["id"]:
                self.quests[i] = quest
                return
        self.quests.append(quest)


store = Store()
app = FastAPI(title="Gary the Goat", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def as_list(payload, key):
    """Accept {"events": [...]}, a bare list, or one object."""
    if isinstance(payload, dict) and key in payload:
        payload = payload[key]
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise HTTPException(422, 'send {"%s": [...]} or a single object' % key)
    return payload


def check_quest(raw):
    """-> (clean quest, None) or (None, why it was refused)."""
    missing = [k for k in QUEST_REQUIRED if raw.get(k) in (None, "")]
    if missing:
        return None, "missing " + ", ".join(missing)
    if raw["time"] not in ("short", "long"):
        return None, 'time must be "short" or "long"'
    target = str(raw["target"]).strip().lower()
    if target not in OUTDOOR:
        return None, "Gary cannot recognise '%s'. Pick a name from contract/labels.json" % raw["target"]
    try:
        xp = int(raw["xp"])
    except (TypeError, ValueError):
        return None, "xp must be a number"
    return {
        "id": str(raw["id"]), "title": str(raw["title"]), "place": str(raw["place"]),
        "time": raw["time"], "minutes": raw.get("minutes"), "target": target, "xp": xp,
        "herd": bool(raw.get("herd", False)), "source": raw.get("source", "manual"),
        "source_url": raw.get("source_url"), "day": raw.get("day") or now().date().isoformat(),
    }, None


def current():
    return rules.compute(store.events, store.quests, OUTDOOR, now(), nap_seconds())


@app.get("/api/health")
def health():
    return {"ok": True, "events": len(store.events), "quests": len(store.quests)}


@app.post("/api/events")
def post_events(payload: Any = Body(...)):
    """The device's journal arrives here. Sending the same id twice is harmless."""
    events = as_list(payload, "events")
    accepted, duplicates, ids = 0, 0, []
    with store.lock:
        for ev in events:
            if not ev.get("id") or not ev.get("type"):
                raise HTTPException(422, "every event needs an id and a type")
            if ev["type"] == "discovery" and not ev.get("label"):
                raise HTTPException(422, "a discovery needs a label")
            ids.append(ev["id"])
            if ev["id"] in store.event_ids:
                duplicates += 1
                continue
            store.event_ids.add(ev["id"])
            if ev["type"] == "mood":
                store.moods.append({"ts": ev.get("ts"), "phase": ev.get("phase"), "value": ev.get("value")})
            else:
                store.events.append(ev)
            accepted += 1
        _, results, _ = current()
    blank = {"xp": 0, "reaction": "mood", "new": False, "quest_id": None}
    return {"accepted": accepted, "duplicates": duplicates,
            "results": [dict(id=i, **results.get(i, blank)) for i in ids]}


@app.get("/api/quests")
def get_quests(time: Optional[str] = Query(None, pattern="^(short|long)$"), all: bool = False):
    """Open quests, oldest first. ?time=short|long filters. ?all=true includes finished ones."""
    with store.lock:
        _, _, done = current()
        quests = [q for q in store.quests
                  if (all or q["id"] not in done) and (time is None or q["time"] == time)]
    return {"quests": quests}


@app.post("/api/quests")
def post_quests(payload: Any = Body(...), x_scout_key: Optional[str] = Header(None)):
    """The scout writes quests here. A quest with a known id is replaced."""
    key = os.environ.get("SCOUT_KEY")
    if key and x_scout_key != key:
        raise HTTPException(401, "wrong or missing X-Scout-Key")
    accepted, rejected = [], []
    with store.lock:
        for raw in as_list(payload, "quests"):
            quest, why = check_quest(raw)
            if quest:
                store.put_quest(quest)
                accepted.append(quest["id"])
            else:
                rejected.append({"id": raw.get("id"), "why": why})
    return {"accepted": accepted, "rejected": rejected}


@app.get("/api/state")
def get_state():
    """Everything the web page draws. Mood is never in here."""
    with store.lock:
        state, _, _ = current()
    return state


@app.post("/api/mood")
def post_mood(payload: dict = Body(...)):
    """A private check-in: {"phase": "before" | "after", "value": 1..5}."""
    phase, value = payload.get("phase"), payload.get("value")
    if phase not in ("before", "after") or not isinstance(value, int) or not 1 <= value <= 5:
        raise HTTPException(422, 'send {"phase": "before" or "after", "value": 1 to 5}')
    with store.lock:
        store.moods.append({"ts": now().strftime("%Y-%m-%dT%H:%M:%SZ"), "phase": phase, "value": value})
    return {"ok": True}


@app.get("/api/wellness")
def get_wellness():
    """Private. Only the person themself sees this. Bare-bones until issue #20."""
    with store.lock:
        state, _, _ = current()
        moods = list(store.moods)
    finds = state["journal"]
    return {"private": True, "checkins": moods, "finds": len(finds),
            "shared": sum(1 for f in finds if f["friend"]), "solo": sum(1 for f in finds if not f["friend"])}


@app.post("/api/dev/reset")
def dev_reset():
    """Forget every event and mood and reload the seed quests. For demos and tests."""
    with store.lock:
        store.reset()
    return {"ok": True}


# If the web page has been built (cd web && npm run build), serve it from here
# too, so one address carries both. This must stay below the API routes.
if (ROOT / "web" / "dist").is_dir():
    app.mount("/", StaticFiles(directory=str(ROOT / "web" / "dist"), html=True), name="web")
