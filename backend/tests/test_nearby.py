"""Explorers nearby: opt-in, coarse, unnamed, and forgotten quickly."""
import json

import pytest

import nearby
from conftest import post, sniff, state_of

GIBBONS = (42.9990, -81.2585)      # Gibbons Park
CLOSE = (43.0041, -81.2612)        # about 600 m north
FAR = (42.9420, -81.3150)          # Springbank way, about 7.8 km
A, B, C = "a" * 16, "b" * 16, "c" * 16


@pytest.fixture(autouse=True)
def empty_map():
    nearby.forget_all()
    yield
    nearby.forget_all()


def tell(client, device, at, quest=None):
    body = {"id": device, "lat": at[0], "lon": at[1]}
    if quest:
        body["quest_id"] = quest
    reply = client.post("/api/nearby", json=body)
    assert reply.status_code == 200, reply.text
    return reply.json()["nearby"]


def test_you_see_the_explorers_near_you_and_they_see_you(client):
    assert tell(client, A, GIBBONS) == []                    # alone
    seen = tell(client, B, CLOSE)
    assert len(seen) == 1 and 500 <= seen[0]["metres"] <= 700 and seen[0]["same_quest"] is False
    back = tell(client, A, GIBBONS)
    assert [o["tag"] for o in back] == [nearby.tag_of(B)]
    # someone across town is not nearby
    assert tell(client, C, FAR) == []
    assert len(tell(client, A, GIBBONS)) == 1


def test_someone_on_your_quest_shows_however_far_they_are(client):
    tell(client, A, GIBBONS, "q-duck")
    seen = tell(client, C, FAR, "q-duck")
    assert len(seen) == 1 and seen[0]["same_quest"] is True and seen[0]["metres"] > 5000
    assert tell(client, B, FAR, "q-other") != [] and tell(client, B, FAR, "q-other")[0]["same_quest"] is False


def test_nobody_is_named_and_nobody_is_pinpointed(client):
    tell(client, A, (42.99904321, -81.25853456))
    seen = tell(client, B, CLOSE)[0]
    assert set(seen) == {"tag", "lat", "lon", "same_quest", "metres", "seconds_ago"}
    assert (seen["lat"], seen["lon"]) == (42.999, -81.259)   # about 100 m, never the exact spot
    assert A not in json.dumps(seen) and len(seen["tag"]) == 8  # the id that moves a dot is never sent out


def test_a_dot_goes_when_you_switch_off_or_stop_refreshing(client):
    tell(client, A, GIBBONS)
    assert len(tell(client, B, CLOSE)) == 1
    assert client.post("/api/nearby/leave", json={"id": A}).json() == {"ok": True, "was_shown": True}
    assert tell(client, B, CLOSE) == []
    assert client.post("/api/nearby/leave", json={"id": A}).json()["was_shown"] is False
    # no refresh for longer than STALE: gone by itself
    nearby.share(A, *GIBBONS, now=1000.0)
    assert len(nearby.share(B, *CLOSE, now=1000.0 + nearby.STALE - 1)) == 1
    assert nearby.share(B, *CLOSE, now=1000.0 + nearby.STALE + 1) == []


def test_it_is_never_stored_and_never_in_garys_shared_state(client):
    post(client, sniff("duck"))
    before = client.get("/api/health").json()["events"]
    tell(client, A, GIBBONS)
    tell(client, B, CLOSE)
    assert client.get("/api/health").json()["events"] == before
    shared = json.dumps(state_of(client))
    assert nearby.tag_of(A) not in shared and "42.999" not in shared


@pytest.mark.parametrize("body", [
    {"id": "short", "lat": 43.0, "lon": -81.2},
    {"id": "a" * 16 + "!", "lat": 43.0, "lon": -81.2},
    {"id": A, "lat": "43.0", "lon": -81.2},
    {"id": A, "lat": 143.0, "lon": -81.2},
    {"id": A, "lat": True, "lon": -81.2},
    {"id": A},
])
def test_a_bad_request_puts_nobody_on_the_map(client, body):
    assert client.post("/api/nearby", json=body).status_code == 422
    assert tell(client, B, GIBBONS) == []


def test_a_showcase_server_can_show_people_in_one_room_apart_and_says_so(client, monkeypatch):
    here, beside = (43.009612, -81.273741), (43.009655, -81.273702)   # about 6 m apart
    # as shipped: both round to the same point, so two people in a room are one dot
    tell(client, A, here)
    usual = client.post("/api/nearby", json={"id": B, "lat": beside[0], "lon": beside[1]}).json()
    assert usual["rounded_m"] == 111.0 and usual["nearby"][0]["metres"] == 0
    assert (usual["nearby"][0]["lat"], usual["nearby"][0]["lon"]) == (43.01, -81.274)
    # GARY_NEARBY_ROUND=5: about a metre, and the reply says how coarse it is
    monkeypatch.setenv("GARY_NEARBY_ROUND", "5")
    tell(client, A, here)
    close = client.post("/api/nearby", json={"id": B, "lat": beside[0], "lon": beside[1]}).json()
    assert close["rounded_m"] == 1.1 and 4 <= close["nearby"][0]["metres"] <= 8
    assert (close["nearby"][0]["lat"], close["nearby"][0]["lon"]) == (43.00961, -81.27374)
    # a silly value falls back to the usual rounding
    monkeypatch.setenv("GARY_NEARBY_ROUND", "lots")
    assert client.post("/api/nearby", json={"id": B, "lat": beside[0], "lon": beside[1]}).json()["rounded_m"] == 111.0
