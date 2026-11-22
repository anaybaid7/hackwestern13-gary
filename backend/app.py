"""Gary's backend: a small API in front of rules.py.

Run it from this folder:

    pip install -r requirements.txt
    uvicorn app:app --reload --port 8000

Then open http://localhost:8000/docs to try every endpoint in the browser.

With nothing set it keeps everything in memory, so a restart starts fresh.
Set DATABASE_URL and it uses Postgres on Tiger Data instead (store.py), and a
restart keeps Gary's state. The shapes are in contract/README.md.

Settings, all optional, from the environment or from a .env file beside this
file (or in the repo root):

    DATABASE_URL       postgres://... on Tiger Data. Unset: GARY_DB, then memory
    GARY_DB            a SQLite file (on the Pi). Used when DATABASE_URL is unset
    SCOUT_KEY          the scout must send it as X-Scout-Key to post quests
    GARY_ADMIN_KEY     POST /api/dev/reset must send it as X-Admin-Key
    GARY_PRIVATE_KEY   a passphrase. With it set, the private side (check-ins
                       and the wellness view) opens only with X-Private-Key
    GARY_NAP_SECONDS   quiet time before Gary naps. Default 8 hours; 60 for a demo
    GARY_TZ            where days and weeks turn over. Default America/Toronto
    GARY_SEED          the quests a fresh backend starts with
    GARY_LIVE_DIR      a folder to serve at /live/: Gary's live view, on the Pi
    GARY_SEEING        Gary's seeing.json, served at /api/seeing (labels only)
    GARY_TALK_DIR      where gary_talk.py is, for POST /api/talk. Default ../device.
                       Its .env holds GEMINI_API_KEY and ELEVENLABS_API_KEY
    GARY_SCOUT_AT      run scout/scout.py every day at this local time, "07:00"
    GARY_SELF_URL      this backend's address, for that scout run to post to
    TINYFISH_API_KEY   picks for you (/api/picks). Unset here: the key in scout/.env
    GARY_PICKS_WAIT    seconds one live page may take for picks. Default 150
"""
import datetime as dt
import hmac
import json
import mimetypes
import os
import re
import threading
import uuid
import zoneinfo
from pathlib import Path
from typing import Any, Optional

from fastapi import Body, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import auth
import rules
import scouting
import talk
from store import make_store

# Picks for you (picks.py) run the scout's TinyFish code from ../scout. A copy
# of the backend without that folder still starts; only /api/picks says no.
try:
    import picks
except ImportError as _exc:  # pragma: no cover
    picks, PICKS_MISSING = None, str(_exc)
else:
    PICKS_MISSING = None

# Python 3.14 calls a .wav "audio/vnd.wave", which browsers may refuse to play:
# Gary's voice clips are served as audio/wav.
mimetypes.add_type("audio/wav", ".wav")

# QNX reports no limit for SC_IOV_MAX (-1), and Python 3.14's asyncio then fails
# on every reply too big for one write: the page's script arrived cut short.
# 1024 is the POSIX/Linux value.
try:
    import asyncio.selector_events as _sel
    if getattr(_sel, "SC_IOV_MAX", 1024) < 1:
        _sel.SC_IOV_MAX = 1024
except ImportError:  # pragma: no cover
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONTRACT = ROOT / "contract"


