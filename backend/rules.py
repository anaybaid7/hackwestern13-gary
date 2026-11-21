"""Gary's game rules.

Pure functions: events and quests go in, the state the web page draws comes
out. Nothing here knows about HTTP or storage, so every rule can be tested by
calling compute() with a list.

The device only reports facts (what, when, friend or not). Everything that is
a judgement lives in this file: XP, stages, naps, the map, the herd, the
active quest, and the private wellness numbers.

Product rules this file must never break (CONTEXT.md, section 8):
no penalties, no individual rankings, mood is private, every stage solo.

Owner: backend (pillar B).
"""
import datetime as dt
import json

# --- XP: the big rewards need a quest, the outdoors or a friend -------------
XP_NEW_OUTDOOR = 10      # first find of an outdoor thing
XP_NEW_INDOOR = 2        # first find of an indoor thing
XP_REPEAT = 1            # a thing Gary has seen before
FRIEND_MULTIPLIER = 2    # a friend in frame doubles that sniff
XP_WELCOME_BACK = 15     # first sniff after a nap; never doubled
XP_BEEN_THERE = 10       # a quest finished at its place (the page said you were there); never doubled
VISIT_BEFORE = 2 * 3600  # a visit this long before the sniff counts...
VISIT_AFTER = 30 * 60    # ...and this long after (the page may report late)

# --- Stages: (id, XP needed). The web swaps images by id. -------------------
STAGES = [("kid", 0), ("scrambler", 60), ("ibex", 150), ("summit-elder", 300)]

NAP_SECONDS = 8 * 3600          # quiet for this long and Gary naps
WELCOME_BACK_SHOWS_FOR = 600    # how long the welcome-back flag stays up
MAP_TILES = 25                  # the map shows the newest 25 places
JOURNAL_LIMIT = 50

# --- Herd Mode ---------------------------------------------------------------
# Badges are earned together and never taken away. (id, what earns it)
HERD_BADGES = [
    ("first-herd", lambda h: h["shared"] >= 1),         # one find with a friend in frame
    ("herd-quest", lambda h: h["quests"] >= 1),         # one quest finished together
    ("herd-of-five", lambda h: h["shared"] >= 5),       # five finds together
    ("trail-mates", lambda h: h["places"] >= 3),        # three places uncovered together
]
# The Herd Cup ranks herds by what they did together this week: quests
# finished with a friend in frame, plus places uncovered together. It resets
# every Monday. People are never ranked, and the table never shows last place.
# Until real herds exist the rivals are seeded demo data, marked demo: true.
RIVAL_HERDS = [("Cliff Hangers", 6), ("The Bleat Goes On", 4), ("Summit Else", 2),
               ("Kid You Not", 1), ("Slow and Steady", 0)]
CUP_SHOWN = 3  # the table is the top three herds, plus yours

# --- Wellness (private) ------------------------------------------------------
PAIR_WITHIN_SECONDS = 12 * 3600   # an "after" answers a "before" from the same outing
OUTDOOR_BLOCK_MINUTES = 10        # each 10-minute block with an outdoor find counts as 10 minutes outdoors
OUTDOOR_NOTE = ("An estimate from Gary's sniffs: each %d-minute block with an outdoor find "
                "counts as %d minutes outdoors." % (OUTDOOR_BLOCK_MINUTES, OUTDOOR_BLOCK_MINUTES))


def load_labels(path):
    """contract/labels.json -> (friend label, {name: is_outdoor})."""
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    return doc["friend"], {item["name"]: bool(item["outdoor"]) for item in doc["labels"]}


def parse_ts(text):
    """'2026-11-21T05:20:00Z' -> aware datetime, or None if it cannot be read."""
    if not isinstance(text, str):
        return None
    try:
        when = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc)


def stage_for(xp):
    """-> (index, id, XP where this stage starts, XP for the next stage or None)."""
    index = 0
    for i, (_, need) in enumerate(STAGES):
        if xp >= need:
            index = i
    nxt = STAGES[index + 1][1] if index + 1 < len(STAGES) else None
    return index, STAGES[index][0], STAGES[index][1], nxt


def place_key(place):
    """Two spellings of one place are one map tile."""
    return " ".join(str(place or "").lower().split())


def iso_week(when, tz=dt.timezone.utc):
    """The week a moment falls in, in local time: weeks turn over on Monday."""
    year, week, _ = when.astimezone(tz).isocalendar()
    return "%d-W%02d" % (year, week)


def local_day(when, tz=dt.timezone.utc):
    return when.astimezone(tz).date().isoformat()


