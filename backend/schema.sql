-- Gary's tables, for Postgres on Tiger Data. store.py runs this file at start;
-- every statement is safe to run again.
--
-- events is the time series: one row per Sniff Test (and per press of "short"
-- or "long" on the web page). On Tiger Data it becomes a hypertable on ts.
-- quests and mood_checkins are ordinary tables. Mood has a table of its own
-- because it is private: nothing that builds /api/state ever reads it.

CREATE TABLE IF NOT EXISTS events (
    seq         BIGSERIAL,                          -- arrival order: the rules fold events in this order
    ts          TIMESTAMPTZ NOT NULL,               -- when it happened, corrected if the device's clock was wrong
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(), -- when the backend got it
    id          TEXT        NOT NULL,
    type        TEXT        NOT NULL,               -- discovery | miss | choice
    device      TEXT,
    label       TEXT,                               -- discovery: the thing found
    friend      BOOLEAN     NOT NULL DEFAULT FALSE, -- a person was in frame
    body        JSONB       NOT NULL                -- the whole event, as rules.py reads it
);
CREATE INDEX IF NOT EXISTS events_seq_idx ON events (seq);

-- "The same id twice counts once." A hypertable cannot hold a unique index
-- on id alone (every unique index must include ts), so ids live here.
CREATE TABLE IF NOT EXISTS event_ids (
    id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS quests (
    position BIGSERIAL,          -- oldest first. Replacing a quest keeps its place
    id       TEXT PRIMARY KEY,
    day      TEXT,
    place    TEXT,
    body     JSONB NOT NULL      -- the whole quest, as in contract/README.md
);

CREATE TABLE IF NOT EXISTS mood_checkins (
    seq    BIGSERIAL PRIMARY KEY,
    ts     TIMESTAMPTZ NOT NULL,
    phase  TEXT        NOT NULL CHECK (phase IN ('before', 'after')),
    value  SMALLINT    NOT NULL CHECK (value BETWEEN 1 AND 5),
    source TEXT        NOT NULL DEFAULT 'web'      -- web | device
);

-- Picks for you (backend/picks.py): one row per request. What was asked (no
-- mood, no position: the name of a known place at most), every TinyFish run
-- with its id, and the picks. The next request reads the newest back.
CREATE TABLE IF NOT EXISTS pick_requests (
    seq  BIGSERIAL PRIMARY KEY,
    ts   TIMESTAMPTZ NOT NULL DEFAULT now(),
    body JSONB       NOT NULL
);
