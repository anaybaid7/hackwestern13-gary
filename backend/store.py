"""Where the backend keeps things.

Two stores with the same methods, so app.py and rules.py never care which one
is in use:

    MemoryStore    Python lists. The default: no setup, and the fake that the
                   other pillars build against. A restart starts fresh.
    PostgresStore  Postgres on Tiger Data, used when DATABASE_URL is set.
                   A restart keeps Gary's state. Tables are in schema.sql.

An event here is already checked and tidied by app.py. Mood events go to their
own private place in both stores; events() never returns them.
"""
import datetime as dt
import functools
import json
import os
from pathlib import Path

import rules

HERE = Path(__file__).resolve().parent


def load_seed(path):
    """The quests a fresh backend starts with."""
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("quests", [])


def mood_row(event):
    return {"ts": event["ts"], "phase": event["phase"], "value": event["value"],
            "source": event.get("source", "device")}


class MemoryStore:
    kind = "memory"

    def __init__(self, seed_path):
        self.seed_path = seed_path
        self.reset()

    def reset(self, keep_quests=False):
        """Forget every event and mood, and go back to the seed quests.
        keep_quests: leave the quests as they are. With no events, all are open again."""
        self._events = []     # every event but mood, in arrival order
        self._ids = set()     # so the same upload twice counts once
        self._moods = []      # private. Never part of /api/state
        if keep_quests and getattr(self, "_quests", None):
            return
        self._quests = []     # oldest first
        for quest in load_seed(self.seed_path):
            self.put_quest(quest)

    def add(self, events):
        """Keep the events not seen before. Returns those, in order."""
        new = []
        for event in events:
            if event["id"] in self._ids:
                continue
            self._ids.add(event["id"])
            if event["type"] == "mood":
                self._moods.append(mood_row(event))
            else:
                self._events.append(event)
            new.append(event)
        return new

    def events(self):
        return list(self._events)

    def moods(self):
        return list(self._moods)

    def quests(self):
        return list(self._quests)

    def put_quest(self, quest):
        """Add a quest. A quest with a known id replaces the old one in place."""
        for i, old in enumerate(self._quests):
            if old["id"] == quest["id"]:
                self._quests[i] = quest
                return
        self._quests.append(quest)

    def outdoor_by_day(self, outdoor_labels, tz_name):
        return None  # no query to run: rules.outdoor_by_day() works it out

    def counts(self):
        last = self._events[-1]["ts"] if self._events else None
        return {"events": len(self._events), "quests": len(self._quests), "last_event": last}

    def info(self):
        return {"store": "memory"}

    def close(self):
        pass