# --------------------------------------------------------------------------
# Quests: which one a sniff finishes, and which one is active
# --------------------------------------------------------------------------
def pick_quest(event, quests, done, active_id=None):
    """Which open quest, if any, does this discovery complete?

    A quest completes when its target is the thing found. A herd quest also
    needs a friend in frame. When several open quests fit, the one the person
    chose on the web page wins, then the one the device named, then the oldest.
    The device makes the same choice from the same facts (choose_quest in
    device/gary_device.py).
    """
    label, friend = event.get("label"), bool(event.get("friend"))
    fits = [q for q in quests
            if q["id"] not in done and q["target"] == label and (friend or not q.get("herd"))]
    for wanted in (active_id, event.get("quest_id")):
        for q in fits:
            if wanted and q["id"] == wanted:
                return q
    return fits[0] if fits else None


def candidates(quests, done, time, now, tz=dt.timezone.utc):
    """Open quests of one length ("short" or "long"), best first:

      1. the scout's quests dated today
      2. anything else dated today, except the built-in quests
      3. the scout's older quests, newest first
      4. the rest: the built-in ("seed") quests and older hand-made ones

    A real place the scout found yesterday still beats a built-in quest, and
    the built-in quests come last on every day, also on the day they are dated.
    Within a group the stored order holds, so the answer is the same on every
    screen."""
    today = local_day(now, tz)

    def rank(q):
        source = q.get("source")
        if q.get("day") == today and source != "seed":
            return (0 if source == "tinyfish" else 1, 0)
        if source == "tinyfish":
            return (2, -_day_number(q.get("day")))
        return (3, 0)

    pool = [q for q in quests if q["id"] not in done and q.get("time") == time]
    return sorted(pool, key=rank)  # sorted() keeps the stored order between equals


def _day_number(day):
    """"2026-11-21" -> a number that grows by one a day. 0 for anything else."""
    try:
        return dt.date.fromisoformat(str(day)).toordinal()
    except ValueError:
        return 0


def choose(quests, done, time, now, tz=dt.timezone.utc, current_id=None):
    """The quest a press of "short" or "long" makes active, or None when no
    quest of that length is open. Pressing the same button again moves on to
    the next one, so a quest that does not suit can be skipped."""
    pool = candidates(quests, done, time, now, tz)
    if not pool:
        return None
    ids = [q["id"] for q in pool]
    if current_id in ids and len(pool) > 1:
        return pool[(ids.index(current_id) + 1) % len(pool)]
    return pool[0]


