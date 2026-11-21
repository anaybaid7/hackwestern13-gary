#!/usr/bin/env python3
"""Pair this Gary with a person. Gary has no keyboard, so he uses Auth0's
Device Authorization Flow: he shows a short code, you approve it on your
phone, and from then on his sniffs arrive signed as yours.

    python3 pair.py                     pair, using GARY_API to find the tenant
    python3 pair.py --api http://host   the same, with the backend named
    python3 pair.py --status            say whether this Gary is paired
    python3 pair.py --forget            unpair: delete the token

The token is kept in gary.token beside the journal. Git ignores it. Pairing
is optional: a Gary with no token works exactly as before.

Standard library only, like sync.py. It needs https to reach Auth0; if the
Pi's Python has none, run this on a laptop and copy gary.token to the Pi.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(HERE, "gary.token")
TIMEOUT = 8
EARLY = 120   # refresh this many seconds before the token runs out


def get_json(url):
    with urllib.request.urlopen(url, timeout=TIMEOUT) as reply:
        return json.loads(reply.read().decode("utf-8"))


def post_form(url, fields):
    """One form POST to Auth0 -> (status, decoded reply). Auth0 answers a
    pending approval with 4xx and a JSON body, so that is not an exception."""
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as reply:
            return reply.status, json.loads(reply.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read().decode("utf-8"))
        except ValueError:
            return err.code, {"error": "http_%d" % err.code}


def load(path=TOKEN_FILE):
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        return saved if isinstance(saved, dict) and saved.get("access_token") else None
    except (OSError, ValueError):
        return None


def save(saved, path=TOKEN_FILE):
    tmp = path + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
        json.dump(saved, f)
    os.replace(tmp, path)


def keep(reply, config, old=None):
    """Auth0's token reply -> what gary.token holds."""
    return {"access_token": reply["access_token"],
            "refresh_token": reply.get("refresh_token") or (old or {}).get("refresh_token"),
            "expires_at": int(time.time()) + int(reply.get("expires_in", 3600)),
            "domain": config["domain"], "client_id": config["client_id"]}


def current_token(path=TOKEN_FILE, post=post_form, now=time.time):
    """The token to send with an upload, or None. Never raises and never
    returns a token that has run out: an upload without a token is accepted,
    one with a stale token is not. Refreshes quietly when it can."""
    saved = load(path)
    if not saved:
        return None
    if now() < saved.get("expires_at", 0) - EARLY:
        return saved["access_token"]
    if not saved.get("refresh_token"):
        return None
    try:
        status, reply = post("https://%s/oauth/token" % saved["domain"],
                             {"grant_type": "refresh_token", "client_id": saved["client_id"],
                              "refresh_token": saved["refresh_token"]})
        if status != 200 or not reply.get("access_token"):
            return None
        fresh = keep(reply, saved, saved)
        save(fresh, path)
        return fresh["access_token"]
    except (OSError, ValueError, KeyError):
        return None


def pair(config, say=print, post=post_form, sleep=time.sleep, path=TOKEN_FILE):
    """Run the device flow. -> True when Gary is paired."""
    domain, client_id = config["domain"], config["client_id"]
    status, start = post("https://%s/oauth/device/code" % domain,
                         {"client_id": client_id, "audience": config["audience"], "scope": "offline_access"})
    if status != 200:
        say("Auth0 would not start the pairing: %s" % (start.get("error_description") or start.get("error")))
        return False
    say("")
    say("  Gary wants to be your goat.")
    say("  On your phone, open:  %s" % start["verification_uri"])
    say("  and enter the code:   %s" % start["user_code"])
    say("  (or open %s)" % start.get("verification_uri_complete", start["verification_uri"]))
    say("")
    wait, deadline = int(start.get("interval", 5)), time.time() + int(start.get("expires_in", 900))
    while time.time() < deadline:
        sleep(wait)
        status, reply = post("https://%s/oauth/token" % domain,
                             {"grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                              "device_code": start["device_code"], "client_id": client_id})
        if status == 200 and reply.get("access_token"):
            save(keep(reply, config), path)
            say("  Paired. Gary's sniffs are now signed as yours.")
            return True
        error = reply.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            wait += 5
            continue
        say("  Not paired: %s" % (reply.get("error_description") or error))
        return False
    say("  Not paired: the code ran out. Run pair.py again.")
    return False


def main():
    ap = argparse.ArgumentParser(description="Pair this Gary with a person (Auth0 device flow).")
    ap.add_argument("--api", default=os.environ.get("GARY_API", "http://localhost:8000"))
    ap.add_argument("--token", default=TOKEN_FILE, help="where the token is kept")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--forget", action="store_true")
    args = ap.parse_args()
    if args.forget:
        if os.path.exists(args.token):
            os.remove(args.token)
        print("This Gary is not paired with anyone now.")
        return 0
    if args.status:
        saved = load(args.token)
        if not saved:
            print("Not paired.")
        else:
            left = saved.get("expires_at", 0) - time.time()
            print("Paired. The token %s." % ("is good for %d more minutes" % (left // 60) if left > 0 else
                                             "has run out" + (" and will be renewed" if saved.get("refresh_token") else "")))
        return 0
    try:
        config = get_json(args.api.rstrip("/") + "/api/auth/config")
    except (OSError, ValueError) as err:
        print("Cannot reach the backend at %s: %s" % (args.api, err))
        return 1
    if not config.get("enabled") or not config.get("device_client_id"):
        print("This backend has no Auth0 tenant set up, so there is nothing to pair with.")
        return 1
    try:
        ok = pair({"domain": config["domain"], "audience": config["audience"],
                   "client_id": config["device_client_id"]}, path=args.token)
    except OSError as err:
        print("Cannot reach Auth0: %s" % err)
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
