#!/usr/bin/env python3
"""personal.py - picks for you: places a TinyFish agent chooses from live pages.

The scout (scout.py) reads the same pages for everyone. This reads them for
one explorer: what Gary has found with you, the places you have already been,
whether you usually pick short or long, and which known place you are near.
That goes into the TinyFish agent's goal, so the agent itself chooses from
the page with you in mind and says, from the page, why each place suits you.

TinyFish is the only source. Nothing here writes a place, a description or a
reason: every pick is a place the agent read on a live page, turned into a
quest by the scout's own code and passed by the scout's own checks. The
ranking below only puts those in order. If TinyFish fails, the result says
so; it is never filled in from anywhere else.

    python3 scout/personal.py --dry-run                 # one live request from the example state; prints the picks
    python3 scout/personal.py --api http://localhost:8000 --near "Gibbons Park"

The web page asks for picks through the backend (POST /api/picks), which runs
the same code. Standard library only.
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import re
import sys
import time
import urllib.request
import uuid
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import scout  # noqa: E402

PAGES = 2            # live pages read for one request, at the same time
WAIT = 150           # seconds one page may take before it is given up on
PER_PAGE = 6         # places asked for, and quests made, per page
MAX_PICKS = 5        # picks returned
LIKES_MAX = 4        # things named as what you like finding
BEEN_MAX = 12        # places named as already visited
WHY_MAX = 160        # characters of the agent's reason that are kept
NATURE = {"bird", "duck", "goose", "squirrel", "tree", "rabbit", "deer", "butterfly", "mushroom", "flower"}
LONG_KINDS = ("trails",)


def plural(label):
    return label + ("es" if label.endswith(("s", "sh", "ch")) else "s")


def one_line(text, limit):
    """Plain text from a page: one line, printable, at most `limit` characters."""
    text = " ".join("".join(ch if ch.isprintable() else " " for ch in str(text or "")).split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


# --------------------------------------------------------------------------
# The context: what Gary knows about you, from his own state
# --------------------------------------------------------------------------
def build_context(state, choices=(), previous=(), near=None):
    """Who the picks are for, from what Gary already keeps. No mood, no
    position: `near` is the name of a known place, worked out in the browser.

    state     GET /api/state (journal, map)
    choices   "short" / "long", one per press of the buttons, oldest first
    previous  earlier pick records, oldest first
    """
    journal = state.get("journal") or []
    counts = Counter(str(f["label"]) for f in journal if f.get("label"))
    likes = [label for label, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))][:LIKES_MAX]
    been = sorted({t["place"] for t in state.get("map") or [] if t.get("place") and (t.get("cleared") or t.get("visited"))})
    times = Counter(c for c in choices if c in ("short", "long")).most_common()
    prefers = times[0][0] if times and (len(times) == 1 or times[0][1] > times[1][1]) else None
    suggested = []
    for record in list(previous)[-5:]:
        for pick in record.get("picks") or []:
            if pick.get("place") and pick["place"] not in suggested:
                suggested.append(pick["place"])
    return {
        "likes": likes,
        "prefers": prefers,
        "been": been[:BEEN_MAX],
        "near": one_line(near, 80) or None if near else None,
        "with_friend": any(f.get("friend") for f in journal),
        "suggested": suggested[-10:],
    }


def choose_pages(sources, context, pages=PAGES):
    """Which live pages to read for this explorer. Their usual length first;
    trails and natural areas for someone who likes animals and trees; the
    events pages last, because they are the slowest and give the fewest places."""
    def score(item):
        n, source = item
        s = 0.0
        if context.get("prefers") and source.get("time") == context["prefers"]:
            s += 2
        if source.get("kind") in LONG_KINDS and NATURE & set(context.get("likes") or []):
            s += 1
        if source.get("kind") == "events":
            s -= 1.5
        return (-s, n)
    return [source for _, source in sorted(enumerate(sources), key=score)[:pages]]


def personal_goal(source, context):
    """The page's own goal, then who this list is for. The JSON form at the
    end asks for one more field, "why", taken from the page."""
    facts = []
    if context.get("likes"):
        facts.append("They like finding %s." % " and ".join(plural(x) for x in context["likes"]))
    if context.get("prefers") == "short":
        facts.append("They usually pick short outings, about 15 minutes.")
    elif context.get("prefers") == "long":
        facts.append("They usually pick longer walks, about 40 minutes.")
    if context.get("been"):
        facts.append("They have already been to %s, so prefer places they have not been to." % ", ".join(context["been"]))
    if context.get("near"):
        facts.append("They are near %s in London, Ontario; nearer is better." % context["near"])
    if context.get("with_friend"):
        facts.append("They often go with a friend.")
    if not facts:
        facts.append("They are new: prefer easy, welcoming places.")
    return (source["goal"] + " This list is for one explorer. " + " ".join(facts) +
            " Put the places that suit them best first. Only list places that are on this page. For each place "
            "also give \"why\": one short sentence, using only what this page says, on why it suits them. "
            "Return JSON in the form {\"places\": [{\"name\": ..., \"address\": ..., \"about\": ..., \"why\": ...}]}.")


# --------------------------------------------------------------------------
# One request: live pages in, ranked picks out
# --------------------------------------------------------------------------
def _read(source, context, api_key, run, endpoint, wait):
    """One TinyFish run on one page. Never raises: a failure is in the result."""
    steps, seen, started = [], {}, time.monotonic()
    out = {"source": source["name"], "kind": source.get("kind"), "url": source["url"]}
    try:
        final = run(source["url"], personal_goal(source, context), api_key, lambda text: None, steps, seen,
                    endpoint, wait)
    except RuntimeError as exc:  # scout.Refused is a RuntimeError too
        out.update(status="FAILED", error=str(exc)[:300], refused=isinstance(exc, scout.Refused),
                   run_id=seen.get("run_id"), streaming_url=seen.get("streaming_url"))
    else:
        places = scout.find_places(final.get("result")) or scout.find_places(
            {k: v for k, v in final.items() if k not in ("type", "status", "run_id", "streaming_url")})
        out.update(status="COMPLETED", run_id=final.get("run_id"), streaming_url=final.get("streaming_url"),
                   places=places)
    out["steps"] = steps
    out["seconds"] = round(time.monotonic() - started, 1)
    return out


def rank(candidates, context):
    """Put the agent's places in order for this explorer. Only orders: every
    pick is one of `candidates`, and every reason is either one of the plain
    reasons below or the agent's own words from the page."""
    been = {scout.place_key(p) for p in context.get("been") or []}
    near = scout.place_key(context.get("near") or "")
    suggested = {scout.place_key(p) for p in context.get("suggested") or []}
    likes = set(context.get("likes") or [])
    ranked = []
    for c in candidates:
        quest, key = c["quest"], scout.place_key(c["quest"]["place"])
        score, reasons = 1.0 / (1 + c["order"]), []  # the agent's own order for this person comes first
        if key in been:
            score -= 1
            reasons.append("You have been here")
        else:
            score += 3
            reasons.append("New to you")
        if quest["target"] in likes:
            score += 2
            reasons.append("You like finding %s" % plural(quest["target"]))
        if context.get("prefers") and quest["time"] == context["prefers"]:
            score += 1.5
            reasons.append("A short outing, like you usually pick" if quest["time"] == "short"
                           else "A longer walk, like you usually pick")
        if near and near == key:
            score += 1
            reasons.append("You are near here")
        if quest.get("herd") and context.get("with_friend"):
            score += 0.5
            reasons.append("One for you and a friend")
        if key in suggested and key not in been:
            score -= 0.75  # suggested before and not taken up: give the others a turn
        ranked.append(dict(c, score=round(score, 3), reasons=reasons))
    ranked.sort(key=lambda r: (-r["score"], r["order"]))
    return ranked


