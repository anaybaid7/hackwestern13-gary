#!/usr/bin/env python3
"""scout.py - Gary's scout.

A TinyFish web agent reads live local pages and comes back with real places.
This script turns each place into a quest Gary can confirm with a Sniff Test,
and sends the quests to the backend. Standard library only.

    export TINYFISH_API_KEY=...            # free student credits: tinyfish.ai/students
    python3 scout/scout.py --dry-run       # live run on the first source, print the quests
    python3 scout/scout.py                 # live run, then POST the quests to the backend
    python3 scout/scout.py --all           # every source in sources.json

    # No key? Build quests from a saved agent reply instead:
    python3 scout/scout.py --from-file scout/sample_result.json --dry-run

Every live run is written to scout/runs.jsonl (run id, page, live-view link,
quests). That file is the evidence that the agent worked on live sites.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TINYFISH_URL = "https://agent.tinyfish.ai/v1/automation/run-sse"

# What to look for at a place. The first rule whose words appear in the place's
# name or description wins. Every target must be an outdoor name in
# contract/labels.json, because the Sniff Test is what confirms the quest.
TARGET_RULES = [
    (("off-leash", "off leash", "dog park", "dogs"), "dog"),
    (("skate",), "skateboard"),
    (("soccer", "baseball", "tennis", "cricket", "volleyball", "sports field", "diamond", "courts"), "sports ball"),
    (("boat", "canoe", "kayak", "rowing", "dock", "reservoir", "marina"), "boat"),
    (("bike", "bicycle", "cycling", "parkway", "paved path", "multi-use"), "bicycle"),
    (("bird", "pond", "wetland", "marsh", "bog", "woods", "forest", "meadow", "natural area", "trail"), "bird"),
    (("garden", "playground", "picnic", "seating", "accessible", "plaza"), "bench"),
]
FALLBACK_TARGETS = ["bench", "bird", "dog", "bicycle"]
LONG_WORDS = ("trail", "hike", "hiking", "woods", "forest", "conservation", "bog", "ponds", "meadow", "valley")
HERD_EVERY = 3  # every third quest is a co-op quest: it needs a friend in frame


def load_labels():
    """Names Gary can recognise outdoors, from the contract."""
    with open(os.path.join(ROOT, "contract", "labels.json"), "r", encoding="utf-8") as f:
        doc = json.load(f)
    return {item["name"] for item in doc["labels"] if item["outdoor"]}


# --------------------------------------------------------------------------
# TinyFish
# --------------------------------------------------------------------------
def parse_sse(lines, on_event=None):
    """Read a TinyFish event stream. Returns the final COMPLETE event, with the
    live-view link added as 'streaming_url' when the stream carried one."""
    final, streaming_url = None, None
    for raw in lines:
        line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
        line = line.strip()
        if not line.startswith("data:"):
            continue
        try:
            event = json.loads(line[5:].strip())
        except ValueError:
            continue
        if on_event:
            on_event(event)
        if event.get("type") == "STREAMING_URL":
            streaming_url = event.get("streaming_url")
        if event.get("type") == "COMPLETE":
            final = event
            break
    if final is not None and streaming_url:
        final.setdefault("streaming_url", streaming_url)
    return final


def run_agent(url, goal, api_key, say):
    """One TinyFish run. Returns the COMPLETE event. Raises RuntimeError with a
    plain message when the run cannot start or does not finish."""
    body = json.dumps({"url": url, "goal": goal}).encode("utf-8")
    req = urllib.request.Request(TINYFISH_URL, data=body, headers={
        "X-API-Key": api_key, "Content-Type": "application/json", "Accept": "text/event-stream"})

    def show(event):
        kind = event.get("type")
        if kind == "STARTED":
            say("  agent started, run %s" % event.get("run_id"))
        elif kind == "STREAMING_URL":
            say("  watch it live: %s" % event.get("streaming_url"))
        elif kind == "PROGRESS" and event.get("purpose"):
            say("  ... %s" % event["purpose"])

    try:
        with urllib.request.urlopen(req, timeout=180) as reply:
            final = parse_sse(reply, show)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        hints = {401: "the API key is missing or wrong", 402: "the account has no balance",
                 403: "no credits or no active plan"}
        raise RuntimeError("TinyFish refused the run: HTTP %d (%s). %s"
                           % (exc.code, hints.get(exc.code, "see the reply"), detail))
    except OSError as exc:
        raise RuntimeError("could not reach TinyFish: %s" % exc)
    if final is None:
        raise RuntimeError("the stream ended without a COMPLETE event")
    if final.get("status") != "COMPLETED":
        raise RuntimeError("the run ended as %s: %s" % (final.get("status"), final.get("error")))
    return final


# --------------------------------------------------------------------------
# Places -> quests
# --------------------------------------------------------------------------
def find_places(result):
    """The agent is asked for {"places": [{"name": ...}]}, but replies vary.
    Take the first list of objects that have a name."""
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return []
    if isinstance(result, list):
        if result and all(isinstance(item, dict) and item.get("name") for item in result):
            return result
        for item in result:
            found = find_places(item)
            if found:
                return found
    if isinstance(result, dict):
        for value in result.values():
            found = find_places(value)
            if found:
                return found
    return []


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def article(word):
    return "an" if word[:1] in "aeiou" else "a"


def pick_target(text, index, allowed):
    lowered = text.lower()
    for words, target in TARGET_RULES:
        if target in allowed and any(word in lowered for word in words):
            return target
    choices = [t for t in FALLBACK_TARGETS if t in allowed] or sorted(allowed)
    return choices[index % len(choices)]


def build_quests(places, source, day, allowed, limit=3):
    """Turn agent places into contract Quests. One quest per place, at most `limit`."""
    quests, seen = [], set()
    for place in places:
        name = str(place.get("name") or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        about = " ".join(str(place.get(key) or "") for key in ("about", "description", "features", "address"))
        text = name + " " + about
        target = pick_target(text, len(quests), allowed)
        is_long = source.get("time") == "long" or any(word in text.lower() for word in LONG_WORDS)
        herd = (len(quests) + 1) % HERD_EVERY == 0
        title = "Find %s %s at %s" % (article(target), target, name)
        if herd:
            title += ", with a friend"
        quests.append({
            "id": "q-%s-%s-%s" % (day, slug(name), slug(target)),
            "title": title,
            "place": name,
            "time": "long" if is_long else "short",
            "minutes": 40 if is_long else 15,
            "target": target,
            "xp": 40 if is_long else 20,
            "herd": herd,
            "source": "tinyfish",
            "source_url": place.get("url") or source.get("url"),
            "day": day,
        })
        if len(quests) >= limit:
            break
    return quests


def post_quests(api, quests):
    headers = {"Content-Type": "application/json"}
    if os.environ.get("SCOUT_KEY"):
        headers["X-Scout-Key"] = os.environ["SCOUT_KEY"]
    req = urllib.request.Request(api.rstrip("/") + "/api/quests",
                                 data=json.dumps({"quests": quests}).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=10) as reply:
        return json.loads(reply.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser(description="Gary's scout: live pages in, quests out")
    ap.add_argument("--dry-run", action="store_true", help="print the quests, send nothing")
    ap.add_argument("--all", action="store_true", help="run every source, not only the first")
    ap.add_argument("--source", help="run only the source with this name")
    ap.add_argument("--max", type=int, default=3, help="quests per source (default 3)")
    ap.add_argument("--from-file", help="use a saved agent reply in place of a live run")
    ap.add_argument("--sources", default=os.path.join(HERE, "sources.json"))
    ap.add_argument("--api", default=os.environ.get("GARY_API", "http://localhost:8000"), help="backend address")
    ap.add_argument("--runs", default=os.path.join(HERE, "runs.jsonl"), help="where live runs are recorded")
    args = ap.parse_args()

    def say(text):
        print(text, flush=True)

    allowed = load_labels()
    day = datetime.date.today().isoformat()
    with open(args.sources, "r", encoding="utf-8") as f:
        sources = json.load(f)
    if args.source:
        sources = [s for s in sources if s["name"] == args.source]
        if not sources:
            sys.exit("no source named %r in %s" % (args.source, args.sources))
    elif not args.all:
        sources = sources[:1]

    quests = []
    if args.from_file:
        with open(args.from_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        places = find_places(saved.get("result", saved) if isinstance(saved, dict) else saved)
        say("%d places from %s (a saved reply, not a live run)" % (len(places), args.from_file))
        quests = build_quests(places, {"url": None}, day, allowed, args.max)
    else:
        key = os.environ.get("TINYFISH_API_KEY")
        if not key:
            sys.exit("Set TINYFISH_API_KEY first (free student credits: tinyfish.ai/students),\n"
                     "or try: python3 scout/scout.py --from-file scout/sample_result.json --dry-run")
        for source in sources:
            say("Scouting %s\n  %s" % (source["name"], source["url"]))
            record = {"ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "source": source["name"], "url": source["url"]}
            try:
                final = run_agent(source["url"], source["goal"], key, say)
            except RuntimeError as exc:
                say("  FAILED: %s" % exc)
                record.update(status="FAILED", error=str(exc))
            else:
                places = find_places(final.get("result"))
                found = build_quests(places, source, day, allowed, args.max)
                say("  %d places -> %d quests" % (len(places), len(found)))
                quests.extend(found)
                record.update(status="COMPLETED", run_id=final.get("run_id"),
                              streaming_url=final.get("streaming_url"), places=len(places),
                              quests=[q["id"] for q in found])
            with open(args.runs, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")

    if not quests:
        sys.exit("No quests came out of this run.")
    if args.dry_run:
        say(json.dumps({"quests": quests}, indent=2))
        say("\n%d quests. Dry run: nothing was sent." % len(quests))
        return
    try:
        out = post_quests(args.api, quests)
    except urllib.error.HTTPError as exc:
        sys.exit("The backend refused the quests: HTTP %d %s" % (exc.code, exc.read().decode("utf-8", "replace")))
    except OSError as exc:
        sys.exit("Could not reach the backend at %s (%s). Use --dry-run to only print." % (args.api, exc))
    say("Backend accepted %d quests: %s" % (len(out.get("accepted", [])), ", ".join(out.get("accepted", []))))
    for bad in out.get("rejected", []):
        say("  refused %s: %s" % (bad.get("id"), bad.get("why")))


if __name__ == "__main__":
    main()
