"""Auth0 tokens: who may do what. Run with: python3 -m pytest backend/tests

The tests sign their own tokens with a key made here, and hand the backend
the matching public key in place of the tenant's. No network is used.
"""
import datetime as dt
import json

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import auth
from conftest import post, quest, sniff, state_of

DOMAIN = "gary-test.ca.auth0.com"
AUDIENCE = "https://gary.api"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)   # somebody else's key


def jwk(key, kid):
    return dict(json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())), kid=kid, use="sig", alg="RS256")


def token(sub="auth0|moe", key=KEY, kid="k1", minutes=10, **claims):
    now = dt.datetime.now(dt.timezone.utc)
    body = {"iss": "https://%s/" % DOMAIN, "aud": AUDIENCE, "sub": sub, "iat": now,
            "exp": now + dt.timedelta(minutes=minutes)}
    body.update(claims)
    return jwt.encode(body, key, algorithm="RS256", headers={"kid": kid})


def bearer(*args, **kwargs):
    return {"Authorization": "Bearer " + token(*args, **kwargs)}


@pytest.fixture
def auth0(client, monkeypatch):
    """The client, with Auth0 switched on and no shared keys."""
    monkeypatch.setenv("AUTH0_DOMAIN", DOMAIN)
    monkeypatch.setenv("AUTH0_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("AUTH0_CLIENT_ID", "page-client")
    monkeypatch.setenv("AUTH0_DEVICE_CLIENT_ID", "device-client")
    monkeypatch.delenv("GARY_PRIVATE_KEY", raising=False)
    monkeypatch.setattr(auth, "fetch_keys", lambda: [jwk(KEY, "k1")])
    auth.forget_keys()
    yield client
    auth.forget_keys()


def test_without_auth0_settings_nothing_changes(client, monkeypatch):
    for name in ("AUTH0_DOMAIN", "AUTH0_AUDIENCE", "GARY_PRIVATE_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert client.get("/api/health").json()["auth0"] is False
    assert client.get("/api/auth/config").json()["enabled"] is False
    # a token is ignored, not checked: the laptop setup needs no tenant
    assert client.get("/api/wellness", headers={"Authorization": "Bearer nonsense"}).status_code == 200
    assert client.get("/api/me", headers={"Authorization": "Bearer nonsense"}).json() == {"signed_in": False}
    assert client.post("/api/quests", json={"quests": [quest("q-open", "duck", "Sifton Bog")]}).json()["accepted"]


def test_the_page_and_the_device_can_ask_how_to_sign_in(auth0):
    assert auth0.get("/api/auth/config").json() == {
        "enabled": True, "domain": DOMAIN, "audience": AUDIENCE,
        "client_id": "page-client", "device_client_id": "device-client"}
    assert auth0.get("/api/health").json()["auth0"] is True


def test_signed_in_your_check_ins_are_yours_alone(auth0):
    moe, ash = bearer("auth0|moe"), bearer("google-oauth2|ash")
    # with Auth0 on, the private side is locked for anyone who is not signed in
    assert auth0.get("/api/wellness").status_code == 401
    assert auth0.post("/api/mood", json={"phase": "before", "value": 2}).status_code == 401

    assert auth0.post("/api/mood", json={"phase": "before", "value": 2}, headers=moe).json() == {"ok": True}
    assert auth0.post("/api/mood", json={"phase": "after", "value": 4}, headers=moe).json() == {"ok": True}
    assert auth0.post("/api/mood", json={"phase": "before", "value": 5}, headers=ash).json() == {"ok": True}

    mine = auth0.get("/api/wellness", headers=moe).json()
    assert sorted(c["value"] for c in mine["checkins"]) == [2, 4] and mine["signed_in"] is True and mine["locked"] is True
    hers = auth0.get("/api/wellness", headers=ash).json()
    assert [c["value"] for c in hers["checkins"]] == [5]
    # no name, no id and no fingerprint comes back with a check-in, and none is in Gary's shared state
    assert "owner" not in json.dumps(mine) and "moe" not in json.dumps(mine)
    assert "owner" not in json.dumps(state_of(auth0))


def test_the_passphrase_still_opens_the_check_ins_nobody_signed(auth0, monkeypatch):
    monkeypatch.setenv("GARY_PRIVATE_KEY", "maple-ridge-otter")
    key = {"X-Private-Key": "maple-ridge-otter"}
    auth0.post("/api/mood", json={"phase": "before", "value": 3}, headers=key)
    auth0.post("/api/mood", json={"phase": "before", "value": 1}, headers=bearer("auth0|moe"))
    shared = auth0.get("/api/wellness", headers=key).json()
    assert [c["value"] for c in shared["checkins"]] == [3] and shared["signed_in"] is False
    assert auth0.get("/api/wellness", headers={"X-Private-Key": "wrong"}).status_code == 401


@pytest.mark.parametrize("bad, why", [
    (lambda: token(minutes=-5), "run out"),
    (lambda: token(aud="https://another.api"), "another API"),
    (lambda: token(iss="https://evil.example/"), "another tenant"),
    (lambda: token(key=OTHER), "could not be checked"),           # right key id, wrong key
    (lambda: token(key=OTHER, kid="k9"), "does not have"),         # a key the tenant never had
    (lambda: jwt.encode({"sub": "auth0|moe", "aud": AUDIENCE}, "secret", algorithm="HS256"), "not signed the way"),
    (lambda: "not.a.token", "could not be checked"),
])
def test_a_token_that_is_sent_and_is_wrong_is_refused_everywhere(auth0, bad, why):
    headers = {"Authorization": "Bearer " + bad()}
    for call in (lambda: auth0.get("/api/wellness", headers=headers),
                 lambda: auth0.get("/api/me", headers=headers),
                 lambda: auth0.post("/api/events", json={"events": [sniff("duck")]}, headers=headers),
                 lambda: auth0.post("/api/quests", json={"quests": []}, headers=headers),
                 lambda: auth0.post("/api/dev/reset", headers=headers)):
        reply = call()
        assert reply.status_code == 401 and why in reply.json()["detail"], reply.text
    assert auth0.get("/api/health").json()["events"] == 0   # the sniff sent with a bad token was not kept


def test_the_scout_writes_quests_with_a_machine_token_that_has_the_permission(auth0):
    body = {"quests": [quest("q-m2m", "duck", "Sifton Bog")]}
    assert auth0.post("/api/quests", json=body).status_code == 401                         # nobody
    assert auth0.post("/api/quests", json=body, headers=bearer("auth0|moe")).status_code == 401   # a person
    wrong = bearer("scout@clients", gty="client-credentials", permissions=["reset:gary"])
    assert auth0.post("/api/quests", json=body, headers=wrong).status_code == 401
    scout = bearer("scout@clients", gty="client-credentials", permissions=["write:quests"])
    assert auth0.post("/api/quests", json=body, headers=scout).json()["accepted"] == ["q-m2m"]
    by_scope = bearer("scout@clients", gty="client-credentials", scope="write:quests")
    assert auth0.post("/api/quests", json=body, headers=by_scope).json()["accepted"] == ["q-m2m"]
    # a machine is not a person: it cannot read or write anyone's check-ins
    assert auth0.get("/api/wellness", headers=scout).status_code == 401
    assert auth0.post("/api/mood", json={"phase": "before", "value": 3}, headers=scout).status_code == 401


def test_the_reset_needs_its_permission(auth0):
    post(auth0, sniff("bottle"), there=False)
    assert auth0.post("/api/dev/reset").status_code == 401
    assert auth0.post("/api/dev/reset", headers=bearer("auth0|moe")).status_code == 401
    assert auth0.get("/api/health").json()["events"] == 1
    admin = bearer("auth0|moe", permissions=["reset:gary"])
    assert auth0.post("/api/dev/reset", json={"keep_quests": True}, headers=admin).json()["ok"] is True
    assert auth0.get("/api/health").json()["events"] == 0


def test_a_paired_gary_signs_his_sniffs_and_an_unpaired_one_still_works(auth0):
    moe = bearer("auth0|moe")
    assert auth0.get("/api/me", headers=moe).json()["paired"] is False
    assert auth0.get("/api/me").json() == {"signed_in": False}

    plain = post(auth0, sniff("bottle"))                    # no token: accepted as before
    assert plain["accepted"] == 1
    assert auth0.get("/api/me", headers=moe).json()["paired"] is False

    forged = dict(sniff("duck"), owner="someone-else")      # a device cannot claim an owner by itself
    assert auth0.post("/api/events", json={"events": [forged]}).json()["accepted"] == 1
    signed = auth0.post("/api/events", json={"events": [sniff("squirrel")]}, headers=moe).json()
    assert signed["accepted"] == 1

    me = auth0.get("/api/me", headers=moe).json()
    assert me["signed_in"] is True and me["paired"] is True
    assert me["fingerprint"] == auth.fingerprint("auth0|moe") and len(me["fingerprint"]) == 16
    assert auth0.get("/api/me", headers=bearer("auth0|ash")).json()["paired"] is False
    shared = json.dumps(state_of(auth0))
    assert "owner" not in shared and me["fingerprint"] not in shared and "someone-else" not in shared
    assert state_of(auth0)["gary"]["xp"] > 0                # the sniffs count all the same


def test_the_tenants_keys_are_fetched_once_and_again_only_for_a_new_key(auth0, monkeypatch):
    calls = []

    def fetch():
        calls.append(1)
        return [jwk(KEY, "k1")] + ([jwk(OTHER, "k2")] if len(calls) > 1 else [])

    monkeypatch.setattr(auth, "fetch_keys", fetch)
    auth.forget_keys()
    for _ in range(3):
        assert auth0.get("/api/me", headers=bearer()).json()["signed_in"] is True
    assert len(calls) == 1
    # the tenant rotated its key: an unknown key id is looked up, but not on every request
    monkeypatch.setattr(auth, "REFETCH_GAP", 0)
    assert auth0.get("/api/me", headers=bearer(key=OTHER, kid="k2")).json()["signed_in"] is True
    assert len(calls) == 2
