"""The scout, run by the backend: one run at a time, daily at a set time."""
import datetime as dt
import threading

import scouting


def test_only_one_run_at_a_time():
    gate = threading.Event()
    assert scouting.start("asked", runner=lambda: gate.wait(5) and 0)
    assert scouting.start("asked", runner=lambda: 0) is False
    gate.set()
    for _ in range(100):
        if not scouting.status["running"]:
            break
        threading.Event().wait(0.02)
    assert scouting.status["ok"] is True
    assert scouting.start("asked", runner=lambda: 1, wait=True) and scouting.status["ok"] is False


def test_a_crash_is_a_failed_run_not_a_dead_backend():
    def boom():
        raise RuntimeError("TinyFish fell over")
    scouting.start("asked", runner=boom, wait=True)
    assert scouting.status == dict(scouting.status, running=False, ok=False)


def test_the_daily_run_is_due_once_after_its_time():
    day = dt.date(2026, 11, 22)
    assert not scouting.due("07:00", dt.datetime(2026, 11, 22, 6, 59), None)
    assert scouting.due("07:00", dt.datetime(2026, 11, 22, 7, 0), None)
    assert not scouting.due("07:00", dt.datetime(2026, 11, 22, 9, 0), day)
    assert not scouting.due("7am", dt.datetime(2026, 11, 22, 9, 0), None)


def test_the_page_can_send_the_scout_out(client, monkeypatch):
    ran = []
    gate = threading.Event()
    monkeypatch.setattr(scouting, "default_runner", lambda: ran.append(1) or gate.wait(5) and 0)
    assert client.get("/api/scout").json()["available"] is True
    first = client.post("/api/scout/run").json()
    assert first["sent"] is True and first["running"] is True
    assert client.post("/api/scout/run").json()["sent"] is False, "one run at a time"
    gate.set()
