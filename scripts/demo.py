#!/usr/bin/env python3
"""demo.py - get the demo ready, check that it is, and rehearse it with no device.

    python3 scripts/demo.py check  --api http://<server>    look only. Changes nothing
    python3 scripts/demo.py reset  --api http://<server>    forget the rehearsal, put the scout's quests back
    python3 scripts/demo.py replay --api http://<server>    play the beats of docs/DEMO.md with pretend sniffs

`reset` and `replay` forget every sniff and every mood check-in on that
backend. They ask first; --yes answers for you.

`check` reads the backend and a few files in this repo, and says what would
go wrong in the demo: FAIL for what must be fixed, WARN for what changes the
words you may say. It exits 0 when nothing must be fixed.

`replay` is for rehearsing the page and the words when Gary is not on the
table. It also proves that the numbers in docs/DEMO.md (20 XP, 40 XP, a
Scrambler at beat 5, the herd moving up) are what the backend really gives.

Keys, when the server sets them: export GARY_ADMIN_KEY (for the reset),
SCOUT_KEY (to post quests) and GARY_PRIVATE_KEY (the passphrase of the private
page: check and replay read and write check-ins). GARY_API can stand in for
--api. Standard library only.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCOUT = os.path.join(ROOT, "scout", "scout.py")
BOTTLE, BACKPACK = "q-demo-bottle", "q-demo-backpack"   # the two quests on the demo table
SHORT_NAP = 600   # seconds. A nap setting shorter than this puts Gary to sleep during the demo


class Offline(Exception):
    """The backend did not answer."""


class Refused(Exception):
    """The backend answered with an error."""

    def __init__(self, code, text):
        Exception.__init__(self, "HTTP %d %s" % (code, text))
        self.code, self.text = code, text


def call(api, path, body=None, headers=None, raw=False, timeout=8):
    """GET, or POST when a body is given. -> parsed JSON, or the text with raw=True.
    Calls to the private side carry the passphrase from GARY_PRIVATE_KEY."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = dict({"Content-Type": "application/json"}, **(headers or {}))
    if path in ("/api/wellness", "/api/mood") and os.environ.get("GARY_PRIVATE_KEY"):
        headers["X-Private-Key"] = os.environ["GARY_PRIVATE_KEY"]
    req = urllib.request.Request(api.rstrip("/") + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as reply:
            text = reply.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise Refused(exc.code, exc.read().decode("utf-8", "replace")[:300])
    except OSError as exc:
        raise Offline(str(getattr(exc, "reason", exc)))
    if raw:
        return text
    try:
        return json.loads(text)
    except ValueError:
        raise Refused(200, "the answer was not JSON. Is %s the backend's address?" % api)


class Report:
    """Prints each finding as it comes and keeps count."""

    def __init__(self):
        self.fails, self.warns = [], []

    def section(self, title):
        print("\n" + title)

    def ok(self, text):
        print("  ok    " + text)

    def note(self, text):
        print("        " + text)

    def warn(self, text, fix=None):
        self.warns.append(text)
        print("  WARN  " + text)
        if fix:
            print("        -> " + fix)

    def fail(self, text, fix=None):
        self.fails.append(text)
        print("  FAIL  " + text)
        if fix:
            print("        -> " + fix)


def zone(name):
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo(name or "America/Toronto")
    except Exception:  # no time zone data here: this machine's own zone will do
        return None


def local_day(ts, tz):
    """'2026-11-22T03:10:00Z' -> the date where Gary lives, '2026-11-21'."""
    try:
        when = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when.astimezone(tz).date().isoformat()


def today(tz):
    return datetime.datetime.now(tz).date().isoformat() if tz else datetime.date.today().isoformat()


def plural(n, one, many=None):
    return "%d %s" % (n, one if n == 1 else (many or one + "s"))


def read_lines_of_json(path):
    out = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


# --------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------
def check_backend(api, report):
    """-> the health reply, or None if the backend cannot be reached."""
    report.section("Backend  %s" % api)
    started = time.monotonic()
    try:
        health = call(api, "/api/health")
    except (Offline, Refused) as exc:
        report.fail("cannot reach the backend (%s)" % exc,
                    "Start it, or check the address. With no backend the page still plays the demo story: add ?mock to its address.")
        return None
    report.ok("answers, in %.2f s" % (time.monotonic() - started))
    if health.get("store") == "postgres":
        if health.get("hypertable"):
            report.ok("keeps its data in Postgres, and events is a hypertable")
        else:
            report.warn("keeps its data in Postgres, but events is a plain table, not a hypertable",
                        "Claim [D] in docs/DEVPOST.md (Tiger Data) is not true on this database. python3 backend/check_db.py says why.")
    else:
        report.warn("keeps everything in memory: restarting the server forgets Gary",
                    "Fine for a demo. But claim [D] in docs/DEVPOST.md (Tiger Data) is not true until DATABASE_URL is set on the server.")
    keys = health.get("keys")
    if keys is None:
        report.warn("this backend is older than this script: it does not say whether its keys are set",
                    "Deploy the current code: sh backend/deploy/deploy.sh root@<ip>")
    else:
        doors = (("admin", "reset Gary", "GARY_ADMIN_KEY"), ("scout", "post quests", "SCOUT_KEY"),
                 ("private", "read the private check-ins", "GARY_PRIVATE_KEY"))
        open_doors = [(what, setting) for name, what, setting in doors if not keys.get(name)]
        if not open_doors:
            report.ok("the reset, quest posting and the private page are locked with keys")
        else:
            report.warn("anyone who has this address can %s (%s not set)" % (
                " and ".join(what for what, _ in open_doors), ", ".join(setting for _, setting in open_doors)),
                "On a public server, set them in /opt/gary/.env and restart: systemctl restart gary")
        if "private" in keys and not keys.get("private"):
            report.note("With no GARY_PRIVATE_KEY the page itself says it is not locked. Do not call it private in beat 7.")
    nap = health.get("nap_seconds")
    if isinstance(nap, (int, float)) and nap < SHORT_NAP:
        report.warn("Gary naps after %d seconds of quiet: he will be asleep again before the demo ends" % nap,
                    "Unset GARY_NAP_SECONDS on the server for the three-minute demo.")
    try:
        page = call(api, "/", raw=True)
        if "<title>Gary the Goat</title>" in page and 'id="root"' in page:
            report.ok("serves the web page")
        else:
            report.warn("answers at / with something that is not Gary's page")
    except Refused:
        report.warn("does not serve the web page (no web/dist beside it)",
                    "Fine if the page runs from `npm run dev`. On the server: build the page and deploy again.")
    except Offline as exc:
        report.warn("the web page did not load (%s)" % exc)
    return health


def check_quests(api, report, day):
    report.section("Quests")
    quests = call(api, "/api/quests?all=true")["quests"]
    open_ids = {q["id"] for q in call(api, "/api/quests")["quests"]}
    scout = [q for q in quests if q.get("source") == "tinyfish"]
    todays = [q for q in scout if q.get("day") == day]
    if not scout:
        report.warn("no quest from a live scout run is loaded",
                    "Beats 2 and 3 then use the \"no live run\" lines in docs/DEMO.md. To load real ones: "
                    "python3 scout/scout.py (needs TINYFISH_API_KEY), or python3 scout/scout.py --cached")
    elif not todays:
        newest = max(str(q.get("day")) for q in scout)
        report.warn("%s from the scout, none dated today (the newest is dated %s)" % (plural(len(scout), "quest"), newest),
                    "Say \"the scout's last run\", not \"this morning\". Or run python3 scout/scout.py again today.")
    else:
        report.ok("%s from live scout runs, %d dated today" % (plural(len(scout), "quest"), len(todays)))
    samples = [q for q in quests if q.get("source") == "sample"]
    if samples:
        report.note("%s loaded (hand-written places). The page says so on each." % plural(len(samples), "sample quest"))
    missing = [qid for qid in (BOTTLE, BACKPACK) if qid not in {q["id"] for q in quests}]
    done = [qid for qid in (BOTTLE, BACKPACK) if qid not in open_ids and qid not in missing]
    if missing:
        report.fail("the table quest is missing: " + ", ".join(missing),
                    "Beats 4 and 5 need the bottle and the backpack quest. python3 scripts/demo.py reset --api %s" % api)
    if done:
        report.fail("the table quest is already finished: " + ", ".join(done),
                    "python3 scripts/demo.py reset --api %s" % api)
    if not missing and not done:
        report.ok("both table quests are open: a water bottle, and a backpack with a friend")
    return quests


def check_gary(api, report):
    report.section("Gary")
    state = call(api, "/api/state")
    gary, finds = state["gary"], len(state.get("journal") or [])
    if gary.get("xp") == 0 and finds == 0:
        report.ok("a clean start: asleep, 0 XP, no finds" if gary.get("napping") else "a clean start: 0 XP, no finds")
    else:
        report.fail("Gary already has %d XP and %s" % (gary.get("xp", 0), plural(finds, "find")),
                    "python3 scripts/demo.py reset --api %s   then, on the Pi: sh start_gary.sh --fresh" % api)
    if state.get("quest_choice"):
        report.warn("short or long was already pressed (%s)" % state["quest_choice"],
                    "Beat 3's tap will then skip to the next quest. A reset clears it.")
    short = (state.get("quest_options") or {}).get("short")
    if short:
        kind = {"tinyfish": "found by the scout", "sample": "a sample quest", "seed": "a built-in quest"}.get(
            short.get("source"), "added by hand")
        report.note("A tap on Short will show: \"%s\" (%s)." % (short.get("title"), kind))
        if not state.get("quest_choice") and (state.get("quest") or {}).get("id") == short.get("id"):
            report.warn("that quest is already on the sign, so beat 3's tap changes nothing anyone can see",
                        "Load the scout's quests (or sample places: reset --samples), so that Short brings up a new sign.")
    else:
        report.warn("no short quest is open: beat 3's tap will change nothing")


def check_you(api, report, tz, day):
    report.section("The private check-in")
    try:
        wellness = call(api, "/api/wellness")
    except Refused as exc:
        if exc.code != 401:
            raise
        if os.environ.get("GARY_PRIVATE_KEY"):
            report.warn("the passphrase in GARY_PRIVATE_KEY did not open the private page",
                        "Use the value of GARY_PRIVATE_KEY in /opt/gary/.env on the server.")
        else:
            report.warn("the private page is locked, so the check-in could not be looked at",
                        "export GARY_PRIVATE_KEY=<the passphrase> and run this again. "
                        "Beat 7 needs a \"before\" check-in, and the Driver's laptop must have opened the You tab once.")
        return
    todays = [c for c in wellness.get("checkins", []) if local_day(c.get("ts"), tz) == day]
    last = todays[-1] if todays else None
    if last is None:
        report.warn("no \"before\" check-in yet today",
                    "Beat 7 needs one. Driver: open the You tab and tap how you feel under \"Before you head out\".")
    elif last.get("phase") == "before":
        if last.get("value") == 5:
            report.warn("the \"before\" check-in is already at the top of the scale",
                        "Beat 7's tap cannot go higher, so the sentence cannot say \"better\". That is fine if it is true.")
        else:
            report.ok("a \"before\" check-in is waiting for its \"after\"")
    else:
        report.warn("today already has a before and an after",
                    "Beat 7's tap would start a new pair. Reset, then tap a \"before\".")


def check_files(report, args, tz, day):
    report.section("This machine  %s" % ROOT)
    runs = [r for r in read_lines_of_json(args.runs) if r.get("status") == "COMPLETED"]
    runs_today = [r for r in runs if local_day(r.get("ts"), tz) == day]
    if not runs:
        report.warn("no live scout run is recorded here (%s)" % os.path.relpath(args.runs, ROOT),
                    "Claim [C] in docs/DEVPOST.md and beat 2 of the demo are not true yet. Issue #8 has the first command.")
    elif not runs_today:
        report.warn("%s recorded, none today" % plural(len(runs), "live scout run"),
                    "Beat 2 says \"this morning's runs\". Run the scout today, or change the words.")
    else:
        report.ok("%s recorded today, on %s" % (plural(len(runs_today), "live scout run"),
                                               plural(len({r.get("url") for r in runs_today}), "page")))
    evidence = os.path.join(os.path.dirname(args.runs), "EVIDENCE.md")
    if runs and (not os.path.exists(evidence) or os.path.getmtime(evidence) < os.path.getmtime(args.runs)):
        report.warn("scout/EVIDENCE.md is older than the run log",
                    "python3 scout/scout.py --report, then commit and push it: the Driver opens it on GitHub.")
    try:
        with open(args.cache, "r", encoding="utf-8") as f:
            cached = json.load(f)
        report.ok("%s saved from the live run of %s: the fallback if TinyFish is slow"
                  % (plural(len(cached.get("quests", [])), "cached quest"), cached.get("saved_at")))
    except (OSError, ValueError):
        report.warn("no cached scout quests here (%s)" % os.path.relpath(args.cache, ROOT),
                    "They are saved by the first live run. Without them there is nothing to fall back on if TinyFish is slow.")
    if os.path.exists(os.path.join(ROOT, "web", "dist", "index.html")):
        report.ok("the page is built here (web/dist)")
    else:
        report.warn("the page is not built here", "cd web && npm install && npm run build   (needed to deploy)")
    try:
        with open(os.path.join(ROOT, "docs", "DEMO.md"), "r", encoding="utf-8") as f:
            if "Talker: ____" in f.read():
                report.warn("docs/DEMO.md has no names in the four roles yet")
            else:
                report.ok("docs/DEMO.md has names in the roles")
    except OSError:
        report.warn("docs/DEMO.md is not here")
    if args.video:
        if os.path.isfile(args.video) and os.path.getsize(args.video) > 1000000:
            report.ok("the backup video is here: %s, %.0f MB" % (args.video, os.path.getsize(args.video) / 1e6))
        else:
            report.fail("the backup video is not at %s, or is smaller than 1 MB" % args.video)
    else:
        report.warn("the backup video was not checked", "Once it is recorded: add --video <file>. It should be on two laptops.")


def check_device(report):
    report.section("Gary, on this machine  %s" % os.path.join(ROOT, "device"))
    device = os.path.join(ROOT, "device")
    try:
        out = subprocess.run(["sh", os.path.join(device, "start_gary.sh"), "status"], capture_output=True, text=True, timeout=30)
        status = out.stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        report.fail("could not ask start_gary.sh for its status (%s)" % exc)
        return
    for name, line in (("Gary", "Gary: up"), ("the button and buzzer", "button and buzzer: up"), ("sync", "sync: up")):
        if line in status:
            report.ok("%s is running" % name)
        else:
            report.fail("%s is not running" % name, "sh device/start_gary.sh --fresh")
    journal = os.path.join(device, "journal.jsonl")
    lines = 0
    if os.path.exists(journal):
        with open(journal, "r", encoding="utf-8") as f:
            lines = sum(1 for line in f if line.strip())
    if lines:
        report.warn("the device's journal has %s from earlier" % plural(lines, "line"), "sh device/start_gary.sh --fresh")
    else:
        report.ok("the device's journal is empty: a fresh run")
    if os.path.exists(os.path.join(device, "qnx", "build", "gary")):
        report.ok("the QNX build of Gary is here")
    else:
        report.warn("this is the Python version of Gary, not the QNX build",
                    "Say \"on the device\", not \"on QNX\", and claim [A] in docs/DEVPOST.md is not true for this Gary.")


def run_check(api, args):
    report = Report()
    print("Gary demo check, %s" % datetime.datetime.now().strftime("%a %d %b %H:%M"))
    health = check_backend(api, report)
    tz = zone((health or {}).get("timezone"))
    day = today(tz)
    if health is not None:
        try:
            check_quests(api, report, day)
            check_gary(api, report)
            check_you(api, report, tz, day)
        except (Offline, Refused, KeyError, TypeError) as exc:
            report.fail("the backend's answers could not be read (%s: %s)" % (type(exc).__name__, exc),
                        "Is the deployed backend the current code?")
    check_files(report, args, tz, day)
    if args.device:
        check_device(report)
    print()
    if report.fails:
        print("NOT READY: %s to fix (FAIL above)%s." % (
            plural(len(report.fails), "thing"), ", and %s" % plural(len(report.warns), "warning") if report.warns else ""))
        return 1
    if report.warns:
        print("READY, with %s. Each one changes what you may say or what you fall back on." % plural(len(report.warns), "warning"))
    else:
        print("READY.")
    return 0


# --------------------------------------------------------------------------
# reset
# --------------------------------------------------------------------------
def confirm(api, yes):
    if yes:
        return
    if not sys.stdin.isatty():
        sys.exit("This would forget every sniff and every mood check-in on %s.\nNothing was changed. Run it again with --yes." % api)
    answer = input("This forgets every sniff and every mood check-in on %s.\nType yes to go on: " % api)
    if answer.strip().lower() != "yes":
        sys.exit("Nothing was changed.")


def run_scout(api, *flags):
    """Run scout.py, passing its output through. -> True if it worked."""
    out = subprocess.run([sys.executable, SCOUT] + list(flags) + ["--api", api], capture_output=True, text=True)
    for line in (out.stdout + out.stderr).strip().splitlines():
        print("    " + line)
    return out.returncode == 0


def do_reset(api, args):
    key = os.environ.get("GARY_ADMIN_KEY")
    try:
        call(api, "/api/dev/reset", {}, {"X-Admin-Key": key} if key else None)
    except Refused as exc:
        if exc.code == 401:
            sys.exit("The backend wants its admin key. export GARY_ADMIN_KEY=<the value in /opt/gary/.env on the server>, then run this again.\nNothing was changed.")
        sys.exit("The backend refused the reset: %s\nNothing was changed." % exc)
    except Offline as exc:
        sys.exit("Cannot reach the backend at %s (%s).\nNothing was changed." % (api, exc))
    print("Reset %s: every sniff and check-in is gone, and the built-in quests are back." % api)
    if args.no_quests:
        return
    if os.path.exists(args.cache):
        print("Putting back the quests of the last live scout run:")
        if not run_scout(api, "--cached", "--cache", args.cache):
            print("  The cached quests could not be posted. If the server sets SCOUT_KEY, export the same value here.")
    elif args.samples:
        print("No cached scout quests here. Posting sample places (the page labels them as samples):")
        run_scout(api, "--from-file", os.path.join(ROOT, "scout", "sample_result.json"))
    else:
        print("No cached scout quests here (%s), so only the built-in quests are loaded." % os.path.relpath(args.cache, ROOT))
        print("  For sample places, labelled as samples on the page: add --samples")


def run_reset(api, args):
    confirm(api, args.yes)
    do_reset(api, args)
    print("\nNext, by hand:")
    print("  1. On the Pi:   sh start_gary.sh --fresh")
    print("  2. The Driver:  open the page, tap You, tap how you feel under \"Before you head out\",")
    print("                  then go back to the Gary tab")
    print("  3. Then:        python3 scripts/demo.py check --api %s" % api)
    return 0


# --------------------------------------------------------------------------
# replay
# --------------------------------------------------------------------------
def pretend_sniff(api, n, label, friend=False):
    """One discovery, the way the device writes it. -> the backend's verdict on it."""
    now = datetime.datetime.now(datetime.timezone.utc)
    event = {"id": "replay-%d-%d" % (int(now.timestamp() * 1000), n), "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
             "type": "discovery", "device": "replay", "label": label, "score": 0.9, "friend": friend, "new": True,
             "quest_id": None, "latency_ms": 40.0}
    return call(api, "/api/events", {"events": [event]})["results"][0]


def run_replay(api, args):
    # The replay makes two check-ins. Find out that it cannot before anything is forgotten.
    try:
        call(api, "/api/wellness")
    except Refused as exc:
        if exc.code == 401:
            sys.exit("The private page is locked. export GARY_PRIVATE_KEY=<the passphrase>, then run the replay again.\n"
                     "Nothing was changed.")
        raise
    confirm(api, args.yes)
    do_reset(api, args)
    problems = []

    def beat(number, title):
        if not args.auto:
            input("\nEnter for beat %s: %s " % (number, title))
        else:
            if args.pause:
                time.sleep(args.pause)
            print("\nBeat %s: %s" % (number, title))

    def expect(what, good, got):
        print("  %s  %s" % ("ok  " if good else "FAIL", what))
        if not good:
            print("        the backend gave: %s" % (got,))
            problems.append(what)

    print("\nThe demo, with pretend sniffs. Watch the page at %s" % api)
    state = call(api, "/api/state")
    beat(1, "Gary is asleep, and that is fine")
    expect("Gary is napping with 0 XP", state["gary"]["napping"] and state["gary"]["xp"] == 0, state["gary"])
    call(api, "/api/mood", {"phase": "before", "value": 3})
    print("  (the Driver's \"before\" check-in from the setup: 3 of 5)")
    rank_before = state["herd"]["cup"]["rank"]

    beat(2, "the scout's evidence page")
    scout_quests = [q for q in call(api, "/api/quests")["quests"] if q.get("source") == "tinyfish"]
    print("  %s on this backend. Nothing changes on Gary's page in this beat." % (
        plural(len(scout_quests), "quest from a live scout run", "quests from live scout runs") if scout_quests
        else "No quest from a live scout run"))

    beat(3, "tap Short")
    chosen = call(api, "/api/quest/choose", {"time": "short"})["quest"]
    expect("a short quest is on the sign", chosen is not None, chosen)
    if chosen:
        credit = {"tinyfish": "Found by the scout", "sample": "A sample quest, written by hand"}.get(
            chosen.get("source"), "A starter quest")
        print("  the sign: \"%s\". Under it: %s." % (chosen["title"], credit))

    beat(4, "the Sniff Test on the water bottle")
    result = pretend_sniff(api, 1, "bottle")
    expect("the bottle finishes its quest for 20 XP",
           result.get("quest_id") == BOTTLE and result.get("xp") == 20, result)
    state = call(api, "/api/state")
    expect("Gary is awake, a Kid with 20 XP", not state["gary"]["napping"] and state["gary"]["xp"] == 20
           and state["gary"]["stage"] == "kid", state["gary"])

    beat(5, "a friend steps in: the backpack")
    result = pretend_sniff(api, 2, "backpack", friend=True)
    expect("the backpack with a friend finishes its quest for 40 XP",
           result.get("quest_id") == BACKPACK and result.get("xp") == 40, result)
    state = call(api, "/api/state")
    expect("Gary grows into a Scrambler at 60 XP", state["gary"]["stage"] == "scrambler" and state["gary"]["xp"] == 60,
           state["gary"])
    rank_after = state["herd"]["cup"]["rank"]
    expect("the herd moves up the Herd Cup (was %s, now %s)" % (rank_before, rank_after), rank_after < rank_before,
           state["herd"]["cup"])

    beat(6, "the map")
    cleared = [tile["place"] for tile in state["map"] if tile["cleared"]]
    expect("two places are uncovered", len(cleared) == 2, cleared)

    beat(7, "the private check-in")
    call(api, "/api/mood", {"phase": "after", "value": 4})
    wellness = call(api, "/api/wellness")
    expect("the sentence: \"%s\"" % wellness.get("summary"),
           wellness.get("summary") == "You reported feeling better after your outing.", wellness.get("summary"))
    expect("mood is nowhere in Gary's shared state", "mood" not in json.dumps(call(api, "/api/state")).lower(), "the word mood")

    beat(8, "Gary, awake")
    state = call(api, "/api/state")
    expect("Gary is still awake at the end", not state["gary"]["napping"], state["gary"])

    print()
    if problems:
        print("%s in docs/DEMO.md no longer match the backend:" % plural(len(problems), "line"))
        for what in problems:
            print("  - " + what)
        print("Change the rules back, or change the script.")
        return 1
    print("The demo's numbers hold.")
    print("Those were pretend sniffs. Before the real demo: python3 scripts/demo.py reset --api %s" % api)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Get the demo ready, check that it is, rehearse it with no device")
    ap.add_argument("what", choices=("check", "reset", "replay"))
    ap.add_argument("--api", default=os.environ.get("GARY_API", "http://localhost:8000"), help="the backend's address")
    ap.add_argument("--yes", action="store_true", help="reset and replay: do not ask before forgetting everything")
    ap.add_argument("--samples", action="store_true",
                    help="reset and replay: with no cached scout quests, post sample places (labelled as samples)")
    ap.add_argument("--no-quests", action="store_true", help="reset and replay: leave only the built-in quests")
    ap.add_argument("--auto", action="store_true", help="replay: do not wait for Enter between beats")
    ap.add_argument("--pause", type=float, default=0.0, help="replay --auto: seconds to wait before each beat")
    ap.add_argument("--video", help="check: the backup video file")
    ap.add_argument("--device", action="store_true", help="check: also look at Gary on this machine (run it on the Pi)")
    ap.add_argument("--cache", default=os.path.join(ROOT, "scout", "cached_quests.json"), help="the scout's cached quests")
    ap.add_argument("--runs", default=os.path.join(ROOT, "scout", "runs.jsonl"), help="the scout's run log")
    args = ap.parse_args(argv)
    api = args.api.rstrip("/")
    try:
        if args.what == "check":
            return run_check(api, args)
        if args.what == "reset":
            return run_reset(api, args)
        return run_replay(api, args)
    except Offline as exc:
        sys.exit("Lost the backend at %s (%s)." % (api, exc))
    except Refused as exc:
        sys.exit("The backend at %s answered with an error: %s" % (api, exc))


if __name__ == "__main__":
    sys.exit(main())
