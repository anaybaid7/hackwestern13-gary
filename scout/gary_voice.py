#!/usr/bin/env python3
"""gary_voice.py - Gemini puts a quest in Gary's voice: its title, and two or
three trail tidbits Gary says on the way (issue #37).

The quest itself still comes from the scout: the place, the thing to find, the
length and the safety note are never touched. Gemini only rewords the title,
and a rewording is kept only if it still names the place and the thing, is
short, and says nothing risky. Anything else, including any error, keeps the
plain title. So this can never break a quest. If Gemini cannot be asked at all
(the key, the model name, the network), it says why once and stops asking.

    export GEMINI_API_KEY=...          # a free key from Google AI Studio
    python3 scout/scout.py --voice

    export GEMINI_MODEL=...            # optional. Model names change often:
                                       # check ai.google.dev for the current one

Tidbits come from the text the TinyFish agent read about the place. With no
text (a cached quest) Gary talks about the kind of place and the thing to find,
never claims a fact about that place, and never says anything is safe to eat,
touch or feed. A tidbit that fails a check is dropped; a quest never fails.
"""
import json
import os
import re
import urllib.error
import urllib.request

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
DEFAULT_MODEL = "gemini-3.5-flash-lite"   # under a second a line; gemini-flash-latest timed out
MAX_LENGTH = 90
TIDBIT_MAX = 160
# Never from Gary: foraging, touching or feeding wildlife, or going off the path.
# "Ducks swim" and "goats climb" are fine; "go for a swim" and "climb it" are not.
UNSAFE = re.compile(r"edible|forag|safe to eat|you can eat|\beat (it|one|them|some)\b|\btaste|\blick|"
                    r"pick (it|one|them|some)|feed (it|them|the|a)|pet (it|them|the|a)\b|touch (it|them|the|a)\b|"
                    r"off the (trail|path)|go (for a )?swim|swim (in|here|there)|climb (it|on|over|up|the)\b", re.I)

TIDBITS_PROMPT = """You are Gary, a pocket mountain goat who walks with people on small outdoor quests in London, Ontario.
Gary is dry, curious and kind. He never nags, rushes or guilts anyone.

Write {count} short things Gary might say on the way to this quest: tidbits that make the walk more interesting.
Quest: {title}
Place: {place}
Thing to find: {target}
What a web page said about the place: {about}

Rules:
- Facts about {place} itself may come ONLY from the web page text above. If that text is empty or says little,
  talk instead about the kind of place (a park, a bog, a river valley) or about {target}s in general.
- Only well-known, true facts. No numbers or dates unless the page text gives them.
- Never suggest eating, tasting, picking, touching or feeding anything, swimming, climbing, or leaving the path.
- Each at most 140 characters, one sentence or two, no emoji, no quotation marks.
Reply as a JSON array of strings only."""

PROMPT = """You write one short line as Gary, a pocket mountain goat who sends people on small outdoor quests.
Gary is dry, curious and kind. He never nags, never rushes anyone and never makes anyone feel guilty.

Reword this quest the way Gary would say it.
Rules:
- Keep the place name "{place}" exactly as written.
- Keep the word "{target}" exactly as written.
- At most 80 characters. One line. No emoji. No quotation marks.
- Nothing about danger, climbing fences, private land, speed or beating anyone.
{herd}
Reply with the line only.

Quest: {title}"""


def acceptable(line, quest, risk_in):
    """Is Gemini's line safe to use in place of the plain title?"""
    if not line or "\n" in line or len(line) > MAX_LENGTH:
        return False
    lowered = line.lower()
    if quest["place"].lower() not in lowered or quest["target"].lower() not in lowered:
        return False
    if quest.get("herd") and ("friend" not in lowered or re.search(r"if you like|if you want|optional|or not|or alone", lowered)):
        return False  # a co-op quest must still say it needs a friend, and not make it sound optional
    if risk_in(line) or not line.isprintable():
        return False
    if re.search(r"https?:|www\.|[<>{}\[\]]", lowered):
        return False  # a title is words, never a link or markup
    return not re.search(r"hurry|quick|fast|race|beat|lazy|should|must|guilt|fence|private", lowered)