def load_env(path, environ=os.environ):
    """KEY=value lines from a .env file. What is already set wins."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_settings(paths, environ=os.environ):
    """Read the .env files, unless GARY_NO_ENV_FILE is set. The tests and the
    scripts that start a throwaway backend set it, so that a developer's own
    .env, with a real database in it, is never used by a test."""
    if environ.get("GARY_NO_ENV_FILE"):
        return False
    for path in paths:
        load_env(path, environ)
    return True


if load_settings([HERE / ".env", ROOT / ".env"]):
    talk.load_keys()

FRIEND, OUTDOOR = rules.load_labels(CONTRACT / "labels.json")
OUTDOOR_LABELS = sorted(name for name, is_outdoor in OUTDOOR.items() if is_outdoor)
QUEST_REQUIRED = ("id", "title", "place", "time", "target", "xp")
QUEST_XP_MAX = 100  # a posted quest cannot be worth more than this. The scout gives 20 or 40
EVENT_TYPES = ("discovery", "miss", "mood")
CLOCK_TOLERANCE = 2.0  # seconds. A device clock closer than this to ours is taken as right

TZ_NAME = os.environ.get("GARY_TZ") or "America/Toronto"  # a blank setting means the default
try:
    TZ = zoneinfo.ZoneInfo(TZ_NAME)
except Exception:  # no timezone data on this machine
    TZ, TZ_NAME = dt.timezone.utc, "UTC"


def now():
    """Server time. Tests replace this to pin the clock."""
    return dt.datetime.now(dt.timezone.utc)


def nap_seconds():
    """Quiet time before Gary naps. A blank or unreadable setting means the default."""
    try:
        seconds = float(os.environ.get("GARY_NAP_SECONDS") or rules.NAP_SECONDS)
    except ValueError:
        return float(rules.NAP_SECONDS)
    return seconds if seconds > 0 else float(rules.NAP_SECONDS)


def stamp(when):
    return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


store = make_store(Path(os.environ.get("GARY_SEED") or CONTRACT / "examples" / "quests.json"))
lock = threading.Lock()  # one request at a time touches the store
app = FastAPI(title="Gary the Goat", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def key_matches(sent, key):
    """Compare a key the same way whether it is nearly right or all wrong."""
    return hmac.compare_digest(str(sent or "").encode("utf-8"), str(key).encode("utf-8"))


def caller(authorization):
    """Who sent this request, from its Auth0 token. None: no token, or Auth0 is
    off. A token that is sent and is wrong is refused, never ignored."""
    try:
        return auth.identify(authorization)
    except auth.AuthError as err:
        raise HTTPException(401, str(err))


def private_side(sent, who=None):
    """The private side is the check-ins and the wellness view. It opens for a
    signed-in person (Auth0), who then sees their own check-ins, or with the
    passphrase when the server sets GARY_PRIVATE_KEY. -> is it locked?"""
    key = os.environ.get("GARY_PRIVATE_KEY")
    if who and not who["machine"]:
        return True
    if key and key_matches(sent, key):
        return True
    if key or auth.enabled():
        raise HTTPException(401, "The private page is locked. Sign in, or send its passphrase as X-Private-Key.")
    return False


def guarded(setting, sent, who, permission, header):
    """A shared key or an Auth0 permission opens this door. With neither set
    up on the server, the door is open, as on a laptop."""
    key = os.environ.get(setting)
    if auth.allows(who, permission) or (key and key_matches(sent, key)):
        return
    if key or auth.enabled():
        raise HTTPException(401, "wrong or missing %s, and no token with %s" % (header, permission))


def as_list(payload, key):
    """Accept {"events": [...]}, a bare list, or one object."""
    if isinstance(payload, dict) and key in payload:
        payload = payload[key]
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise HTTPException(422, 'send {"%s": [...]} or a single object' % key)
    return payload


def event_time(device_ts, sent_at, received):
    """When an event really happened, by our clock. -> (datetime, was it changed)

    A Pi that starts with no network may not know the time, so its journal can
    be stamped hours or years off. sync.py sends what the device's clock reads
    at upload time ("sent_at"). The gap between that and our clock is how wrong
    the device is, and every event in the upload is moved by that much.
    An event is never dated in the future.
    """
    when = rules.parse_ts(device_ts)
    if when is None:
        return received, device_ts is not None
    changed = False
    if sent_at is not None:
        skew = (received - sent_at).total_seconds()
        if abs(skew) > CLOCK_TOLERANCE:
            when, changed = when + dt.timedelta(seconds=skew), True
    if when > received:
        when, changed = received, True
    return when, changed


def check_mood(phase, value):
    if phase not in ("before", "after") or isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise HTTPException(422, 'a mood check-in needs "phase": "before" or "after", and "value": 1 to 5')


def clean_event(raw, sent_at, received):
    """One event from a device -> the tidy form the store and the rules use."""
    if not raw.get("id") or not raw.get("type"):
        raise HTTPException(422, "every event needs an id and a type")
    kind = raw["type"]
    if kind not in EVENT_TYPES:
        raise HTTPException(422, "type must be one of: %s" % ", ".join(EVENT_TYPES))
    event = dict(raw)
    event["id"] = str(raw["id"])
    when, changed = event_time(raw.get("ts"), sent_at, received)
    if changed:
        event["device_ts"] = raw.get("ts")  # what the device wrote, kept for the record
    event["ts"] = stamp(when)
    if kind == "discovery":
        label = str(raw.get("label") or "").strip().lower()
        if not label:
            raise HTTPException(422, "a discovery needs a label")
        event["label"] = label
        event["friend"] = bool(raw.get("friend"))
    elif kind == "miss":
        event["friend"] = bool(raw.get("friend"))
    else:
        check_mood(raw.get("phase"), raw.get("value"))
        event["source"] = "device"
    return event


def one_line(value, limit):
    """Plain text on one line: line breaks, tabs and control characters become
    spaces, runs of spaces become one, and it is cut at `limit`. A quest's words
    can come from a web page (through the scout) and they end up in the device's
    tab-separated quest file, so they are cleaned here, once, for everyone."""
    text = "".join(ch if ch.isprintable() else " " for ch in str(value))
    return " ".join(text.split())[:limit]


def web_address(value):
    """An http or https address, or None. The page makes a link of it, so
    nothing else is let through."""
    text = str(value or "").strip()
    lower = text.lower()
    has_scheme = lower.startswith("http://") or lower.startswith("https://")
    has_bad_char = any(ch.isspace() or ch in "<>\"'" for ch in text)
    return text if len(text) <= 300 and has_scheme and not has_bad_char else None


def check_quest(raw):
    """-> (clean quest, None) or (None, why it was refused)."""
    if not isinstance(raw, dict):
        return None, "a quest must be an object"
    clean = {"id": one_line(raw.get("id") or "", 80).replace(" ", "-"),
             "title": one_line(raw.get("title") or "", 140),
             "place": one_line(raw.get("place") or "", 80)}
    missing = [k for k in QUEST_REQUIRED if (clean[k] if k in clean else raw.get(k)) in (None, "")]
    if missing:
        return None, "missing " + ", ".join(missing)
    if raw["time"] not in ("short", "long"):
        return None, 'time must be "short" or "long"'
    target = str(raw["target"]).strip().lower()
    if target not in OUTDOOR:
        return None, "Gary cannot recognise '%s'. Pick a name from contract/labels.json" % one_line(raw["target"], 40)
    try:
        xp = int(raw["xp"])
    except (TypeError, ValueError):
        return None, "xp must be a number"
    if not 1 <= xp <= QUEST_XP_MAX:
        return None, "xp must be between 1 and %d" % QUEST_XP_MAX
    try:
        minutes = int(raw["minutes"])
        minutes = minutes if 1 <= minutes <= 600 else None
    except (KeyError, TypeError, ValueError):
        minutes = None
    day = str(raw.get("day") or "")
    return {
        **clean, "time": raw["time"], "minutes": minutes, "target": target, "xp": xp,
        "herd": raw.get("herd") is True,
        "note": (one_line(raw["note"], 200) or None) if raw.get("note") else None,
        "source": one_line(raw.get("source") or "manual", 20) or "manual",
        "source_url": web_address(raw.get("source_url")),
        "day": day if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) else rules.local_day(now(), TZ),
        "lat": degrees(raw.get("lat"), 90), "lng": degrees(raw.get("lng"), 180),
        # Gary's trail tidbits (the scout, with Gemini): plain lines only, at most three
        "tidbits": [line for line in (one_line(t, 160) for t in raw.get("tidbits") or [] if isinstance(t, str))
                    if line][:3] if isinstance(raw.get("tidbits"), list) else [],
    }, None


def degrees(value, limit):
    """A latitude or longitude, or None: the page uses it to tell whether you
    are at the place, so anything that is not a number in range is dropped."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(float(value), 6) if -limit <= value <= limit else None


