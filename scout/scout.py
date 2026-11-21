#!/usr/bin/env python3
"""scout.py - Gary's scout.

A TinyFish web agent reads live local pages (parks, trails, events) and comes
back with real places. This script turns each place into a quest that Gary can
confirm with a Sniff Test, checks it, and sends the quests to the backend.
Standard library only.

    # Put TINYFISH_API_KEY=... in scout/.env, or export it in your shell.
    python3 scout/scout.py --one --dry-run # one live run on the first source; print, send nothing
    python3 scout/scout.py                 # the day's quests: every source, then POST to the backend
    python3 scout/scout.py --source events # only the sources whose name contains "events"
    python3 scout/scout.py --report        # write scout/EVIDENCE.md from the recorded runs

    # No key, or TinyFish is slow during judging:
    python3 scout/scout.py --cached        # post the quests from the last good live run
    python3 scout/scout.py --from-file scout/sample_result.json --dry-run

Every live run is written to scout/runs.jsonl: the TinyFish run id, the page,
the live-view link, what the agent did, the quests, and what was dropped and
why. That file is the evidence that the agent worked on live sites.

Checks every quest passes before it is sent (issue #32):
  - its target is a thing Gary's on-device model can name
  - one quest per place
  - no place that is closed, private, under construction or on risky ground
  - a note that says where to stand: "any safe, accessible spot"
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TINYFISH_URL = "https://agent.tinyfish.ai/v1/automation/run-sse"
# Where a place really is, so the web page can tell when you are there.
# OpenStreetMap's Nominatim: at most one request a second, a named client.
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
LONDON_BOX = "-81.45,43.10,-81.10,42.88"  # west, north, east, south: London, Ontario
GEO_AGENT = "gary-scout/0.1 (hackathon project)"


def load_settings(path=None, environ=None):
    """Read scout/.env without replacing shell settings or executing its contents."""
    environ = os.environ if environ is None else environ
    if environ.get("GARY_NO_ENV_FILE"):
        return
    path = os.path.join(HERE, ".env") if path is None else path
    try:
        with open(path, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        environ.setdefault(key, value)


# What to look for at a place. The first rule whose words appear in the place's
# name or description wins. Every target must be an outdoor name in
# contract/labels.json, because the Sniff Test is what confirms the quest.
# Only things that are there in any season: a quest nobody can finish is no
# fun. So no "sports ball" for a tennis court and no flower or butterfly in
# November. And only things Gary names well (device/bench_results.md): no
# bench, dog or goose, which he gets about one time in four.
# A rule may name several things; each place always gets the same one of them.
TARGET_RULES = [
    (("bike", "bicycle", "cycling", "parkway", "paved path", "multi-use"), ("bicycle",)),
    (("pond", "wetland", "marsh", "bog", "lake"), ("duck",)),
    (("wood", "forest", "meadow", "natural area", "trail", "valley"), ("tree", "squirrel")),
    (("river", "creek"), ("duck",)),
    (("bird",), ("bird",)),
    (("garden", "playground", "picnic", "seating", "accessible", "plaza", "market", "square", "festival", "lights",
      "park"), ("tree", "squirrel")),
]
FALLBACK_TARGETS = ["tree", "squirrel", "bird", "bicycle"]
LONG_WORDS = ("trail", "hike", "hiking", "woods", "forest", "conservation", "bog", "ponds", "meadow", "valley")
HERD_EVERY = 3  # every third quest is a co-op quest: it needs a friend in frame

# A place is dropped when its name or description says any of this. Gary must
# never send anyone somewhere closed, private or risky.
RISKS = [
    (r"\bclosed\b|\bclosure\b|\bnot open\b", "it is closed"),
    (r"\bprivate (property|land|road|club|residence|event)\b|\bmembers only\b|\bno public access\b|\brestricted\b"
     r"|\bby permit\b|\bpermit only\b|\btrespass|\bkeep out\b|\bno entry\b", "it is not open to everyone"),
    (r"\bconstruction\b|\bunder repair\b|\bdetour\b", "there is construction"),
    (r"\bcancell?ed\b|\bpostponed\b|\bsold out\b", "the event is off or full"),
    (r"\bunsafe\b|\bdanger|\bhazard|\bthin ice\b|\bflooded\b|\bflooding\b|\bcliff|\bquarry\b|\bspillway\b"
     r"|\bweir\b|\brail ?yard\b|\brailway track|\brooftop\b|\bwashed out\b", "the ground may be risky"),
]

# Every quest carries a note that says where to stand (issue #32).
NOTES = {
    "parks": "Any safe, accessible spot in the park counts. Stay on public paths.",
    "trails": "Stay on the marked trail. Any safe, accessible spot counts.",
    "events": "Any safe, accessible spot at the venue counts, outside included. No ticket needed.",
}
DEFAULT_NOTE = "Any safe, accessible spot counts. Stay on public paths."


def load_labels():
    """The things a quest may ask for: outdoor names in the contract that the
    device's own label file also has. A quest for anything else could never be
    confirmed, so it is dropped."""
    with open(os.path.join(ROOT, "contract", "labels.json"), "r", encoding="utf-8") as f:
        doc = json.load(f)
    allowed = {item["name"] for item in doc["labels"] if item["outdoor"]}
    # the device's two label files: SSD's everyday things, the nature model's
    on_device = set()
    for name in ("coco_labels.txt", "gary_nature_labels.txt"):
        path = os.path.join(ROOT, "device", "models", name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                on_device |= {line.strip() for line in f}
    if on_device:
        allowed &= on_device
    return allowed


# --------------------------------------------------------------------------
# TinyFish
# --------------------------------------------------------------------------
def field(event, *names):
    """The first of these fields the event has. TinyFish's documents spell them
    run_id and streaming_url; this also reads runId and streamingUrl."""
    for name in names:
        if event.get(name):
            return event[name]
    return None


def parse_sse(lines, on_event=None):
    """Read a TinyFish event stream. Returns the final COMPLETE event, with the
    run id and the live-view link added when an earlier event carried them."""
    final, streaming_url, run_id = None, None, None
    for raw in lines:
        line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
        line = line.strip()
        if not line.startswith("data:"):
            continue
        try:
            event = json.loads(line[5:].strip())
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if on_event:
            on_event(event)
        run_id = field(event, "run_id", "runId") or run_id
        streaming_url = field(event, "streaming_url", "streamingUrl") or streaming_url
        if event.get("type") == "COMPLETE":
            final = event
            break
    if final is not None:
        if run_id:
            final["run_id"] = run_id
        if streaming_url:
            final["streaming_url"] = streaming_url
    return final


class Refused(RuntimeError):
    """TinyFish would not start the run because of the key or the account. Every
    other page would be refused the same way, so the scout stops asking."""


def run_agent(url, goal, api_key, say, steps=None, seen=None, endpoint=TINYFISH_URL, wait=300):
    """One TinyFish run. Returns the COMPLETE event. Raises RuntimeError with a
    plain message when the run cannot start, does not finish, or takes longer
    than `wait` seconds. What the agent says it is doing is added to `steps`;
    the run id and the live-view link are put in `seen` as soon as they arrive,
    so a run that fails later still has them."""
    body = json.dumps({"url": url, "goal": goal}).encode("utf-8")
    req = urllib.request.Request(endpoint, data=body, headers={
        "X-API-Key": api_key, "Content-Type": "application/json", "Accept": "text/event-stream"})
    give_up_at = time.monotonic() + wait

    def show(event):
        kind = event.get("type")
        run_id, live = field(event, "run_id", "runId"), field(event, "streaming_url", "streamingUrl")
        if seen is not None:
            if run_id:
                seen["run_id"] = run_id
            if live:
                seen["streaming_url"] = live
        if kind == "STARTED":
            say("  agent started, run %s" % run_id)
        elif kind == "STREAMING_URL":
            say("  watch it live: %s" % live)
        elif kind == "PROGRESS" and event.get("purpose"):
            say("  ... %s" % event["purpose"])
            if steps is not None and len(steps) < 15:
                steps.append(str(event["purpose"])[:160])
        if kind != "COMPLETE" and time.monotonic() > give_up_at:
            raise RuntimeError("no answer after %d seconds, so the scout stopped waiting" % wait)

    quiet = max(1, min(wait, 180))
    try:
        with urllib.request.urlopen(req, timeout=quiet) as reply:
            final = parse_sse(reply, show)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        hints = {401: "the API key is missing or wrong", 402: "the account has no balance",
                 403: "no credits or no active plan"}
        kind = Refused if exc.code in hints else RuntimeError
        raise kind("TinyFish refused the run: HTTP %d (%s). %s"
                   % (exc.code, hints.get(exc.code, "see the reply"), detail))
    except TimeoutError:
        raise RuntimeError("TinyFish sent nothing for %d seconds, so the scout stopped waiting" % quiet)
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
        # A list of objects where at least one has a name is the list of places.
        # (An entry with no name is skipped later; it must not hide the others.)
        if result and all(isinstance(item, dict) for item in result) and any(item.get("name") for item in result):
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
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48]


def article(word):
    return "an" if word[:1] in "aeiou" else "a"


NAME_MAX = 70  # longer than this is a sentence, not the name of a place


def web_address(value):
    """An http or https address, or None. What the agent copied from a page is
    not trusted: the web page turns this into a link."""
    text = str(value or "").strip()
    return text if len(text) <= 300 and re.match(r"https?://[^\s<>\"']+$", text, flags=re.I) else None


def today():
    """Today's date where Gary lives (GARY_TZ, default America/Toronto), so the
    scout and the backend agree on which quests are today's."""
    try:
        import zoneinfo
        zone = zoneinfo.ZoneInfo(os.environ.get("GARY_TZ") or "America/Toronto")
        return datetime.datetime.now(zone).date().isoformat()
    except Exception:  # no time zone data on this machine: its own date will do
        return datetime.date.today().isoformat()


