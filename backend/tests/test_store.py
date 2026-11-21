"""The two stores (#16), the settings, and the contract's example files."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

import app as backend
import rules
import store as stores
from conftest import BACKEND, PINNED_NOW, SEED, TEST_DATABASE_URL, post, quest, sniff, state_of

needs_postgres = pytest.mark.skipif(not TEST_DATABASE_URL, reason="set TEST_DATABASE_URL to a throwaway database")


def test_memory_is_the_default_and_says_so(client):
    if backend.store.kind != "memory":
        pytest.skip("this run is on Postgres")
    health = client.get("/api/health").json()
    assert health["ok"] is True and health["store"] == "memory"
    assert health["events"] == 0 and health["quests"] == 3 and health["last_event"] is None
    post(client, sniff("dog"))
    assert client.get("/api/health").json()["last_event"] == "2026-11-21T05:20:00Z"
    assert stores.make_store(SEED).kind == "memory", "no DATABASE_URL, no database"


def test_a_replaced_quest_keeps_its_place_in_the_order(client):
    client.post("/api/quests", json={"quests": [quest("q-demo-bottle", "cup", "Somewhere else", source="manual")]})
    quests = client.get("/api/quests").json()["quests"]
    assert [q["id"] for q in quests] == ["q-demo-bottle", "q-demo-backpack", "q-harris-bench"]
    assert quests[0]["target"] == "cup" and quests[0]["place"] == "Somewhere else"


def test_reset_can_be_locked_with_a_key(client, monkeypatch):
    post(client, sniff("dog"))
    monkeypatch.setenv("GARY_ADMIN_KEY", "open-sesame")
    assert client.post("/api/dev/reset").status_code == 401
    assert client.post("/api/dev/reset", headers={"X-Admin-Key": "wrong"}).status_code == 401
    assert state_of(client)["gary"]["xp"] == rules.XP_NEW_OUTDOOR, "nothing was reset"
    assert client.post("/api/dev/reset", headers={"X-Admin-Key": "open-sesame"}).status_code == 200
    assert state_of(client)["gary"]["xp"] == 0 and state_of(client)["quests_open"] == 3


def test_dotenv_file_is_read_without_overriding_the_shell(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# a comment\nGARY_TEST_A=from-file\nGARY_TEST_B="quoted value"\n\nnot a setting\nGARY_TEST_C=x=y\n')
    monkeypatch.setenv("GARY_TEST_A", "from-shell")
    monkeypatch.delenv("GARY_TEST_B", raising=False)
    monkeypatch.delenv("GARY_TEST_C", raising=False)
    backend.load_env(env)
    assert os.environ["GARY_TEST_A"] == "from-shell"
    assert os.environ["GARY_TEST_B"] == "quoted value" and os.environ["GARY_TEST_C"] == "x=y"
    backend.load_env(tmp_path / "missing.env")       # no file is fine
    monkeypatch.delenv("GARY_TEST_B")
    monkeypatch.delenv("GARY_TEST_C")


def test_the_tests_never_read_a_developers_own_settings_file(tmp_path):
    """backend/.env holds the real database's address. A test backend that read
    it would write test sniffs into the real Gary."""
    assert os.environ.get("GARY_NO_ENV_FILE"), "conftest.py sets this before the backend is imported"
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=postgres://the-real-one\nGARY_NAP_SECONDS=60\n")
    settings = {"GARY_NO_ENV_FILE": "1"}
    assert backend.load_settings([env], settings) is False and settings == {"GARY_NO_ENV_FILE": "1"}
    settings = {}
    assert backend.load_settings([env, tmp_path / "missing.env"], settings) is True
    assert settings == {"DATABASE_URL": "postgres://the-real-one", "GARY_NAP_SECONDS": "60"}
    # and the two scripts that start a throwaway backend say the same
    for script in ("e2e.py", "make_examples.py"):
        text = (BACKEND.parent / "scripts" / script).read_text(encoding="utf-8")
        assert "GARY_NO_ENV_FILE" in text and 'DATABASE_URL"] = ""' in text, script


def test_the_contract_examples_are_what_the_backend_returns():
    """state.json, wellness.json and story.json are written by scripts/make_examples.py.
    If this fails, run that script and commit the result."""
    out = subprocess.run([sys.executable, str(BACKEND.parent / "scripts" / "make_examples.py"), "--check"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def test_no_file_here_hides_a_python_module():
    """A file named after one of Python's own modules (json.py, queue.py ...)
    would replace it for everything started from this folder."""
    for path in sorted(BACKEND.glob("*.py")):
        assert path.stem not in getattr(sys, "stdlib_module_names", ()), path.name


# --- Postgres (Tiger Data) ------------------------------------------------------
def play_a_day(client):
    client.post("/api/quests", json={"quests": [quest("q-gibbons", "dog", "Gibbons Park", herd=True)]})
    client.post("/api/mood", json={"phase": "before", "value": 2})
    client.post("/api/quest/choose", json={"time": "long"})
    post(client, sniff("bench", ts="2026-11-21T05:00:00Z"), sniff("dog", friend=True, ts="2026-11-21T05:10:00Z"),
         {"id": "miss-1", "ts": "2026-11-21T05:11:00Z", "type": "miss", "friend": False},
         {"id": "m-dev", "ts": "2026-11-21T05:12:00Z", "type": "mood", "phase": "after", "value": 4},
         sniff("kite", ts="2026-11-21T03:30:00Z"))


@needs_postgres
def test_a_restart_keeps_garys_state(client):
    if backend.store.kind != "postgres":
        pytest.skip("the memory run")
    play_a_day(client)
    before_state = state_of(client)
    before_wellness = client.get("/api/wellness").json()
    before_quests = client.get("/api/quests?all=true").json()
    assert before_state["gary"]["xp"] > 0 and before_state["quest_choice"] == "long"

    # "Restart": a brand-new store on the same database, as a new process would make.
    again = stores.PostgresStore(TEST_DATABASE_URL, SEED)
    try:
        state, _, _ = rules.compute(again.events(), again.quests(), backend.OUTDOOR, PINNED_NOW,
                                    rules.NAP_SECONDS, backend.TZ)
        assert state == before_state
        assert rules.wellness(again.moods(), again.events(), backend.OUTDOOR, backend.TZ,
                              again.outdoor_by_day(backend.OUTDOOR_LABELS, backend.TZ_NAME)) == before_wellness
        assert [q["id"] for q in again.quests()] == [q["id"] for q in before_quests["quests"]] or \
            sorted(q["id"] for q in again.quests()) == sorted(q["id"] for q in before_quests["quests"])
        assert len(again.quests()) == 4, "the seed quests are not added a second time"
        # the same upload after a restart still counts once
        assert again.add([dict(sniff("bench"), id="test-replay")]) != []
        assert again.add([dict(sniff("bench"), id="test-replay")]) == []
    finally:
        again.close()


@needs_postgres
def test_the_outdoor_query_matches_the_python_sum(client, clock):
    if backend.store.kind != "postgres":
        pytest.skip("the memory run")
    clock.set("2026-11-23T00:00:00Z")
    post(client,
         sniff("bench", ts="2026-11-21T15:01:00Z"), sniff("dog", ts="2026-11-21T15:08:00Z"),
         sniff("bird", ts="2026-11-21T15:12:00Z"), sniff("cup", ts="2026-11-21T15:25:00Z"),
         sniff("kite", ts="2026-11-22T03:30:00Z"),      # 10:30 pm Saturday local: still Saturday
         sniff("kite", ts="2026-11-22T04:59:59Z"),      # one second before local midnight
         sniff("kite", ts="2026-11-22T05:00:00Z"),      # local midnight: Sunday
         sniff("bicycle", ts="2026-03-08T06:30:00Z"),   # the night the clocks go forward
         sniff("bicycle", ts="2026-03-08T07:30:00Z"))
    from_query = backend.store.outdoor_by_day(backend.OUTDOOR_LABELS, backend.TZ_NAME)
    from_python = rules.outdoor_by_day(backend.store.events(), backend.OUTDOOR, backend.TZ)
    assert from_query == from_python
    assert {d["day"]: d["minutes"] for d in from_query} == {
        "2026-03-08": 20, "2026-11-21": 40, "2026-11-22": 10}
    assert client.get("/api/wellness").json()["outdoor"] == from_query
    # the plain form (no TimescaleDB) is the one this database can run; say which is in use
    info = backend.store.info()
    assert info["store"] == "postgres" and info["outdoor_query"] in ("time_bucket", "plain")
    assert client.get("/api/health").json()["store"] == "postgres"


@needs_postgres
def test_postgres_keeps_arrival_order_and_private_moods_apart(client):
    if backend.store.kind != "postgres":
        pytest.skip("the memory run")
    play_a_day(client)
    kinds = [e["type"] for e in backend.store.events()]
    assert kinds == ["choice", "discovery", "discovery", "miss", "discovery"], "arrival order, and no mood rows"
    with backend.store.conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM mood_checkins")
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT count(*) FROM events WHERE type = 'mood' OR body::text ILIKE '%phase%'")
        assert cur.fetchone()[0] == 0, "mood never reaches the events table"
        cur.execute("SELECT count(*) FROM event_ids")
        assert cur.fetchone()[0] == 7


@needs_postgres
def test_a_dropped_connection_is_reopened(client):
    if backend.store.kind != "postgres":
        pytest.skip("the memory run")
    post(client, sniff("dog"))
    backend.store.conn.close()             # as Tiger Data does to an idle connection
    assert state_of(client)["gary"]["xp"] == rules.XP_NEW_OUTDOOR
    backend.store.conn.close()
    assert post(client, sniff("cup"))["accepted"] == 1