def current(events=None, quests=None):
    """The state right now. Call with the lock held."""
    return rules.compute(store.events() if events is None else events,
                         store.quests() if quests is None else quests,
                         OUTDOOR, now(), nap_seconds(), TZ)


@app.get("/api/seeing")
def seeing():
    """What Gary is sure he sees right now: seeing.json, labels only, never a
    picture. Lets gary_talk.py run on a laptop while Gary looks on the Pi."""
    path = os.environ.get("GARY_SEEING")
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}
    except (OSError, ValueError):
        return {}


@app.get("/api/health")
def health():
    """Is the backend up, and how is it set up? Says whether each key is set,
    never what it is."""
    with lock:
        return {"ok": True, **store.counts(), **store.info(), "timezone": TZ_NAME,
                "nap_seconds": nap_seconds(),
                "keys": {name: bool(os.environ.get(setting)) for name, setting in
                         (("scout", "SCOUT_KEY"), ("admin", "GARY_ADMIN_KEY"), ("private", "GARY_PRIVATE_KEY"))},
                "auth0": auth.enabled()}


@app.get("/api/auth/config")
def auth_config():
    """What the page and the device need to start an Auth0 login. Nothing secret."""
    return auth.public_config()


@app.get("/api/me")
def get_me(authorization: Optional[str] = Header(None)):
    """Who the token says you are, as Gary knows you: a fingerprint, never a
    name. "paired" says whether a Gary has sent sniffs signed as you."""
    who = caller(authorization)
    if not who:
        return {"signed_in": False}
    with lock:
        paired = any(ev.get("owner") == who["fingerprint"] for ev in store.events())
    return {"signed_in": True, "fingerprint": who["fingerprint"], "paired": paired,
            "permissions": who["permissions"]}