class VoiceError(Exception):
    """Gemini could not be asked at all: the key, the model name or the network."""


def ask(prompt, key, model=None, opener=urllib.request.urlopen, as_json=False, timeout=30):
    """One Gemini call. Returns the reply text, or None when the reply holds
    none. Raises VoiceError when Gemini cannot be asked at all."""
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if as_json:
        body["generationConfig"] = {"responseMimeType": "application/json"}
    body = json.dumps(body).encode("utf-8")
    name = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
    req = urllib.request.Request(GEMINI_URL % name, data=body,
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with opener(req, timeout=timeout) as reply:
            data = json.loads(reply.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        hints = {400: "the request or the key was not accepted",
                 401: "the key was not accepted", 403: "the key may not use this model",
                 404: "there is no model called %s. Set GEMINI_MODEL to a current one from ai.google.dev" % name,
                 429: "too many requests, or no quota left"}
        raise VoiceError("Gemini answered HTTP %d: %s" % (exc.code, hints.get(exc.code, "see Google's Gemini API pages")))
    except OSError as exc:
        raise VoiceError("could not reach Gemini (%s)" % exc)
    except ValueError:
        return None
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return None
    return str(text).strip() or None


def gary_title(quest, key, model=None, opener=urllib.request.urlopen):
    """Gemini's rewording of a quest title, or None."""
    prompt = PROMPT.format(place=quest["place"], target=quest["target"], title=quest["title"],
                           herd='- It needs a friend: keep the word "friend".' if quest.get("herd") else "")
    text = ask(prompt, key, model, opener)
    return (text.strip('"').strip("'").strip() or None) if text else None


def safe_line(line, risk_in, limit=TIDBIT_MAX):
    """A line Gary may say: short, plain words, nothing risky or unsafe."""
    return (isinstance(line, str) and 0 < len(line.strip()) <= limit and "\n" not in line and line.isprintable()
            and not risk_in(line) and not UNSAFE.search(line)
            and not re.search(r"https?:|www\.|[<>{}\[\]\"]", line))


def gary_tidbits(quest, about, key, risk_in, model=None, opener=urllib.request.urlopen, count=3):
    """Up to `count` trail tidbits that pass the checks (maybe none)."""
    prompt = TIDBITS_PROMPT.format(count=count, title=quest["title"], place=quest["place"], target=quest["target"],
                                   about=(about or "")[:1500] or "(none)")
    text = ask(prompt, key, model, opener, as_json=True)
    try:
        lines = json.loads(text) if text else []
    except ValueError:
        return []
    if not isinstance(lines, list):
        return []
    return [line.strip() for line in lines if safe_line(line, risk_in)][:count]


def apply(quests, key, say=print, model=None, opener=urllib.request.urlopen):
    """Reword the titles in place where Gemini gives a line that passes the
    checks, and add trail tidbits ("tidbits", from the quest's "_about": the
    page text). Returns how many titles changed."""
    if not key:
        say("  --voice needs GEMINI_API_KEY. The plain titles are kept.")
        return 0
    from scout import risk_in  # the same safety check the scout uses
    changed = 0
    for quest in quests:
        try:
            line = gary_title(quest, key, model, opener)
        except VoiceError as exc:
            say("  %s. The plain titles are kept." % exc)
            break
        if acceptable(line, quest, risk_in):
            quest["title"] = line
            changed += 1
        elif line:
            say("  kept the plain title for %s (Gemini's line did not pass the checks)" % quest["id"])
        try:
            tidbits = gary_tidbits(quest, quest.get("_about"), key, risk_in, model, opener)
        except VoiceError as exc:
            say("  %s. No more tidbits." % exc)
            break
        if tidbits:
            quest["tidbits"] = tidbits
    return changed