def clean_name(name):
    """'  Kains Woods ESA ' -> 'Kains Woods', so two sites' spellings of one
    place end up as one place. Line breaks and control characters go too."""
    name = "".join(ch if ch.isprintable() else " " for ch in str(name or ""))
    name = " ".join(name.split())
    name = re.sub(r"\s*\((esa|environmentally significant area)\)\s*$", "", name, flags=re.I)
    name = re.sub(r"\s+(esa|environmentally significant area)$", "", name, flags=re.I)
    return name.strip(" ,.;:-")


def place_key(name):
    return re.sub(r"[^a-z0-9]+", " ", clean_name(name).lower()).strip()


def risk_in(text):
    """Why this place must not become a quest, or None if nothing says so."""
    lowered = str(text).lower()
    for pattern, why in RISKS:
        if re.search(pattern, lowered):
            return why
    return None


def pick_target(name, text, allowed):
    """The thing to look for at a place. The same place always gets the same
    thing, so running the scout twice does not change today's quests."""
    lowered = text.lower()
    turn = sum(ord(ch) for ch in place_key(name))
    for words, targets in TARGET_RULES:
        choices = [t for t in targets if t in allowed]
        if choices and any(word in lowered for word in words):
            return choices[turn % len(choices)]
    choices = [t for t in FALLBACK_TARGETS if t in allowed] or sorted(allowed)
    if not choices:
        return None
    return choices[turn % len(choices)]