def _retry(method):
    """Tiger Data closes idle connections. Reconnect once and try again."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except (self.pg.OperationalError, self.pg.InterfaceError):
            self._connect()
            return method(self, *args, **kwargs)

    return wrapper


class PostgresStore:
    kind = "postgres"

    # Estimated outdoor minutes per local day: each 10-minute block that holds
    # an outdoor find counts as 10 minutes. On Tiger Data this is one
    # time_bucket query over the events hypertable.
    OUTDOOR_TIME_BUCKET = """
        SELECT (time_bucket(INTERVAL '1 day', ts, %(tz)s::text) AT TIME ZONE %(tz)s::text)::date AS day,
               count(DISTINCT time_bucket(INTERVAL '10 minutes', ts)) * 10 AS minutes
        FROM events
        WHERE type = 'discovery' AND label = ANY(%(labels)s)
        GROUP BY 1
        ORDER BY 1
    """
    # The same sum on a Postgres without TimescaleDB (a laptop, the tests).
    OUTDOOR_PLAIN = """
        SELECT (ts AT TIME ZONE %(tz)s::text)::date AS day,
               count(DISTINCT floor(extract(epoch FROM ts) / 600)) * 10 AS minutes
        FROM events
        WHERE type = 'discovery' AND label = ANY(%(labels)s)
        GROUP BY 1
        ORDER BY 1
    """

    def __init__(self, url, seed_path):
        try:
            import psycopg
            from psycopg.types.json import Jsonb
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("DATABASE_URL is set, but the Postgres driver is missing. "
                               "Run: pip install -r requirements.txt") from exc
        self.pg, self.Jsonb = psycopg, Jsonb
        self.url, self.seed_path = url, seed_path
        self.conn = None
        self.timescaledb = self.hypertable = self.time_bucket = False
        self._connect()
        self._migrate()
        if not self.quests():
            for quest in load_seed(self.seed_path):
                self.put_quest(quest)

    # -- plumbing -----------------------------------------------------------
    def _connect(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
        # A connection the network drops without a word would otherwise make a
        # query wait forever, holding the lock every request needs. Keepalives
        # and tcp_user_timeout notice a dead link in about 15 s, statement_timeout
        # caps one query at 10 s; both raise OperationalError, so _retry reconnects.
        self.conn = self.pg.connect(
            self.url, autocommit=True, connect_timeout=10, keepalives=1, keepalives_idle=10,
            keepalives_interval=5, keepalives_count=3, tcp_user_timeout=15000,
            options="-c statement_timeout=10000")

    def _try(self, sql):
        """Run one statement that is allowed to fail. True if it worked."""
        try:
            with self.conn.transaction(), self.conn.cursor() as cur:
                cur.execute(sql)
            return True
        except self.pg.Error:
            return False

    def _exists(self, sql):
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
                return cur.fetchone() is not None
        except self.pg.Error:
            return False

    def _migrate(self):
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.execute((HERE / "schema.sql").read_text(encoding="utf-8"))
        # Tiger Data: make events a hypertable on ts. On a plain Postgres these
        # steps fail quietly and events stays an ordinary table.
        self._try("CREATE EXTENSION IF NOT EXISTS timescaledb")
        self.timescaledb = self._exists("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
        if self.timescaledb:
            if not self._try("SELECT create_hypertable('events', by_range('ts'), "
                             "if_not_exists => TRUE, migrate_data => TRUE)"):
                # TimescaleDB older than 2.13 has only this form
                self._try("SELECT create_hypertable('events', 'ts', if_not_exists => TRUE, migrate_data => TRUE)")
            self.hypertable = self._exists(
                "SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = 'events'")
            self.time_bucket = self._try("SELECT time_bucket(INTERVAL '1 day', now(), 'UTC'::text)")

    # -- the same methods as MemoryStore -------------------------------------
    @_retry
    def reset(self, keep_quests=False):
        if keep_quests and self.quests():
            with self.conn.transaction(), self.conn.cursor() as cur:
                cur.execute("TRUNCATE events, event_ids, mood_checkins RESTART IDENTITY")
            return
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.execute("TRUNCATE events, event_ids, mood_checkins, quests RESTART IDENTITY")
        for quest in load_seed(self.seed_path):
            self.put_quest(quest)

    @_retry
    def add(self, events):
        new = []
        with self.conn.transaction(), self.conn.cursor() as cur:
            for event in events:
                cur.execute("INSERT INTO event_ids (id) VALUES (%s) ON CONFLICT DO NOTHING", (event["id"],))
                if cur.rowcount == 0:
                    continue  # seen before
                when = rules.parse_ts(event["ts"])
                if event["type"] == "mood":
                    row = mood_row(event)
                    cur.execute("INSERT INTO mood_checkins (ts, phase, value, source) VALUES (%s, %s, %s, %s)",
                                (when, row["phase"], row["value"], row["source"]))
                else:
                    cur.execute(
                        "INSERT INTO events (ts, id, type, device, label, friend, body) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (when, event["id"], event["type"], event.get("device"), event.get("label"),
                         bool(event.get("friend")), self.Jsonb(event)))
                new.append(event)
        return new

    @_retry
    def events(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT body FROM events ORDER BY seq")
            return [row[0] for row in cur.fetchall()]

    @_retry
    def moods(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT ts, phase, value, source FROM mood_checkins ORDER BY seq")
            return [{"ts": ts.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "phase": phase, "value": value, "source": source}
                    for ts, phase, value, source in cur.fetchall()]

    @_retry
    def quests(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT body FROM quests ORDER BY position")
            return [row[0] for row in cur.fetchall()]

    @_retry
    def put_quest(self, quest):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO quests (id, day, place, body) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET day = EXCLUDED.day, place = EXCLUDED.place, body = EXCLUDED.body",
                (quest["id"], quest.get("day"), quest.get("place"), self.Jsonb(quest)))

    @_retry
    def outdoor_by_day(self, outdoor_labels, tz_name):
        params = {"tz": tz_name, "labels": list(outdoor_labels)}
        if self.time_bucket:
            try:
                return self._outdoor(self.OUTDOOR_TIME_BUCKET, params)
            except self.pg.Error:
                self.time_bucket = False  # an older TimescaleDB: use the plain form from now on
        return self._outdoor(self.OUTDOOR_PLAIN, params)

    def _outdoor(self, sql, params):
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.execute(sql, params)
            return [{"day": day.isoformat(), "minutes": int(minutes)} for day, minutes in cur.fetchall()]

    @_retry
    def counts(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT (SELECT count(*) FROM events), (SELECT count(*) FROM quests), "
                        "(SELECT body->>'ts' FROM events ORDER BY seq DESC LIMIT 1)")
            events, quests, last = cur.fetchone()
        return {"events": events, "quests": quests, "last_event": last}

    def info(self):
        return {"store": "postgres", "timescaledb": self.timescaledb, "hypertable": self.hypertable,
                "outdoor_query": "time_bucket" if self.time_bucket else "plain"}

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


def make_store(seed_path):
    """Postgres when DATABASE_URL is set, memory otherwise."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return PostgresStore(url, seed_path)
    return MemoryStore(seed_path)