@app.post("/api/events")
def post_events(payload: Any = Body(...), authorization: Optional[str] = Header(None)):
    """The device's journal arrives here. Sending the same id twice is harmless.
    A Gary that was paired (Auth0 device flow) sends a token: his sniffs are
    then marked with his person's fingerprint. No token is fine too."""
    who = caller(authorization)
    events = as_list(payload, "events")
    sent_at = rules.parse_ts(payload.get("sent_at")) if isinstance(payload, dict) else None
    received = now()
    clean = [clean_event(raw, sent_at, received) for raw in events]
    for event in clean:
        event.pop("owner", None)  # only a checked token can say whose it is
        if who and not who["machine"]:
            event["owner"] = who["fingerprint"]
    with lock:
        accepted = len(store.add(clean))
        _, results, _ = current()
    blank = {"xp": 0, "reaction": "mood", "new": False, "quest_id": None}
    return {"accepted": accepted, "duplicates": len(clean) - accepted,
            "results": [dict(id=ev["id"], **results.get(ev["id"], blank)) for ev in clean]}


@app.get("/api/quests")
def get_quests(time: Optional[str] = Query(None, pattern="^(short|long)$"), all: bool = False):
    """Open quests. The active one comes first and is marked, so the device
    prefers it; the rest are oldest first. ?time=short|long filters.
    ?all=true includes finished ones."""
    with lock:
        quests = store.quests()
        state, _, done = current(quests=quests)
    active_id = state["quest"]["id"] if state["quest"] else None
    listed = [dict(q, active=q["id"] == active_id) for q in quests
              if (all or q["id"] not in done) and (time is None or q["time"] == time)]
    listed.sort(key=lambda q: not q["active"])  # stable: only the active one moves
    return {"quests": listed}


@app.post("/api/quests")
def post_quests(payload: Any = Body(...), x_scout_key: Optional[str] = Header(None),
                authorization: Optional[str] = Header(None)):
    """The scout writes quests here. A quest with a known id is replaced. It
    proves itself with SCOUT_KEY or with an Auth0 token that has write:quests."""
    guarded("SCOUT_KEY", x_scout_key, caller(authorization), "write:quests", "X-Scout-Key")
    accepted, rejected = [], []
    with lock:
        for raw in as_list(payload, "quests"):
            quest, why = check_quest(raw)
            if quest:
                store.put_quest(quest)
                accepted.append(quest["id"])
            else:
                rejected.append({"id": raw.get("id") if isinstance(raw, dict) else None, "why": why})
    return {"accepted": accepted, "rejected": rejected}


@app.post("/api/quest/choose")
def choose_quest(payload: dict = Body(...)):
    """{"time": "short" | "long"} makes a quest of that length the active one.
    With "quest_id" too, that open quest (the page's nearest pick for short).
    Today's scout quests come first. Asking again moves on to the next one.
    Returns the quest (null if none of that length is open) and the new state."""
    time = payload.get("time")
    if time not in ("short", "long"):
        raise HTTPException(422, 'send {"time": "short"} or {"time": "long"}')
    wanted = payload.get("quest_id")
    with lock:
        quests = store.quests()
        state, _, done = current(quests=quests)
        if wanted is not None:
            # The page picked it: the nearest open quest, worked out in the browser
            # from a position that never leaves it. Only the id arrives.
            quest = next((q for q in quests if q["id"] == wanted and q["id"] not in done), None)
            if quest is None:
                raise HTTPException(422, "no open quest has that id")
        else:
            showing = state["quest"]["id"] if state["quest"] and state["quest_choice"] == time else None
            quest = rules.choose(quests, done, time, now(), TZ, showing)
        if quest is not None:
            # The choice joins the event stream, so the rules can tell which
            # quest was active when each sniff happened, and a restart keeps it.
            store.add([{"id": "choice-" + uuid.uuid4().hex[:12], "ts": stamp(now()), "type": "choice",
                        "time": time, "quest_id": quest["id"]}])
            state, _, _ = current(quests=quests)
    return {"quest": quest, "state": state}


