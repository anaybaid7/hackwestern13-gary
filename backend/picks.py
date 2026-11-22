"""Picks for you: the backend's side of scout/personal.py.

POST /api/picks starts one TinyFish request in the background (a live page
takes 30 to 200 seconds, longer than a web request should wait). The page
asks GET /api/picks until it is done. One request runs at a time.

TinyFish is the only source of picks. When a request fails, the reply says
so and still carries the last good picks, marked with when they were made.
Every request, good or not, is kept by the store (add_pick), and the next
request reads them back as "previous requests".

Settings:

    TINYFISH_API_KEY   the TinyFish key. Unset here: the one in scout/.env is used
    GARY_PICKS_WAIT    seconds one page may take. Default 150
    GARY_TINYFISH_URL  another TinyFish address (the tests' stand-in)
"""
import datetime as dt
import json
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCOUT = ROOT / "scout"
if str(SCOUT) not in sys.path:
    sys.path.insert(0, str(SCOUT))

import personal  # noqa: E402
import scout  # noqa: E402

HISTORY_SHOWN = 5


def api_key(environ=os.environ):
    """TINYFISH_API_KEY from the backend's settings, else from scout/.env, the
    file the scout already keeps it in. Only that one key is read from there."""
    key = (environ.get("TINYFISH_API_KEY") or "").strip()
    if key or environ.get("GARY_NO_ENV_FILE"):
        return key
    found = {}
    scout.load_settings(str(SCOUT / ".env"), found)
    return (found.get("TINYFISH_API_KEY") or "").strip()


def wait_seconds(environ=os.environ):
    try:
        seconds = int(environ.get("GARY_PICKS_WAIT") or personal.WAIT)
    except ValueError:
        return personal.WAIT
    return seconds if 5 <= seconds <= 600 else personal.WAIT


def sources():
    with open(SCOUT / "sources.json", "r", encoding="utf-8") as f:
        return json.load(f)


def stamp():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Runner:
    """At most one picks request at a time, in a background thread."""

    def __init__(self, spawn=None):
        self.lock = threading.Lock()
        self.job = None
        # tests pass a spawn that runs the job at once
        self.spawn = spawn or (lambda work: threading.Thread(target=work, daemon=True, name="picks").start())

    def start(self, context, day, keep):
        """-> (job, started). A request already running is returned instead of a second one."""
        with self.lock:
            if self.job and self.job["status"] == "running":
                return dict(self.job), False
            job = {"id": None, "status": "running", "started": stamp(), "finished": None, "error": None,
                   "near": context.get("near")}
            self.job = job

        def work():
            try:
                record = personal.run_picks(context, sources(), api_key(), scout.load_labels(), day,
                                            os.environ.get("GARY_TINYFISH_URL") or scout.TINYFISH_URL,
                                            wait_seconds())
            except Exception as exc:  # never leave the job "running" for ever
                record = {"id": "pick-error-" + stamp(), "ts": stamp(), "context": context, "runs": [],
                          "picks": [], "status": "failed", "error": "the picks request stopped: %s" % exc}
            try:
                keep(record)
            finally:
                with self.lock:
                    job.update(id=record["id"], status=record["status"], finished=stamp(),
                               error=record.get("error"))

        self.spawn(work)
        with self.lock:
            return dict(job), True

    def current(self):
        with self.lock:
            return dict(self.job) if self.job else None


def summary(record):
    """A past request, short: for "previous requests" on the page."""
    ctx = record.get("context") or {}
    return {"id": record.get("id"), "ts": record.get("ts"), "status": record.get("status"),
            "near": ctx.get("near"), "likes": ctx.get("likes") or [], "places": [p.get("place") for p in record.get("picks") or []],
            "runs": [{"source": r.get("source"), "status": r.get("status"), "run_id": r.get("run_id")}
                     for r in record.get("runs") or []]}


def view(job, history, ready):
    """GET /api/picks. `picks` are always the last good ones (or none);
    `cached` says they are not from the request that just finished."""
    good = next((r for r in reversed(history) if r.get("status") == "ok" and r.get("picks")), None)
    last = history[-1] if history else None
    return {
        "ready": ready,
        "job": job,
        "picks": good["picks"] if good else [],
        "picked_at": good["ts"] if good else None,
        "runs": good["runs"] if good else [],
        "cached": bool(good and last and last is not good),
        "error": last.get("error") if last and last.get("status") != "ok" else None,
        "previous": [summary(r) for r in reversed(history[-HISTORY_SHOWN:])],
    }


def find_pick(history, quest_id):
    """The quest of a pick from the last good request, or None."""
    good = next((r for r in reversed(history) if r.get("status") == "ok" and r.get("picks")), None)
    for pick in (good or {}).get("picks") or []:
        if pick.get("quest", {}).get("id") == quest_id:
            return pick["quest"]
    return None
