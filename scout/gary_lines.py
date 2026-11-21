#!/usr/bin/env python3
"""gary_lines.py - Gemini writes Gary's lines for the web page, once.

    python3 scout/gary_lines.py            writes web/src/gary_lines.json
    python3 scout/gary_lines.py --progress only the home-screen progress templates

For each of the things Gary can recognise (contract/labels.json): one line for
finding it, and two facts about it. Plus bigger pools of his everyday lines
(a quest done, a new find, one seen again, a friend in frame, napping, welcome
back, awake). The page reads the file, so Gary talks with no network at all,
and the same find always gets the same words. Read the file before you commit
it: every fact should be one you would tell a child.

Every line passes the same checks as the trail tidbits (gary_voice.safe_line):
short, plain words, nothing about eating, touching or feeding anything.
Needs GEMINI_API_KEY (scout/.env).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "web", "src", "gary_lines.json")
BATCH = 15

GARY = """You are Gary, a pocket mountain goat who goes on small outdoor quests with people.
Gary is dry, nosy and kind, unimpressed by flat ground, and proud of climbing. He never nags, rushes or guilts anyone.
Missing a day is just a nap to him."""

THINGS_PROMPT = GARY + """

For each thing below, write:
- "line": what Gary says the first time he sniffs one. One dry, funny sentence, at most 90 characters, starting with "A" or "An" and the thing.
- "facts": two true, well-known facts about the thing, said by Gary, each at most 130 characters. A child should be able to repeat them.
Rules: no numbers unless you are sure; never suggest eating, tasting, touching, picking or feeding anything; no emoji; no quotation marks.
Things: {things}
Reply as a JSON object mapping each thing, exactly as written, to {{"line": ..., "facts": [..., ...]}}."""

POOLS = {
    "quest": "the person just finished the quest Gary asked for",
    "new": "the person just showed Gary something he had never sniffed before",
    "again": "the person showed Gary something he has seen before (it still counts, a little)",
    "friend": "a friend was in the frame too (a short add-on sentence, said after another line)",
    "napping": "Gary is napping because it has been quiet; it costs nothing and is no one's fault",
    "welcome_back": "the person is back after a quiet spell; Gary is glad, no guilt at all",
    "awake": "Gary is awake and waiting to be pointed at something",
}
POOLS_PROMPT = GARY + """

For each situation below, write 6 different things Gary might say, each at most 80 characters, one or two short sentences.
No emoji, no quotation marks, no guilt, no hurry.
Situations: {situations}
Reply as a JSON object mapping each situation name to a list of 6 strings."""


# Gary's line on the home screen, about the person's own progress. Gemini
# writes templates once; the page fills the {slots} from the state, so the
# line is personal and needs no network. Each situation: (when, slots it must use).
PROGRESS = {
    "start": ("no finds yet today, and there is a quest to do", ["target", "place"]),
    "today": ("the person has found things today", ["finds_today"]),
    "almost": ("Gary is close to growing into his next stage", ["xp_left", "next_stage"]),
    "guide": ("how full Gary's field guide of things is", ["guide"]),
    "encourage": ("a warm nudge about body, mind or friends outdoors: getting outside, moving at any pace, noticing "
                  "small things, feeling calmer, a place never visited, bringing a friend. Never pressure, and never "
                  "claim that it improves anyone's health", []),
}
SLOTS = {"target": "the thing to find, with a or an (a bench)", "place": "where the quest is (Harris Park)",
         "finds_today": "how many finds today, with the word (3 finds, 1 find)", "last": "the last thing found (a squirrel)",
         "xp_left": "XP still needed to grow (20 XP)", "next_stage": "Gary's next stage name (Ibex)",
         "guide": "how many things found of all (12 of 90 things)"}
PROGRESS_PROMPT = GARY + """

