"""Auth0 for Gary: who is asking, proved by a token.

Three kinds of caller get a token from the team's Auth0 tenant, each by the
flow made for it:

  the web page   a person signs in (Universal Login)
  Gary himself   Device Authorization Flow: no keyboard, so a code on a phone
  the scout      a machine-to-machine token that carries "write:quests"

This file only checks tokens: RS256, signed by the tenant's keys, issued by
the tenant, meant for Gary's API. It is switched on by two settings:

  AUTH0_DOMAIN     the tenant, for example gary.ca.auth0.com
  AUTH0_AUDIENCE   the API's identifier, for example https://gary.api

Without them nothing here does anything, and the shared keys work as before.

Gary keeps no names and no e-mail addresses. A person is a fingerprint: the
first 16 hex digits of the SHA-256 of their Auth0 id. That is enough to keep
one person's check-ins apart from another's, and it is all that is stored.
"""
import hashlib
import json
import os
import threading
import time
import urllib.request

KEYS_TTL = 600          # seconds a fetched key set is trusted
REFETCH_GAP = 30        # at most one extra fetch per this many seconds for an unknown key id
_lock = threading.Lock()
_cache = {"at": 0.0, "keys": None}


class AuthError(Exception):
    """A token was sent and it is not acceptable. The text is safe to show."""


def domain():
    return (os.environ.get("AUTH0_DOMAIN") or "").strip().removeprefix("https://").strip("/")


def audience():
    return (os.environ.get("AUTH0_AUDIENCE") or "").strip()


def enabled():
    return bool(domain() and audience())


def public_config():
    """What the page and the device need to start a login. None of it is secret."""
    return {"enabled": enabled(), "domain": domain() or None, "audience": audience() or None,
            "client_id": (os.environ.get("AUTH0_CLIENT_ID") or "").strip() or None,
            "device_client_id": (os.environ.get("AUTH0_DEVICE_CLIENT_ID") or "").strip() or None}


def fetch_keys():
    """The tenant's public signing keys. Tests replace this function."""
    with urllib.request.urlopen("https://%s/.well-known/jwks.json" % domain(), timeout=8) as reply:
        return json.load(reply)["keys"]


def signing_key(kid):
    import jwt
    now = time.time()
    with _lock:
        stale = _cache["keys"] is None or now - _cache["at"] > KEYS_TTL
        unknown = not stale and not any(k.get("kid") == kid for k in _cache["keys"])
        if stale or (unknown and now - _cache["at"] > REFETCH_GAP):
            _cache["keys"], _cache["at"] = fetch_keys(), now
        for key in _cache["keys"]:
            if key.get("kid") == kid:
                return jwt.PyJWK.from_dict(key).key
    raise AuthError("this token was signed with a key the tenant does not have")


def forget_keys():
    with _lock:
        _cache["keys"], _cache["at"] = None, 0.0


def fingerprint(sub):
    return hashlib.sha256(str(sub).encode("utf-8")).hexdigest()[:16]


def identify(authorization):
    """The Authorization header -> who sent it, or None when there is no token
    or Auth0 is off. A token that is sent and is wrong raises AuthError: a bad
    token is never treated as no token."""
    if not enabled() or not authorization:
        return None
    kind, _, token = str(authorization).partition(" ")
    if kind.lower() != "bearer" or not token.strip():
        return None
    import jwt
    try:
        header = jwt.get_unverified_header(token.strip())
        if header.get("alg") != "RS256":
            raise AuthError("this token is not signed the way the tenant signs")
        claims = jwt.decode(token.strip(), signing_key(header.get("kid")), algorithms=["RS256"],
                            audience=audience(), issuer="https://%s/" % domain(),
                            options={"require": ["exp", "iat", "sub"]}, leeway=30)
    except AuthError:
        raise
    except jwt.ExpiredSignatureError:
        raise AuthError("this token has run out: sign in again")
    except jwt.InvalidAudienceError:
        raise AuthError("this token is for another API")
    except jwt.InvalidIssuerError:
        raise AuthError("this token is from another tenant")
    except Exception:  # a broken token, a key that cannot be fetched
        raise AuthError("this token could not be checked")
    sub = str(claims["sub"])
    granted = set(claims.get("permissions") or []) | set(str(claims.get("scope") or "").split())
    return {"fingerprint": fingerprint(sub), "permissions": sorted(granted),
            "machine": sub.endswith("@clients") or claims.get("gty") == "client-credentials"}


def allows(who, permission):
    return bool(who) and permission in who["permissions"]