# -- picks for you: a TinyFish agent chooses places from live pages ----------
picks_runner = picks.Runner() if picks else None


def picks_or_503():
    if picks is None:
        raise HTTPException(503, "picks need the scout folder beside the backend (%s)" % PICKS_MISSING)
    return picks


@app.get("/api/picks")
def get_picks():
    """The last good picks, the request running now (if any), and the last few
    requests. Picks are only ever places a TinyFish agent read on a live page."""
    p = picks_or_503()
    with lock:
        history = store.picks()
    return p.view(picks_runner.current(), history, bool(p.api_key()))


@app.post("/api/picks", status_code=202)
def ask_picks(payload: Any = Body(None)):
    """{"near": <a known place>}, optional: start a picks request. The page
    works out which known place is nearest in the browser and sends only that
    name; anything that is not the name of one of Gary's places is ignored.
    One request runs at a time: asking again returns the one running."""
    p = picks_or_503()
    if not p.api_key():
        raise HTTPException(503, "TinyFish is not set up on this server: put TINYFISH_API_KEY in backend/.env")
    asked = one_line((payload.get("near") if isinstance(payload, dict) else None) or "", 80)
    with lock:
        quests = store.quests()
        state, _, _ = current(quests=quests)
        known = {rules.place_key(q["place"]): q["place"] for q in quests}
        near = known.get(rules.place_key(asked)) if asked else None
        choices = [ev.get("time") for ev in store.events() if ev.get("type") == "choice"]
        context = p.personal.build_context(state, choices, store.picks(), near)

    def keep(record):
        with lock:
            store.add_pick(record)

    job, started = picks_runner.start(context, rules.local_day(now(), TZ), keep)
    return {"job": job, "started": started}


@app.post("/api/picks/take")
def take_pick(payload: dict = Body(...)):
    """{"id": <the quest id of a pick>}: make that pick today's quest. It is
    checked like any posted quest, added, and chosen."""
    p = picks_or_503()
    with lock:
        raw = p.find_pick(store.picks(), str(payload.get("id") or ""))
        if raw is None:
            raise HTTPException(404, "no pick has that id")
        quest, why = check_quest(raw)
        if quest is None:
            raise HTTPException(422, why)
        store.put_quest(quest)
        store.add([{"id": "choice-" + uuid.uuid4().hex[:12], "ts": stamp(now()), "type": "choice",
                    "time": quest["time"], "quest_id": quest["id"]}])
        state, _, _ = current()
    return {"quest": quest, "state": state}


@app.get("/api/state")
def get_state():
    """Everything the web page draws. Mood is never in here."""
    with lock:
        state, _, _ = current()
    return state


@app.post("/api/mood")
def post_mood(payload: dict = Body(...), x_private_key: Optional[str] = Header(None),
              authorization: Optional[str] = Header(None)):
    """A private check-in: {"phase": "before" | "after", "value": 1..5}.
    Signed in, it is kept as yours."""
    who = caller(authorization)
    private_side(x_private_key, who)
    check_mood(payload.get("phase"), payload.get("value"))
    mine = who["fingerprint"] if who and not who["machine"] else None
    with lock:
        store.add([{"id": "mood-" + uuid.uuid4().hex[:12], "ts": stamp(now()), "type": "mood",
                    "phase": payload["phase"], "value": payload["value"], "source": "web", "owner": mine}])
    return {"ok": True}


@app.post("/api/visit")
def post_visit(payload: dict = Body(...)):
    """{"quest_id": ...}: the web page is at that quest's place. It works that
    out in the browser, so no position ever reaches this server, and only the
    quest id is kept. A quest finished near a visit earns the Been there bonus."""
    quest_id = str(payload.get("quest_id") or "")
    with lock:
        if not any(q["id"] == quest_id for q in store.quests()):
            raise HTTPException(422, "no quest has that id")
        store.add([{"id": "visit-" + uuid.uuid4().hex[:12], "ts": stamp(now()), "type": "visit",
                    "quest_id": quest_id}])
    return {"ok": True}


talk_lock = threading.Lock()  # one conversation at a time: each turn costs Gemini and ElevenLabs calls


@app.get("/api/talk")
def talk_config():
    """Whether the page can talk to Gary: gary_talk.py is here and both keys are set."""
    return {"enabled": talk.enabled()}


