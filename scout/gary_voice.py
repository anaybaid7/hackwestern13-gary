#!/usr/bin/env python3
"""gary_voice.py - stretch (issue #37): Gemini puts a quest title in Gary's voice.

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

Not run against the real Gemini API yet: there was no key. The request shape
is the one in Google's REST quickstart.
"""
import json
import os
import re
import urllib.error
import urllib.request

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
DEFAULT_MODEL = "gemini-flash-latest"
MAX_LENGTH = 90

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
    if quest.get("herd") and "friend" not in lowered:
        return False  # a co-op quest must still say it needs a friend
    if risk_in(line) or not line.isprintable():
        return False
    if re.search(r"https?:|www\.|[<>{}\[\]]", lowered):
        return False  # a title is words, never a link or markup
    return not re.search(r"hurry|quick|fast|race|beat|lazy|should|must|guilt|fence|private", lowered)


class VoiceError(Exception):
    """Gemini could not be asked at all: the key, the model name or the network."""


def gary_title(quest, key, model=None, opener=urllib.request.urlopen):
    """Ask Gemini for one line. Returns the text, or None when the reply holds
    no usable line. Raises VoiceError when Gemini cannot be asked at all."""
    prompt = PROMPT.format(place=quest["place"], target=quest["target"], title=quest["title"],
                           herd='- It needs a friend: keep the word "friend".' if quest.get("herd") else "")
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    name = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
    req = urllib.request.Request(GEMINI_URL % name, data=body,
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with opener(req, timeout=20) as reply:
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
    return str(text).strip().strip('"').strip("'").strip() or None


def apply(quests, key, say=print, model=None, opener=urllib.request.urlopen):
    """Reword the titles in place where Gemini gives a line that passes the checks.
    Returns how many titles changed."""
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
    return changed
