"""Shared pieces for the backend tests.

Every API test runs against the in-memory store. Set TEST_DATABASE_URL to an
empty, throwaway Postgres database and the same tests run against
PostgresStore too:

    TEST_DATABASE_URL=postgresql://user@localhost:5432/gary_test pytest

That database is wiped by every test. Never point it at the real one.
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
# The tests must not pick up a developer's real settings (a .env file, or
# variables in the shell): start from a known, empty configuration.
os.environ["DATABASE_URL"] = ""
os.environ["GARY_TZ"] = "America/Toronto"
for _name in ("SCOUT_KEY", "GARY_ADMIN_KEY"):
    os.environ[_name] = ""
os.environ.pop("GARY_NAP_SECONDS", None)
os.environ.pop("GARY_SEED", None)

import app as backend  # noqa: E402
import store as stores  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

EXAMPLES = BACKEND.parent / "contract" / "examples"
# Two minutes after the example discovery, so Gary is awake.
PINNED_NOW = dt.datetime(2026, 11, 21, 5, 22, 0, tzinfo=dt.timezone.utc)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
SEED = EXAMPLES / "quests.json"


def example(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


_postgres = []


def postgres_store():
    """One PostgresStore for the whole test run."""
    if not _postgres:
        _postgres.append(stores.PostgresStore(TEST_DATABASE_URL, SEED))
    return _postgres[0]


@pytest.fixture(params=["memory"] + (["postgres"] if TEST_DATABASE_URL else []))
def client(request, monkeypatch):
    monkeypatch.setattr(backend, "now", lambda: PINNED_NOW)
    for name in ("SCOUT_KEY", "GARY_NAP_SECONDS", "GARY_ADMIN_KEY"):
        monkeypatch.delenv(name, raising=False)
    if request.param == "postgres":
        monkeypatch.setattr(backend, "store", postgres_store())
    backend.store.reset()
    return TestClient(backend.app)


class Clock:
    """A clock the test moves by hand."""

    def __init__(self, monkeypatch, start=PINNED_NOW):
        self.now = start
        monkeypatch.setattr(backend, "now", lambda: self.now)

    def set(self, text):
        self.now = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))

    def forward(self, **kwargs):
        self.now = self.now + dt.timedelta(**kwargs)


@pytest.fixture
def clock(client, monkeypatch):
    return Clock(monkeypatch)


_counter = [0]


def sniff(label, friend=False, quest_id=None, ts="2026-11-21T05:20:00Z"):
    """A discovery event the way the device writes it."""
    _counter[0] += 1
    return {"id": "test-%d" % _counter[0], "ts": ts, "type": "discovery", "device": "test",
            "label": label, "score": 0.9, "friend": friend, "new": True, "quest_id": quest_id,
            "latency_ms": 40.0}


def quest(quest_id, target, place, time="short", herd=False, source="tinyfish", day="2026-11-21", **more):
    q = {"id": quest_id, "title": "Find a %s at %s" % (target, place), "place": place, "time": time,
         "minutes": 15 if time == "short" else 40, "target": target, "xp": 20 if time == "short" else 40,
         "herd": herd, "source": source, "source_url": "https://london.ca/parks-london", "day": day}
    q.update(more)
    return q


def post(client, *events, **extra):
    return client.post("/api/events", json=dict({"events": list(events)}, **extra)).json()


def state_of(client):
    return client.get("/api/state").json()
