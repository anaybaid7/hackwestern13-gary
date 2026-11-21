"""Gary's game rules.

Pure functions: events and quests go in, the state the web page draws comes
out. Nothing here knows about HTTP or storage, so every rule can be tested by
calling compute() with a list.

The device only reports facts (what, when, friend or not). Everything that is
a judgement lives in this file: XP, stages, naps, the map, the herd.

Owner: backend (pillar B). Starting values are from docs/PLAN.md.
"""
import datetime as dt
import json

# --- XP: the big rewards need a quest, the outdoors or a friend -------------
XP_NEW_OUTDOOR = 10      # first find of an outdoor thing
XP_NEW_INDOOR = 2        # first find of an indoor thing
XP_REPEAT = 1            # a thing Gary has seen before
FRIEND_MULTIPLIER = 2    # a friend in frame doubles that sniff
XP_WELCOME_BACK = 15     # first sniff after a nap; never doubled

# --- Stages: (id, XP needed). The web swaps images by id. -------------------
STAGES = [("kid", 0), ("scrambler", 60), ("ibex", 150), ("summit-elder", 300)]

NAP_SECONDS = 8 * 3600          # quiet for this long and Gary naps
WELCOME_BACK_SHOWS_FOR = 600    # how long the welcome-back flag stays up
MAP_TILES = 25                  # the map shows the newest 25 places
JOURNAL_LIMIT = 50

# --- Herd Cup: seeded rivals until real herds exist (issue #19) --------------
RIVAL_HERDS = [("Cliff Hangers", 6), ("The Bleat Goes On", 4), ("Summit Else", 2)]
HERD_BADGES = [("first-herd", 1), ("herd-of-five", 5)]


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


def pick_quest(event, quests, done):
    """Which open quest, if any, does this discovery complete?

    A quest completes when its target is the thing found. A herd quest also
    needs a friend in frame. If the device named a quest, that one wins.
    """
    label, friend = event.get("label"), bool(event.get("friend"))
    fits = [q for q in quests
            if q["id"] not in done and q["target"] == label and (friend or not q.get("herd"))]
    for q in fits:
        if q["id"] == event.get("quest_id"):
            return q
    return fits[0] if fits else None


def iso_week(when):
    year, week, _ = when.isocalendar()
    return "%d-W%02d" % (year, week)


def compute(events, quests, outdoor, now, nap_seconds=NAP_SECONDS):
    """Fold every event, in arrival order, into the state.

    events   list of event dicts (contract/examples/event.*.json)
    quests   list of quest dicts, oldest first
    outdoor  {label: bool} from contract/labels.json
    now      aware datetime
    Returns (state, results). results maps event id -> what that event earned.
    The same inputs always give the same output.
    """
    xp, found, done = 0, [], set()
    journal, results = [], {}
    shared, shared_this_week = 0, 0
    last_when, last_was_return = None, False
    this_week = iso_week(now)

    for ev in events:
        kind = ev.get("type")
        if kind != "discovery":
            results[ev.get("id")] = {"xp": 0, "reaction": kind or "unknown", "new": False, "quest_id": None}
            continue
        label, friend = ev.get("label"), bool(ev.get("friend"))
        when = parse_ts(ev.get("ts"))
        is_new = label not in found
        quest = pick_quest(ev, quests, done)

        if quest:
            gained, reaction = int(quest.get("xp", 0)), "quest_complete"
            done.add(quest["id"])
        elif is_new:
            gained = XP_NEW_OUTDOOR if outdoor.get(label, False) else XP_NEW_INDOOR
            reaction = "new_discovery"
        else:
            gained, reaction = XP_REPEAT, "seen_before"
        if friend:
            gained *= FRIEND_MULTIPLIER
            shared += 1
            if when and iso_week(when) == this_week:
                shared_this_week += 1

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
            "latency_ms": ev.get("latency_ms"), "xp": gained,
        }
        journal.append(entry)
        results[ev.get("id")] = {"xp": gained, "reaction": reaction, "new": is_new, "quest_id": entry["quest_id"]}

    # Gary himself
    index, stage, stage_xp, next_xp = stage_for(xp)
    idle = (now - last_when).total_seconds() if last_when else None
    napping = idle is None or idle >= nap_seconds
    welcome_back = bool(last_was_return and idle is not None and idle < WELCOME_BACK_SHOWS_FOR)

    # The map: one tile per real place, newest 25. Fog lifts when a quest there is done.
    tiles, seen_places = [], {}
    for q in quests:
        place = q.get("place")
        if not place:
            continue
        if place not in seen_places:
            seen_places[place] = {"place": place, "quest_id": q["id"], "cleared": False}
            tiles.append(seen_places[place])
        if q["id"] in done:
            seen_places[place]["cleared"] = True
    tiles = tiles[-MAP_TILES:]

    # The herd, and the weekly Herd Cup. Herds are ranked; people never are.
    table = [{"herd": name, "score": score} for name, score in RIVAL_HERDS]
    table.append({"herd": "Your herd", "score": shared_this_week, "you": True})
    table.sort(key=lambda row: (-row["score"], bool(row.get("you"))))
    rank = next(i for i, row in enumerate(table) if row.get("you")) + 1
    shown = table[:3] if rank <= 3 else table[:3] + [table[rank - 1]]

    open_quests = [q for q in quests if q["id"] not in done]
    state = {
        "gary": {"stage": stage, "stage_index": index, "xp": xp, "stage_xp": stage_xp,
                 "next_stage_xp": next_xp, "napping": napping, "welcome_back": welcome_back},
        "quest": open_quests[0] if open_quests else None,
        "quests_open": len(open_quests),
        "journal": list(reversed(journal))[:JOURNAL_LIMIT],
        "guide": {"total": len(outdoor), "found": found},
        "map": tiles,
        "herd": {
            "badges": [name for name, need in HERD_BADGES if shared >= need],
            "shared": shared,
            "cup": {"week": this_week, "rank": rank, "demo": True, "table": shown},
        },
    }
    return state, results, done