@app.post("/api/talk")
def post_talk(payload: dict = Body(...)):
    """One thing said on the web page: {"audio": base64 WAV (16 kHz mono),
    "listening": Gary asked something or was just woken, "history": the last
    few [said, replied]}. Nothing said is stored or logged."""
    if not talk.enabled():
        raise HTTPException(503, "talking is off: this server needs gary_talk.py and both keys")
    pcm = talk.pcm_of(payload.get("audio"))
    if pcm is None:
        raise HTTPException(422, "send audio: a base64 WAV, 16 kHz mono 16-bit, under 9 seconds")
    if not talk_lock.acquire(blocking=False):
        return {"busy": True}
    try:
        with lock:
            state, _, _ = current()

        def choose(time_):
            return choose_quest({"time": time_})["quest"]

        def post_quest(quest):
            with lock:
                checked, why = check_quest(quest)
                if checked:
                    store.put_quest(checked)
            return None if checked else why

        things = [name for name in OUTDOOR_LABELS if name != FRIEND]
        seeing = talk.brain.read_seeing(os.environ.get("GARY_SEEING") or "")
        gemini_key, eleven_key = talk.keys()
        return talk.turn(pcm, payload.get("listening") is True, talk.history_of(payload.get("history")), seeing,
                         talk.App(state, choose, post_quest, things), gemini_key, eleven_key)
    except talk.brain.TalkError as exc:
        return {"error": str(exc)}
    finally:
        talk_lock.release()


@app.get("/api/scout")
def scout_status():
    """The scout's last run started from here: running, started, finished, ok."""
    return dict(scouting.status, available=scouting.available(), daily_at=os.environ.get("GARY_SCOUT_AT") or None)


@app.post("/api/scout/run")
def scout_run(x_admin_key: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    """Send the scout out now (it takes minutes). Guarded like reset. The quests
    arrive through POST /api/quests as usual."""
    guarded("GARY_ADMIN_KEY", x_admin_key, caller(authorization), "reset:gary", "X-Admin-Key")
    if not scouting.available():
        raise HTTPException(503, "scout/scout.py is not on this server")
    sent = scouting.start("asked")
    return dict(scouting.status, sent=sent)


@app.get("/api/wellness")
def get_wellness(x_private_key: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    """The private side: check-ins, before and after pairs, estimated outdoor
    minutes per day, and solo versus shared finds. None of it is ever part of
    /api/state. "locked" says whether a passphrase guards it: without
    GARY_PRIVATE_KEY anyone who has the address can read this, and the page
    says so. The wording never says an outing caused a feeling."""
    who = caller(authorization)
    locked = private_side(x_private_key, who)
    mine = who["fingerprint"] if who and not who["machine"] else None
    with lock:
        events, moods = store.events(), store.moods()
        days = store.outdoor_by_day(OUTDOOR_LABELS, TZ_NAME)
    # Signed in: your own check-ins. With the passphrase: the ones nobody signed.
    moods = [m for m in moods if m.get("owner") == mine]
    return dict(rules.wellness(moods, events, OUTDOOR, TZ, days), locked=locked, signed_in=bool(mine))


@app.post("/api/dev/reset")
def dev_reset(payload: Any = Body(None), x_admin_key: Optional[str] = Header(None),
              authorization: Optional[str] = Header(None)):
    """Forget every event and mood and reload the seed quests. For demos and tests.
    With {"keep_quests": true} the quests stay, the scout's included, and every
    one is open again: that is the page's "Reset Gary" button."""
    guarded("GARY_ADMIN_KEY", x_admin_key, caller(authorization), "reset:gary", "X-Admin-Key")
    keep = isinstance(payload, dict) and payload.get("keep_quests") is True
    with lock:
        store.reset(keep_quests=keep)
    return {"ok": True, "quests_kept": keep}


scouting.schedule(TZ)

# If the web page has been built (cd web && npm run build), serve it from here
# too, so one address carries both. This must stay below the API routes.
# GARY_LIVE_DIR: on the Pi, the folder Gary writes his live frame to. Served
# at /live/, so the page's "What Gary sees" link needs no second server.
if os.environ.get("GARY_LIVE_DIR") and Path(os.environ["GARY_LIVE_DIR"]).is_dir():
    app.mount("/live", StaticFiles(directory=os.environ["GARY_LIVE_DIR"], html=True), name="live")
if (ROOT / "web" / "dist").is_dir():
    app.mount("/", StaticFiles(directory=str(ROOT / "web" / "dist"), html=True), name="web")