# --------------------------------------------------------------------------
# The state
# --------------------------------------------------------------------------
def compute(events, quests, outdoor, now, nap_seconds=NAP_SECONDS, tz=dt.timezone.utc):
    """Fold every event, in arrival order, into the state.

    events   list of event dicts: discovery, miss, and the server's own
             "choice" events (a press of short or long on the web page)
    quests   list of quest dicts, oldest first
    outdoor  {label: bool} from contract/labels.json
    now      aware datetime
    tz       the timezone that days and weeks are counted in
    Returns (state, results, done). results maps event id -> what that event
    earned; done is the set of finished quest ids.
    The same inputs always give the same output.
    """
    by_id = {q["id"]: q for q in quests}
    xp, found, done = 0, [], set()
    journal, results = [], {}
    herd = {"shared": 0, "quests": 0, "places": 0}       # ever: for badges
    cup = {"quests": 0, "places": 0}                     # this week: for the Herd Cup
    cleared = {}        # place key -> when its fog lifted
    finds_at = {}       # place key -> what was found there
    choices = []        # (when, time, quest id), oldest first
    last_when, last_was_return = None, False
    this_week = iso_week(now, tz)
    # Visits first, so a visit that arrives after its sniff still counts.
    visits = {}         # quest id -> [when the page was at its place]
    for ev in events:
        if ev.get("type") == "visit":
            visits.setdefault(ev.get("quest_id"), []).append(parse_ts(ev.get("ts")))

    def been_there(quest_id, when):
        return bool(when) and any(at and -VISIT_AFTER <= (when - at).total_seconds() <= VISIT_BEFORE
                                  for at in visits.get(quest_id, []))

    def active_at(when):
        """The quest the person had chosen at that moment, or None."""
        picked = None
        for chosen_when, _, quest_id in choices:
            if when is None or chosen_when is None or chosen_when <= when:
                picked = quest_id
        return picked

    for ev in events:
        kind = ev.get("type")
        if kind == "visit":
            results[ev.get("id")] = {"xp": 0, "reaction": "visit", "new": False, "quest_id": ev.get("quest_id")}
            continue
        if kind == "choice":
            choices.append((parse_ts(ev.get("ts")), ev.get("time"), ev.get("quest_id")))
            results[ev.get("id")] = {"xp": 0, "reaction": "choice", "new": False, "quest_id": ev.get("quest_id")}
            continue
        if kind != "discovery":
            results[ev.get("id")] = {"xp": 0, "reaction": kind or "unknown", "new": False, "quest_id": None}
            continue
        label, friend = ev.get("label"), bool(ev.get("friend"))
        when = parse_ts(ev.get("ts"))
        is_new = label not in found
        quest = pick_quest(ev, quests, done, active_at(when))

        if quest:
            gained, reaction = int(quest.get("xp", 0)), "quest_complete"
            done.add(quest["id"])
        elif is_new:
            gained = XP_NEW_OUTDOOR if outdoor.get(label, False) else XP_NEW_INDOOR
            reaction = "new_discovery"
        else:
            gained, reaction = XP_REPEAT, "seen_before"
        in_cup = bool(friend and when and iso_week(when, tz) == this_week)
        if friend:
            gained *= FRIEND_MULTIPLIER
            herd["shared"] += 1
        there = bool(quest) and been_there(quest["id"], when)
        if there:
            gained += XP_BEEN_THERE

        # A quest lifts the fog over its place. With a friend it also counts for the herd.
        place = None
        if quest and quest.get("place"):
            place, key = quest["place"], place_key(quest["place"])
            finds_at.setdefault(key, []).append(
                {"label": label, "ts": ev.get("ts"), "friend": friend, "quest_id": quest["id"]})
            first_here = key not in cleared
            if first_here:
                cleared[key] = ev.get("ts")
            if friend and first_here:
                herd["places"] += 1
                cup["places"] += int(in_cup)
        if quest and friend:
            herd["quests"] += 1
            cup["quests"] += int(in_cup)

        # Coming back after a nap earns a small bonus. Missing days costs nothing.
        last_was_return = bool(when and last_when and (when - last_when).total_seconds() >= nap_seconds)
        if last_was_return:
            gained += XP_WELCOME_BACK
        if when:
            last_when = when

        if is_new:
            found.append(label)
        xp += gained
        entry = {
            "id": ev.get("id"), "ts": ev.get("ts"), "label": label, "score": ev.get("score"),
            "friend": friend, "new": is_new, "quest_id": quest["id"] if quest else None,
            "latency_ms": ev.get("latency_ms"), "xp": gained, "place": place, "been_there": there,
        }
        journal.append(entry)
        results[ev.get("id")] = {"xp": gained, "reaction": reaction, "new": is_new, "quest_id": entry["quest_id"]}

    # Gary himself
    index, stage, stage_xp, next_xp = stage_for(xp)
    idle = (now - last_when).total_seconds() if last_when else None
    napping = idle is None or idle >= nap_seconds
    welcome_back = bool(last_was_return and idle is not None and idle < WELCOME_BACK_SHOWS_FOR)

    # The map: one tile per real place, newest 25. Fog lifts when a quest there is done.
    tiles, seen_places = [], set()
    for q in quests:
        key = place_key(q.get("place"))
        if not key or key in seen_places:
            continue
        seen_places.add(key)
        tiles.append({"place": q["place"], "quest_id": q["id"], "cleared": key in cleared,
                      "cleared_at": cleared.get(key), "finds": finds_at.get(key, []),
                      "lat": q.get("lat"), "lng": q.get("lng"),
                      "visited": any(visits.get(other["id"]) for other in quests
                                     if place_key(other.get("place")) == key)})
    tiles = tiles[-MAP_TILES:]

    # The quest to show: the chosen one while it is open, then the next of the
    # same length, then the oldest open quest.
    open_quests = [q for q in quests if q["id"] not in done]
    choice_time, choice_id = (choices[-1][1], choices[-1][2]) if choices else (None, None)
    options = {t: (candidates(quests, done, t, now, tz) or [None])[0] for t in ("short", "long")}
    active = None
    if choice_time:
        chosen = by_id.get(choice_id)
        active = chosen if chosen and chosen["id"] not in done else options.get(choice_time)
        if active is not None:
            options[choice_time] = active
    if active is None:
        active = open_quests[0] if open_quests else None

    # The herd, and the weekly Herd Cup. Herds are ranked; people never are.
    score = cup["quests"] + cup["places"]
    table = [{"herd": name, "score": rival} for name, rival in RIVAL_HERDS]
    table.append({"herd": "Your herd", "score": score, "quests": cup["quests"], "places": cup["places"], "you": True})
    table.sort(key=lambda row: (-row["score"], not row.get("you")))   # a tie goes to you
    rank = next(i for i, row in enumerate(table) if row.get("you")) + 1
    shown = table[:CUP_SHOWN] if rank <= CUP_SHOWN else table[:CUP_SHOWN] + [table[rank - 1]]
    ahead = table[rank - 2] if rank > 1 else None

    state = {
        "gary": {"stage": stage, "stage_index": index, "xp": xp, "stage_xp": stage_xp,
                 "next_stage_xp": next_xp, "napping": napping, "welcome_back": welcome_back},
        "quest": active,
        "quest_choice": choice_time,
        "quest_options": options,
        "quests_open": len(open_quests),
        "journal": list(reversed(journal))[:JOURNAL_LIMIT],
        "guide": {"total": len(outdoor), "found": found},
        "map": tiles,
        "herd": {
            "badges": [name for name, earned in HERD_BADGES if earned(herd)],
            "shared": herd["shared"],
            "quest": next((q for q in open_quests if q.get("herd")), None),
            "cup": {"week": this_week, "rank": rank, "herds": len(table), "demo": True, "table": shown,
                    # The herd just above yours, and how many more points pass it (a tie goes to you).
                    "ahead": {"herd": ahead["herd"], "score": ahead["score"], "gap": ahead["score"] - score}
                    if ahead else None},
        },
    }
    return state, results, done


