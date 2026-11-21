#!/usr/bin/env python3
"""fake_gary.py - a stand-in for Gary, for the tests of gary_io.py and
start_gary.sh. It does what the real one does at its edges, with no camera
and no model:

    writes gary.pid, appends one journal line per SIGUSR1 (a Sniff Test),
    stops cleanly on SIGTERM and removes gary.pid.

    python3 fake_gary.py [folder]        (default: the current folder)
"""
import json
import os
import signal
import sys
import time

folder = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "."
pid_path = os.path.join(folder, "gary.pid")
journal = os.path.join(folder, "journal.jsonl")
state = {"asked": 0, "written": 0, "run": True}


def on_sniff(*_):
    state["asked"] += 1


def on_stop(*_):
    state["run"] = False


signal.signal(signal.SIGUSR1, on_sniff)
signal.signal(signal.SIGTERM, on_stop)
signal.signal(signal.SIGINT, on_stop)
signal.signal(signal.SIGHUP, lambda *_: None)  # "reload the quests"
with open(pid_path, "w", encoding="utf-8") as f:
    f.write("%d\n" % os.getpid())
print("fake Gary is awake", flush=True)
try:
    while state["run"]:
        while state["written"] < state["asked"]:
            state["written"] += 1
            n = state["written"]
            line = {"id": "fake-%d-%d" % (os.getpid(), n), "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "type": "discovery", "device": "fake", "label": "bottle", "score": 0.9, "friend": False,
                    "new": n == 1, "quest_id": None, "latency_ms": 12.0}
            with open(journal, "a", encoding="utf-8") as f:
                f.write(json.dumps(line) + "\n")
                f.flush()
                os.fsync(f.fileno())
            print("SNIFF %d" % n, flush=True)
        time.sleep(0.01)
finally:
    try:
        os.remove(pid_path)
    except OSError:
        pass
