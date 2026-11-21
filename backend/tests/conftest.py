import datetime as dt
import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import app as backend  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

EXAMPLES = BACKEND.parent / "contract" / "examples"
# Two minutes after the example discovery, so Gary is awake.
PINNED_NOW = dt.datetime(2026, 11, 21, 5, 22, 0, tzinfo=dt.timezone.utc)


def example(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(backend, "now", lambda: PINNED_NOW)
    monkeypatch.delenv("SCOUT_KEY", raising=False)
    monkeypatch.delenv("GARY_NAP_SECONDS", raising=False)
    backend.store.reset()
    return TestClient(backend.app)


_counter = [0]


def sniff(label, friend=False, quest_id=None, ts="2026-11-21T05:20:00Z"):
    """A discovery event the way the device writes it."""
    _counter[0] += 1
    return {"id": "test-%d" % _counter[0], "ts": ts, "type": "discovery", "device": "test",
            "label": label, "score": 0.9, "friend": friend, "new": True, "quest_id": quest_id,
            "latency_ms": 40.0}