Write lines Gary says on the home screen about the person's own progress. Each line is a template:
put a slot name in curly braces where a value goes. The slots are:
{slots}
For each situation below write 8 lines. Each must use the slots listed for it, may use {{last}}, and no other slots.
At most 80 characters before the slots are filled. No emoji, no quotation marks, no guilt, no hurry, never "you should".
Situations:
{situations}
Reply as a JSON object mapping each situation name to a list of 8 strings."""


def progress_templates(key, model=None, ask=None):
    """{situation: [templates]} that use only the allowed slots and every required one."""
    import gary_voice
    from scout import risk_in
    ask = ask or ask_json
    reply = ask(PROGRESS_PROMPT.format(
        slots="\n".join("{%s}: %s" % kv for kv in SLOTS.items()),
        situations="\n".join("%s (%s): must use %s" % (name, when, ", ".join("{%s}" % s for s in need))
                              for name, (when, need) in PROGRESS.items())), key, model)
    out = {}
    for name, (_, need) in PROGRESS.items():
        good = []
        for line in (reply.get(name) or []) if isinstance(reply, dict) else []:
            used = set(re.findall(r"\{(\w+)\}", line)) if isinstance(line, str) else {"?"}
            if used <= set(need) | {"last"} and set(need) <= used and gary_voice.safe_line(line.replace("{", "").replace("}", ""), risk_in, 90):
                good.append(line.strip())
        out[name] = good[:8]
    return out


def labels():
    with open(os.path.join(ROOT, "contract", "labels.json"), encoding="utf-8") as f:
        return [item["name"] for item in json.load(f)["labels"]]


def ask_json(prompt, key, model):
    import gary_voice
    text = gary_voice.ask(prompt, key, model, as_json=True, timeout=90)
    try:
        return json.loads(text) if text else {}
    except ValueError:
        return {}


def build(key, model=None, say=print, ask=ask_json):
    """-> the file's content. Things Gemini gave nothing usable for are left out:
    the page falls back to its hand-written lines for them."""
    import gary_voice
    from scout import risk_in
    ok = lambda line, limit: gary_voice.safe_line(line, risk_in, limit)  # noqa: E731
    things, names = {}, labels()
    for start in range(0, len(names), BATCH):
        batch = names[start:start + BATCH]
        reply = ask(THINGS_PROMPT.format(things=", ".join(batch)), key, model)
        for name in batch:
            got = reply.get(name) if isinstance(reply, dict) else None
            if not isinstance(got, dict):
                continue
            line = got.get("line") if ok(got.get("line"), 100) else None
            facts = [f.strip() for f in got.get("facts") or [] if ok(f, 140)][:2]
            if line or facts:
                things[name] = {"line": line, "facts": facts}
        say("things %d-%d: %d with lines" % (start + 1, start + len(batch), sum(n in things for n in batch)))
    reply = ask(POOLS_PROMPT.format(situations="; ".join("%s: %s" % kv for kv in POOLS.items())), key, model)
    pools = {name: [line.strip() for line in (reply.get(name) or []) if ok(line, 90)][:6]
             for name in POOLS} if isinstance(reply, dict) else {}
    return {"_note": "Written by scout/gary_lines.py with Gemini, then read by a person. Edit by hand freely.",
            "things": things, "pools": pools}


def main():
    sys.path.insert(0, HERE)
    import scout
    scout.load_settings()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("Set GEMINI_API_KEY in scout/.env first (a free key from Google AI Studio).")
    if "--progress" in sys.argv[1:]:  # only the progress templates; the rest of the file, read and fixed by hand, stays
        with open(OUT, encoding="utf-8") as f:
            content = json.load(f)
        content["progress"] = progress_templates(key, os.environ.get("GEMINI_MODEL"))
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("Wrote the progress templates: %s" % {k: len(v) for k, v in content["progress"].items()})
        return
    content = build(key, os.environ.get("GEMINI_MODEL"))
    content["progress"] = progress_templates(key, os.environ.get("GEMINI_MODEL"))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("Wrote %s: %d things, %d pools. Read it before you commit it."
          % (os.path.relpath(OUT, ROOT), len(content["things"]), sum(1 for v in content["pools"].values() if v)))


if __name__ == "__main__":
    main()
