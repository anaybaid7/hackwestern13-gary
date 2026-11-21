#!/usr/bin/env python3
"""sync.py - joins the device to the backend. Standard library only, so it
runs on QNX's Python 3 as well as on a laptop.

Every few seconds it does two things:

  1. Uploads new lines of journal.jsonl to   POST /api/events
  2. Fetches today's quests from             GET  /api/quests
     and, if they changed, rewrites quests.tsv and tells Gary to reload.

It remembers how far it got in sync.state. With no network it simply waits:
Gary keeps working from his journal and his cached quests, and everything is
uploaded later. No event is lost, and none is counted twice.

    python3 sync.py --api http://192.168.1.20:8000     # keep running
    python3 sync.py --api http://localhost:8000 --once  # one pass, then exit
"""
import argparse
import datetime
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BATCH = 100
TIMEOUT = 5


def call(api, path, body=None):
    """One JSON request. Returns the decoded reply, or raises OSError."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(api.rstrip("/") + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as reply:
        return json.loads(reply.read().decode("utf-8"))


def clock():
    """This device's clock right now. Sent with every upload as "sent_at": a Pi
    that booted without a network does not know the time, and the backend uses
    this to put the journal's timestamps right."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def load_state(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"offset": 0}


def save_state(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def upload_journal(api, journal_path, state_path, say):
    """Send every complete, not-yet-sent journal line. Returns how many went."""
    state = load_state(state_path)
    if not os.path.exists(journal_path):
        return 0
    if os.path.getsize(journal_path) < state.get("offset", 0):
        state["offset"] = 0  # the journal was replaced; the server ignores repeats
    sent = 0
    with open(journal_path, "rb") as f:
        f.seek(state.get("offset", 0))
        while True:
            events, size = [], 0
            while len(events) < BATCH:
                line = f.readline()
                if not line.endswith(b"\n"):
                    break  # end of file, or a line still being written
                size += len(line)
                try:
                    event = json.loads(line.decode("utf-8"))
                except ValueError:
                    continue  # a torn line from a power cut: skip it for good
                if isinstance(event, dict) and event.get("id") and event.get("type"):
                    events.append(event)
            if not size:
                break
            if events:
                try:
                    call(api, "/api/events", {"events": events, "sent_at": clock()})
                except urllib.error.HTTPError as exc:
                    if exc.code >= 500:
                        raise
                    # The server refused the batch. Send one by one so a single
                    # bad line cannot block the rest for ever.
                    for event in events:
                        try:
                            call(api, "/api/events", {"events": [event], "sent_at": clock()})
                        except urllib.error.HTTPError as one:
                            say("server refused event %s: HTTP %d" % (event.get("id"), one.code))
            state["offset"] = state.get("offset", 0) + size
            save_state(state_path, state)
            sent += len(events)
    return sent


def quests_as_tsv(quests, api):
    lines = [
        "# Written by sync.py from %s. Edit by hand only when sync.py is not running." % api,
        "# Columns are separated by TABs: id, target, xp, text, and optionally \"herd\".",
    ]
    for q in quests:
        cols = [str(q["id"]), str(q["target"]), str(q.get("xp", 0)),
                str(q.get("title") or "Find a " + q["target"]).replace("\t", " ")]
        if q.get("herd"):
            cols.append("herd")
        lines.append("\t".join(cols))
    return "\n".join(lines) + "\n"


def fetch_quests(api, quests_path, pid_path):
    """Rewrite quests.tsv if the backend's quests changed. Returns True if it did."""
    quests = call(api, "/api/quests").get("quests", [])
    text = quests_as_tsv(quests, api)
    try:
        with open(quests_path, "r", encoding="utf-8") as f:
            if f.read() == text:
                return False
    except OSError:
        pass
    tmp = quests_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, quests_path)
    # Tell a running Gary to reload. It is fine if he is not running.
    try:
        with open(pid_path, "r", encoding="utf-8") as f:
            os.kill(int(f.read().strip()), signal.SIGHUP)
    except (OSError, ValueError, AttributeError):
        pass
    return True


def main():
    ap = argparse.ArgumentParser(description="Upload Gary's journal and fetch his quests")
    ap.add_argument("--api", default=os.environ.get("GARY_API", "http://localhost:8000"),
                    help="backend address (or set GARY_API)")
    ap.add_argument("--dir", default=HERE, help="the device folder (journal.jsonl, quests.tsv, gary.pid)")
    ap.add_argument("--interval", type=float, default=3.0, help="seconds between passes")
    ap.add_argument("--once", action="store_true", help="one pass, then exit (exit code 1 if offline)")
    ap.add_argument("--no-quests", action="store_true", help="upload only; leave quests.tsv alone")
    args = ap.parse_args()

    journal = os.path.join(args.dir, "journal.jsonl")
    state = os.path.join(args.dir, "sync.state")
    quests = os.path.join(args.dir, "quests.tsv")
    pid = os.path.join(args.dir, "gary.pid")

    def say(text):
        print(time.strftime("%H:%M:%S"), text, flush=True)

    say("syncing %s with %s" % (args.dir, args.api))
    offline = False
    while True:
        try:
            sent = upload_journal(args.api, journal, state, say)
            if sent:
                say("uploaded %d event%s" % (sent, "" if sent == 1 else "s"))
            if not args.no_quests and fetch_quests(args.api, quests, pid):
                say("quests updated")
            if offline:
                say("back online")
            offline = False
        except (OSError, ValueError) as exc:  # no network, server down, bad reply
            if not offline:
                say("offline (%s). Gary carries on; will retry." % exc)
            offline = True
        if args.once:
            return 1 if offline else 0
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