# --------------------------------------------------------------------------
# Wellness: private. Never part of the state above.
# --------------------------------------------------------------------------
def outdoor_by_day(events, outdoor, tz=dt.timezone.utc):
    """Estimated minutes outdoors per local day, oldest day first.

    Each 10-minute block that holds at least one outdoor find counts as 10
    minutes. PostgresStore.outdoor_by_day() is the same sum as one time_bucket
    query; the tests check that the two agree.
    """
    blocks = {}
    for ev in events:
        if ev.get("type") != "discovery" or not outdoor.get(ev.get("label"), False):
            continue
        when = parse_ts(ev.get("ts"))
        if when is None:
            continue
        block = int(when.timestamp()) // (OUTDOOR_BLOCK_MINUTES * 60)
        blocks.setdefault(local_day(when, tz), set()).add(block)
    return [{"day": day, "minutes": len(found) * OUTDOOR_BLOCK_MINUTES} for day, found in sorted(blocks.items())]


def mood_pairs(moods, tz=dt.timezone.utc):
    """Match each "after" to the "before" of the same outing."""
    stamped = sorted(((parse_ts(m.get("ts")), i, m) for i, m in enumerate(moods)
                      if parse_ts(m.get("ts")) is not None), key=lambda item: (item[0], item[1]))
    pairs, before = [], None
    for when, _, mood in stamped:
        if mood.get("phase") == "before":
            before = (when, mood)
        elif mood.get("phase") == "after" and before is not None:
            started, first = before
            if (when - started).total_seconds() <= PAIR_WITHIN_SECONDS:
                pairs.append({"day": local_day(when, tz), "before": first["value"], "after": mood["value"],
                              "change": mood["value"] - first["value"], "before_ts": first.get("ts"),
                              "after_ts": mood.get("ts"),
                              "minutes": int(round((when - started).total_seconds() / 60.0))})
            before = None
    return pairs


def mood_summary(pairs):
    """One careful sentence. It reports what the person said, and never claims
    that an outing caused a feeling."""
    total = len(pairs)
    if total == 0:
        return "No before-and-after check-ins yet. They are always optional."
    better = sum(1 for p in pairs if p["change"] > 0)
    same = sum(1 for p in pairs if p["change"] == 0)
    lower = total - better - same
    if total == 1:
        word = "better" if better else ("about the same" if same else "lower")
        return "You reported feeling %s after your outing." % word
    if better:
        return "You reported feeling better after %d of %d outings." % (better, total)
    if same == total:
        return "You reported feeling about the same after %d outings." % total
    return "You reported feeling lower after %d of %d outings." % (lower, total)


def wellness(moods, events, outdoor, tz=dt.timezone.utc, outdoor_days=None):
    """What GET /api/wellness returns. Only the person themself sees it.

    outdoor_days lets the store supply the per-day minutes from its own query
    (time_bucket on Tiger Data). Left out, they are worked out here.
    """
    finds = [ev for ev in events if ev.get("type") == "discovery"]
    shared = sum(1 for ev in finds if ev.get("friend"))
    days = outdoor_days if outdoor_days is not None else outdoor_by_day(events, outdoor, tz)
    pairs = mood_pairs(moods, tz)
    start_of_time = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    checkins = sorted(({"ts": m.get("ts"), "phase": m.get("phase"), "value": m.get("value"),
                        "source": m.get("source", "web")} for m in moods),
                      key=lambda m: parse_ts(m["ts"]) or start_of_time)
    return {
        "private": True,
        "checkins": checkins,
        "pairs": pairs,
        "summary": mood_summary(pairs),
        "outdoor": days,
        "outdoor_minutes": sum(day["minutes"] for day in days),
        "outdoor_note": OUTDOOR_NOTE,
        "finds": len(finds),
        "shared": shared,
        "solo": len(finds) - shared,
    }