def run_picks(context, sources, api_key, allowed, day, endpoint=scout.TINYFISH_URL, wait=WAIT,
              run=scout.run_agent, pages=PAGES, max_picks=MAX_PICKS):
    """One request for picks. -> a record: what was asked, every TinyFish run
    (id, live view, status), and the picks. status is "ok" (picks found),
    "empty" (the pages answered, nothing passed the checks) or "failed"."""
    chosen = choose_pages(sources, context, pages)
    record = {"id": "pick-" + uuid.uuid4().hex[:12],
              "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "context": context, "runs": [], "picks": []}
    if not api_key:
        record.update(status="failed", error="TinyFish is not set up: TINYFISH_API_KEY is missing")
        return record
    with concurrent.futures.ThreadPoolExecutor(max(1, len(chosen))) as pool:
        reads = list(pool.map(lambda s: _read(s, context, api_key, run, endpoint, wait), chosen))

    candidates, taken, made = [], set(), []
    for source, read in zip(chosen, reads):
        summary = {k: read.get(k) for k in ("source", "kind", "url", "status", "error", "run_id",
                                            "streaming_url", "seconds", "steps")}
        summary["places"] = [scout.clean_name(p.get("name")) for p in read.get("places") or [] if isinstance(p, dict)][:20]
        record["runs"].append(summary)
        if read["status"] != "COMPLETED":
            continue
        places = read["places"]
        quests, dropped = scout.build_quests(places, source, day, allowed, PER_PAGE, taken, len(made))
        record["runs"][-1]["dropped"] = dropped
        made.extend(quests)
        words = {scout.place_key(scout.clean_name(p.get("name"))): p for p in places if isinstance(p, dict)}
        for quest in quests:
            place = words.get(scout.place_key(quest["place"]), {})
            why = one_line(place.get("why"), WHY_MAX)
            order = next((n for n, p in enumerate(places) if isinstance(p, dict) and
                          scout.place_key(scout.clean_name(p.get("name"))) == scout.place_key(quest["place"])), 99)
            candidates.append({"quest": quest, "order": order, "source": source["name"], "run_id": read.get("run_id"),
                               "why": why if why and not scout.risk_in(why) else None,
                               "about": one_line(quest.get("_about"), 200) or None})

    good, refused = scout.check_quests([c["quest"] for c in candidates], allowed)
    passed = {id(q) for q in good}
    candidates = [c for c in candidates if id(c["quest"]) in passed]
    for c in candidates:
        for name in [k for k in c["quest"] if k.startswith("_")]:
            del c["quest"][name]
    record["refused"] = [{"place": q.get("place"), "why": why} for q, why in refused]

    record["picks"] = [{"place": c["quest"]["place"], "quest": c["quest"], "why": c["why"], "about": c["about"],
                        "reasons": c["reasons"], "score": c["score"], "source": c["source"], "run_id": c["run_id"]}
                       for c in rank(candidates, context)[:max_picks]]
    errors = ["%s: %s" % (r["source"], r["error"]) for r in reads if r["status"] != "COMPLETED"]
    if record["picks"]:
        record["status"] = "ok"
    elif any(r["status"] == "COMPLETED" for r in reads):
        record["status"] = "empty"
        record["error"] = "TinyFish read the pages, but no place passed Gary's checks"
    else:
        record["status"] = "failed"
        record["error"] = "; ".join(errors) or "TinyFish did not answer"
    if errors and record["status"] != "failed":
        record["partial"] = errors
    record["refused_key"] = any(r.get("refused") for r in reads)
    return record


# --------------------------------------------------------------------------
def main(argv=None):
    scout.load_settings()
    ap = argparse.ArgumentParser(description="Picks for you: a TinyFish agent chooses from live pages")
    ap.add_argument("--api", default=os.environ.get("GARY_API"), help="read Gary's state from this backend")
    ap.add_argument("--state", default=os.path.join(scout.ROOT, "contract", "examples", "state.json"),
                    help="a state file to use when no --api is given")
    ap.add_argument("--near", help="the name of a known place you are near")
    ap.add_argument("--pages", type=int, default=PAGES)
    ap.add_argument("--wait", type=int, default=WAIT)
    ap.add_argument("--dry-run", action="store_true", help="print the request and the picks (the default here)")
    ap.add_argument("--sources", default=os.path.join(HERE, "sources.json"))
    ap.add_argument("--tinyfish-url", default=scout.TINYFISH_URL, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.api:
        with urllib.request.urlopen(args.api.rstrip("/") + "/api/state", timeout=10) as reply:
            state = json.loads(reply.read().decode("utf-8"))
    else:
        with open(args.state, "r", encoding="utf-8") as f:
            state = json.load(f)
    with open(args.sources, "r", encoding="utf-8") as f:
        sources = json.load(f)
    key = os.environ.get("TINYFISH_API_KEY")
    if not key:
        sys.exit("Set TINYFISH_API_KEY in scout/.env or your shell first.")
    context = build_context(state, near=args.near)
    print("For: %s" % json.dumps(context))
    print("Reading: %s" % ", ".join(s["name"] for s in choose_pages(sources, context, args.pages)), flush=True)
    record = run_picks(context, sources, key, scout.load_labels(), scout.today(), args.tinyfish_url, args.wait,
                       pages=args.pages)
    for r in record["runs"]:
        print("  %s: %s%s, run %s (%s s)" % (r["source"], r["status"], "" if r["status"] == "COMPLETED" else " - " + str(r["error"]),
                                             r["run_id"], r["seconds"]))
    for n, pick in enumerate(record["picks"], 1):
        print("%d. %s  [%s]" % (n, pick["quest"]["title"], ", ".join(pick["reasons"])))
        if pick["why"]:
            print("   the page: %s" % pick["why"])
    print("Status: %s%s" % (record["status"], " - " + record["error"] if record.get("error") else ""))
    return 0 if record["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