_last_geocode = [0.0]


def geocode(name, address=None, fetch=None):
    """(lat, lng) of a place in London, Ontario, or None. The agent's street
    address is used when it gave one, the name otherwise. A failure never
    drops a quest: it only has no position, and the page then never says
    "you are here" about it."""
    query = "%s, London, Ontario" % (address or name)
    url = NOMINATIM_URL + "?" + urllib.parse.urlencode(
        {"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "ca", "viewbox": LONDON_BOX, "bounded": 1})
    if fetch is None:
        wait = 1.0 - (time.monotonic() - _last_geocode[0])
        if wait > 0:
            time.sleep(wait)
        _last_geocode[0] = time.monotonic()

        def fetch(u):
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": GEO_AGENT}), timeout=10) as r:
                return r.read()
    try:
        found = json.loads(fetch(url))
        lat, lng = float(found[0]["lat"]), float(found[0]["lon"])
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None
    return (round(lat, 6), round(lng, 6)) if -90 <= lat <= 90 and -180 <= lng <= 180 else None


def build_quests(places, source, day, allowed, limit=3, taken=None, count=0, locate=None):
    """Turn agent places into contract Quests.

    places   what the agent returned: [{"name", "about", ...}]
    source   the entry from sources.json (url, time, kind). With "sample": True
             the quests are marked source "sample" and not "tinyfish": they
             were not found by an agent, and the page must not say they were
    taken    place keys already used in this run; a place gets one quest
    count    quests built so far in this run (every third is a herd quest)
    locate   (name, address) -> (lat, lng) or None, e.g. geocode. None: no positions
    Returns (quests, dropped). dropped is [{"name", "why"}].
    """
    taken = set() if taken is None else taken
    quests, dropped = [], []
    def about_of(place):
        return " ".join(str(place.get(key) or "") for key in ("about", "description", "features", "address", "status"))
    # every description of a place, so a place listed twice gets the same target whichever copy comes first
    abouts = {}
    for place in places:
        abouts.setdefault(place_key(clean_name(place.get("name")) or ""), []).append(about_of(place))
    for place in places:
        if len(quests) >= limit:
            break
        name = clean_name(place.get("name"))
        if not name:
            continue
        if len(name) > NAME_MAX:
            dropped.append({"name": name[:NAME_MAX] + "...", "why": "that is too long to be the name of a place"})
            continue
        text = name + " " + about_of(place)
        key = place_key(name)
        if key in taken:
            dropped.append({"name": name, "why": "another quest is already at this place"})
            continue
        why = risk_in(text)
        if why:
            dropped.append({"name": name, "why": why})
            continue
        target = pick_target(name, name + " " + " ".join(sorted(abouts[key])), allowed)
        if target is None or target not in allowed:
            dropped.append({"name": name, "why": "nothing Gary can recognise fits this place"})
            continue
        taken.add(key)
        is_long = source.get("time") == "long" or (
            source.get("time") is None and any(word in text.lower() for word in LONG_WORDS))
        herd = (count + len(quests) + 1) % HERD_EVERY == 0
        title = "Find %s %s at %s" % (article(target), target, name)
        if herd:
            title += ", with a friend"
        quests.append({
            "id": "q-%s-%s" % (day, slug(name)),
            "title": title,
            "place": name,
            "time": "long" if is_long else "short",
            "minutes": 40 if is_long else 15,
            "target": target,
            "xp": 40 if is_long else 20,
            "herd": herd,
            "note": NOTES.get(source.get("kind"), DEFAULT_NOTE),
            "source": "sample" if source.get("sample") else "tinyfish",
            "source_url": web_address(place.get("url")) or web_address(source.get("url")),
            "day": day,
        })
        quests[-1]["_about"] = " ".join(sorted(abouts[key])).strip()  # for --voice; never posted
        spot = locate(name, clean_name(place.get("address"))) if locate else None
        if spot:
            quests[-1]["lat"], quests[-1]["lng"] = spot
    return quests, dropped


def check_quests(quests, allowed):
    """A last look at every quest before it leaves. -> (good, [(quest, why)])"""
    good, bad, places = [], [], set()
    for quest in quests:
        if quest.get("target") not in allowed:
            bad.append((quest, "Gary cannot recognise '%s'" % quest.get("target")))
        elif place_key(quest.get("place")) in places:
            bad.append((quest, "a second quest at %s" % quest.get("place")))
        elif risk_in("%s %s" % (quest.get("title"), quest.get("place"))):
            bad.append((quest, risk_in("%s %s" % (quest.get("title"), quest.get("place")))))
        elif "safe, accessible spot" not in str(quest.get("note", "")):
            bad.append((quest, "its note does not say where it is safe to stand"))
        else:
            places.add(place_key(quest["place"]))
            good.append(quest)
    return good, bad


def machine_token(env=None, opener=urllib.request.urlopen):
    """The scout's own identity: an Auth0 machine-to-machine token that carries
    the write:quests permission. Needs AUTH0_DOMAIN, AUTH0_AUDIENCE,
    AUTH0_SCOUT_CLIENT_ID and AUTH0_SCOUT_CLIENT_SECRET in scout/.env.
    -> the token, or None when they are not set or Auth0 cannot be reached."""
    env = os.environ if env is None else env
    names = ("AUTH0_DOMAIN", "AUTH0_AUDIENCE", "AUTH0_SCOUT_CLIENT_ID", "AUTH0_SCOUT_CLIENT_SECRET")
    if not all(env.get(name) for name in names):
        return None
    body = json.dumps({"grant_type": "client_credentials", "client_id": env["AUTH0_SCOUT_CLIENT_ID"],
                       "client_secret": env["AUTH0_SCOUT_CLIENT_SECRET"], "audience": env["AUTH0_AUDIENCE"]})
    req = urllib.request.Request("https://%s/oauth/token" % env["AUTH0_DOMAIN"].strip("/"),
                                 data=body.encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with opener(req, timeout=10) as reply:
            return json.loads(reply.read().decode("utf-8")).get("access_token")
    except (OSError, ValueError):
        return None


def post_quests(api, quests):
    headers = {"Content-Type": "application/json"}
    if os.environ.get("SCOUT_KEY"):
        headers["X-Scout-Key"] = os.environ["SCOUT_KEY"]
    token = machine_token()
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(api.rstrip("/") + "/api/quests",
                                 data=json.dumps({"quests": quests}).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=10) as reply:
        return json.loads(reply.read().decode("utf-8"))


# --------------------------------------------------------------------------
# Evidence: what the agent read, for the judges (issue #33)
# --------------------------------------------------------------------------
def read_runs(path):
    runs = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    runs.append(json.loads(line))
                except ValueError:
                    continue
    return runs


def evidence_markdown(runs):
    """scout/EVIDENCE.md: every recorded live run, newest day first."""
    out = ["# What the scout read", "",
           "Each row is one run of a TinyFish web agent on a live page. This file is written by",
           "`python3 scout/scout.py --report` from `scout/runs.jsonl`. Do not edit it by hand.", ""]
    live = [r for r in runs if r.get("status")]
    if not live:
        out += ["**No live runs are recorded yet.** Set `TINYFISH_API_KEY`, run `python3 scout/scout.py`,",
                "then `python3 scout/scout.py --report`.", ""]
        return "\n".join(out)
    done = [r for r in live if r.get("status") == "COMPLETED"]
    out += ["%d runs, %d completed, %d quests made, on %d different pages."
            % (len(live), len(done), sum(len(r.get("quests", [])) for r in done),
               len({r.get("url") for r in done})), ""]
    days = sorted({str(r.get("ts", ""))[:10] for r in live}, reverse=True)
    for day in days:
        out += ["## %s" % day, "", "| Time (UTC) | Page the agent read | Result | TinyFish run | Quests |",
                "| --- | --- | --- | --- | --- |"]
        todays = [r for r in live if str(r.get("ts", ""))[:10] == day]
        for r in todays:
            run = r.get("run_id") or "none"
            if r.get("streaming_url"):
                run = "%s ([live view](%s))" % (run, r["streaming_url"])
            if r.get("status") == "COMPLETED":
                result = "%d places read in %s s" % (r.get("places", 0), r.get("seconds", "?"))
                quests = "<br>".join(q["title"] if isinstance(q, dict) else str(q) for q in r.get("quests", [])) or "none"
            else:
                result = "failed: %s" % str(r.get("error", "")).replace("|", "/")[:120]
                quests = "none"
            out.append("| %s | [%s](%s) | %s | %s | %s |"
                       % (str(r.get("ts", ""))[11:16], r.get("source"), r.get("url"), result, run, quests))
        out.append("")
        for r in todays:
            if r.get("steps") or r.get("dropped"):
                out.append("**%s, %s**" % (r.get("source"), str(r.get("ts", ""))[11:16]))
                out.append("")
                if r.get("steps"):
                    out.append("What the agent did: " + "; ".join(r["steps"]) + ".")
                    out.append("")
                for d in r.get("dropped", []):
                    out.append("- Left out %s: %s." % (d.get("name"), d.get("why")))
                if r.get("dropped"):
                    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
def main(argv=None):
    load_settings()
    ap = argparse.ArgumentParser(description="Gary's scout: live pages in, quests out")
    ap.add_argument("--dry-run", action="store_true", help="print the quests, send nothing")
    ap.add_argument("--one", action="store_true", help="run only the first source (a quick test of the key)")
    ap.add_argument("--source", help="run only the sources whose name contains this")
    ap.add_argument("--max", type=int, default=3, help="quests per source (default 3)")
    ap.add_argument("--from-file", help="build sample quests from a file of places. No agent run; marked as sample")
    ap.add_argument("--wait", type=int, default=300, help="seconds to wait for one page before giving up (default 300)")
    ap.add_argument("--tinyfish-url", default=TINYFISH_URL, help=argparse.SUPPRESS)  # tests point this at a stand-in
    ap.add_argument("--cached", action="store_true", help="post the quests saved by the last good live run")
    ap.add_argument("--report", action="store_true", help="write EVIDENCE.md from runs.jsonl, then stop")
    ap.add_argument("--voice", action="store_true", help="stretch: let Gemini put each title in Gary's voice (GEMINI_API_KEY)")
    ap.add_argument("--sources", default=os.path.join(HERE, "sources.json"))
    ap.add_argument("--api", default=os.environ.get("GARY_API", "http://localhost:8000"), help="backend address")
    ap.add_argument("--runs", default=os.path.join(HERE, "runs.jsonl"), help="where live runs are recorded")
    ap.add_argument("--cache", default=os.path.join(HERE, "cached_quests.json"), help="the last good set of quests")
    ap.add_argument("--evidence", default=os.path.join(HERE, "EVIDENCE.md"))
    ap.add_argument("--all", action="store_true", help=argparse.SUPPRESS)  # every source is now the default
    ap.add_argument("--no-geocode", action="store_true",
                    help="do not look up where each place is (OpenStreetMap). Also GARY_NO_GEOCODE=1")
    args = ap.parse_args(argv)
    locate = None if args.no_geocode or os.environ.get("GARY_NO_GEOCODE") else geocode

    def say(text):
        print(text, flush=True)

    if args.report:
        runs = read_runs(args.runs)
        with open(args.evidence, "w", encoding="utf-8") as f:
            f.write(evidence_markdown(runs) + "\n")
        say("Wrote %s from %d recorded runs." % (args.evidence, len(runs)))
        return 0

    allowed = load_labels()
    day = today()
    quests, live = [], False

    if args.cached:
        try:
            with open(args.cache, "r", encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            sys.exit("No cached quests yet (%s). They are saved by the first good live run." % args.cache)
        quests = saved.get("quests", [])
        say("%d quests from the live run saved at %s. No new agent run was made." % (len(quests), saved.get("saved_at")))
        missing = [q for q in quests if q.get("lat") is None] if locate else []
        for quest in missing:  # saved before the scout looked up positions: look them up once, and keep them
            spot = locate(quest.get("place"), None)
            if spot:
                quest["lat"], quest["lng"] = spot
        if any(q.get("lat") is not None for q in missing):
            with open(args.cache, "w", encoding="utf-8") as f:
                json.dump(dict(saved, quests=quests), f, indent=2)
                f.write("\n")
            say("Looked up where %d of %d places are." % (sum(q.get("lat") is not None for q in missing), len(missing)))
    elif args.from_file:
        with open(args.from_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        places = find_places(saved.get("result", saved) if isinstance(saved, dict) else saved)
        say("%d places from %s. This is not a live run: the quests are marked as sample quests,\n"
            "and the page will not say the scout found them." % (len(places), args.from_file))
        source = {"url": None, "kind": saved.get("kind") if isinstance(saved, dict) else None, "sample": True}
        quests, dropped = build_quests(places, source, day, allowed, args.max, locate=locate)
        for d in dropped:
            say("  left out %s: %s" % (d["name"], d["why"]))
    else:
        with open(args.sources, "r", encoding="utf-8") as f:
            sources = json.load(f)
        if args.source:
            sources = [s for s in sources if args.source.lower() in s["name"].lower()]
            if not sources:
                sys.exit("no source with %r in its name in %s" % (args.source, args.sources))
        elif args.one:
            sources = sources[:1]
        key = os.environ.get("TINYFISH_API_KEY")
        if not key:
            sys.exit("Set TINYFISH_API_KEY in scout/.env or your shell first (free student credits: tinyfish.ai/students).\n"
                     "With no key: python3 scout/scout.py --cached   (the last good live run)\n"
                     "         or: python3 scout/scout.py --from-file scout/sample_result.json --dry-run")
        live, taken = True, set()
        for source in sources:
            say("Scouting %s\n  %s" % (source["name"], source["url"]))
            started, steps, seen, key_refused = time.monotonic(), [], {}, False
            record = {"ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "source": source["name"], "kind": source.get("kind"), "url": source["url"]}
            try:
                final = run_agent(source["url"], source["goal"], key, say, steps, seen, args.tinyfish_url, args.wait)
            except RuntimeError as exc:
                say("  FAILED: %s" % exc)
                record.update(status="FAILED", error=str(exc), steps=steps, run_id=seen.get("run_id"),
                              streaming_url=seen.get("streaming_url"))
                key_refused = isinstance(exc, Refused)
            else:
                # The reply is documented as "result"; look through the whole event if it is elsewhere.
                places = find_places(final.get("result")) or find_places(
                    {k: v for k, v in final.items() if k not in ("type", "status", "run_id", "streaming_url")})
                found, dropped = build_quests(places, source, day, allowed, args.max, taken, len(quests), locate)
                say("  %d places -> %d quests" % (len(places), len(found)))
                for d in dropped:
                    say("  left out %s: %s" % (d["name"], d["why"]))
                quests.extend(found)
                record.update(status="COMPLETED", run_id=final.get("run_id"),
                              streaming_url=final.get("streaming_url"), steps=steps, places=len(places),
                              place_names=[clean_name(p.get("name")) for p in places][:20],
                              quests=[{"id": q["id"], "title": q["title"], "place": q["place"],
                                       "target": q["target"]} for q in found],
                              dropped=dropped)
            record["seconds"] = round(time.monotonic() - started, 1)
            with open(args.runs, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
            if key_refused:
                say("  Not trying the other pages: they would be refused the same way.")
                break

    quests, refused = check_quests(quests, allowed)
    for quest, why in refused:
        say("  dropped %s: %s" % (quest.get("id"), why))
    if not quests:
        sys.exit("No quests came out of this run. To post the last good ones: python3 scout/scout.py --cached")

    if args.voice:
        import gary_voice
        changed = gary_voice.apply(quests, os.environ.get("GEMINI_API_KEY"), say=say)
        say("Gemini put %d of %d titles in Gary's voice, and gave %d quests trail tidbits."
            % (changed, len(quests), sum(1 for q in quests if q.get("tidbits"))))
    for quest in quests:  # working notes, like the page text, stay here
        for name in [k for k in quest if k.startswith("_")]:
            del quest[name]

    if args.cached and args.voice:
        with open(args.cache, "w", encoding="utf-8") as f:
            json.dump(dict(saved, quests=quests), f, indent=2)
            f.write("\n")
    if live:
        with open(args.cache, "w", encoding="utf-8") as f:
            json.dump({"saved_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "day": day, "quests": quests}, f, indent=2)
            f.write("\n")

    if args.dry_run:
        say(json.dumps({"quests": quests}, indent=2))
        say("\n%d quests. Dry run: nothing was sent." % len(quests))
        return 0
    try:
        out = post_quests(args.api, quests)
    except urllib.error.HTTPError as exc:
        sys.exit("The backend refused the quests: HTTP %d %s" % (exc.code, exc.read().decode("utf-8", "replace")))
    except OSError as exc:
        sys.exit("Could not reach the backend at %s (%s). Use --dry-run to only print." % (args.api, exc))
    say("Backend accepted %d quests: %s" % (len(out.get("accepted", [])), ", ".join(out.get("accepted", []))))
    for bad in out.get("rejected", []):
        say("  refused %s: %s" % (bad.get("id"), bad.get("why")))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    sys.exit(main())
