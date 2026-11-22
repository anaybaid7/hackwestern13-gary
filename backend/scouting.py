"""Run the scout from the backend: once a day, and when the page asks.

scout/scout.py runs as its own process (it takes minutes and talks to
TinyFish), posting its quests back to this backend like it always has. Only
one run at a time. Its output goes to scout/last_run.log.

    GARY_SCOUT_AT    a local time, "07:00": run the scout every day then. Unset: never on its own
    GARY_SELF_URL    this backend, for the scout to post to. Default http://127.0.0.1:8000
"""
import datetime as dt
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

SCOUT = Path(os.environ.get("GARY_SCOUT_DIR") or Path(__file__).resolve().parent.parent / "scout")
TIMEOUT = 20 * 60  # seconds: TinyFish waits up to 5 min a page

_lock = threading.Lock()
status = {"running": False, "started": None, "finished": None, "ok": None, "why": None}


def available():
    return (SCOUT / "scout.py").is_file()


def _run(runner):
    try:
        ok = runner() == 0
    except Exception:  # a broken run must never take the backend down
        ok = False
    with _lock:
        status.update(running=False, finished=time.time(), ok=ok)


def default_runner():
    with open(SCOUT / "last_run.log", "w", encoding="utf-8") as log:
        return subprocess.run([sys.executable, str(SCOUT / "scout.py"), "--api",
                               os.environ.get("GARY_SELF_URL") or "http://127.0.0.1:8000"],
                              cwd=str(SCOUT), stdout=log, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, timeout=TIMEOUT).returncode


def start(why, runner=None, wait=False):
    """Start a run unless one is going. -> True if this call started it."""
    with _lock:
        if status["running"]:
            return False
        status.update(running=True, started=time.time(), finished=None, ok=None, why=why)
    thread = threading.Thread(target=_run, args=(runner or default_runner,), daemon=True)
    thread.start()
    if wait:
        thread.join()
    return True


def due(at, now, last_day):
    """Is the daily run due? `at` is "HH:MM", `now` a local datetime."""
    try:
        hour, minute = (int(x) for x in str(at).split(":"))
    except ValueError:
        return False
    return now.date() != last_day and (now.hour, now.minute) >= (hour, minute)


def schedule(tz):
    """Run the scout every day at GARY_SCOUT_AT, in the background."""
    at = os.environ.get("GARY_SCOUT_AT")
    if not at or not available():
        return

    def loop():
        now = dt.datetime.now(tz)
        last_day = now.date() if due(at, now, None) else None  # started after the time: not again today
        while True:
            now = dt.datetime.now(tz)
            if due(at, now, last_day):
                last_day = now.date()
                start("daily")
            time.sleep(60)

    threading.Thread(target=loop, daemon=True).start()
