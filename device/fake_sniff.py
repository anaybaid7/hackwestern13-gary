#!/usr/bin/env python3
"""fake_sniff.py - pretend to be Gary. Posts one event straight to the backend,
so the backend and the web page can be built and demoed with no device at all.
Standard library only.

    python3 fake_sniff.py bench                 # Gary sniffed a bench
    python3 fake_sniff.py bench --friend        # ...with a friend in frame (Herd Mode)
    python3 fake_sniff.py bottle --quest q-demo-bottle
    python3 fake_sniff.py --miss                # a sniff that found nothing
    python3 fake_sniff.py --mood before 3       # a private mood check-in
    python3 fake_sniff.py dog --api http://my-server:8000

The thing must be a name from contract/labels.json (bench, dog, bird, bottle ...).
"""
import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request


def main():
    ap = argparse.ArgumentParser(description="Post one pretend sniff to the backend")
    ap.add_argument("label", nargs="?", help="what Gary sniffed, for example bench")
    ap.add_argument("--friend", action="store_true", help="a friend was in the frame")
    ap.add_argument("--quest", help="the quest id the device thinks this completes")
    ap.add_argument("--miss", action="store_true", help="a sniff that named nothing")
    ap.add_argument("--mood", nargs=2, metavar=("PHASE", "VALUE"), help="before or after, and 1 to 5")
    ap.add_argument("--score", type=float, default=0.9)
    ap.add_argument("--device", default="fake")
    ap.add_argument("--api", default=os.environ.get("GARY_API", "http://localhost:8000"))
    args = ap.parse_args()

    now = datetime.datetime.now(datetime.timezone.utc)
    event = {
        "id": "%s-%d-%d" % (args.device, int(now.timestamp() * 1000), os.getpid()),
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "device": args.device,
    }
    if args.mood:
        event.update(type="mood", phase=args.mood[0], value=int(args.mood[1]))
    elif args.miss:
        event.update(type="miss", friend=args.friend, latency_ms=40.0)
    elif args.label:
        event.update(type="discovery", label=args.label.lower(), score=args.score, friend=args.friend,
                     new=True, quest_id=args.quest, latency_ms=40.0)
    else:
        ap.error("say what Gary sniffed, or use --miss or --mood")

    req = urllib.request.Request(args.api.rstrip("/") + "/api/events",
                                 data=json.dumps({"events": [event]}).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as reply:
            out = json.loads(reply.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        sys.exit("The backend refused it: HTTP %d %s" % (exc.code, exc.read().decode("utf-8", "replace")))
    except OSError as exc:
        sys.exit("Could not reach %s (%s). Is the backend running?" % (args.api, exc))

    result = (out.get("results") or [{}])[0]
    print("sent: %s" % json.dumps(event))
    print("backend says: %s, +%s XP%s" % (result.get("reaction"), result.get("xp"),
                                         ", quest %s done" % result["quest_id"] if result.get("quest_id") else ""))


if __name__ == "__main__":
    main()
