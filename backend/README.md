# Backend

A small API in front of `rules.py`. The device sends facts, the scout sends
quests, and this is where every rule lives: XP, stages, naps, the map, the
herd, the active quest and the private wellness numbers. The shapes are in
[`../contract`](../contract/README.md).

With nothing set it keeps everything in memory. Set `DATABASE_URL` and it uses
Postgres on Tiger Data, and a restart keeps Gary's state.

## Run it

```
cd backend
python3 -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Open http://localhost:8000/docs to try every endpoint in the browser.
Add `--host 0.0.0.0` so the Pi or a phone on the same network can reach it.

It starts with the three seed quests from `contract/examples/quests.json`. No
scout, no device and no database are needed.

## Try it with curl

```
# what the web page draws
curl -s localhost:8000/api/state

# a sniff arrives (the contract's example: a bench, with a friend, at Harris Park)
curl -s -X POST localhost:8000/api/events -H 'Content-Type: application/json' \
     -d @../contract/examples/event.discovery.json

# open quests. The active one comes first
curl -s localhost:8000/api/quests

# short or long picks the active quest. Ask again for the next one
curl -s -X POST localhost:8000/api/quest/choose -H 'Content-Type: application/json' -d '{"time":"short"}'

# the scout adds a quest
curl -s -X POST localhost:8000/api/quests -H 'Content-Type: application/json' \
     -d '{"id":"q-gibbons-dog","title":"Find a dog at Gibbons Park","place":"Gibbons Park","time":"short","target":"dog","xp":20}'

# a private mood check-in, and the private view
curl -s -X POST localhost:8000/api/mood -H 'Content-Type: application/json' -d '{"phase":"before","value":3}'
curl -s localhost:8000/api/wellness

# start over
curl -s -X POST localhost:8000/api/dev/reset
```

No device handy? From the repo root: `python3 device/fake_sniff.py bench --friend`.

## Settings

All optional. Set them in the shell, or copy `.env.example` to `.env` here.
On the server they live in `/opt/gary/.env`. None of these files is in git.

| Setting | Meaning |
| --- | --- |
| `DATABASE_URL` | Postgres on Tiger Data. Unset: memory |
| `SCOUT_KEY` | If set, the scout must send it as `X-Scout-Key` to post quests |
| `GARY_ADMIN_KEY` | If set, `POST /api/dev/reset` must send it as `X-Admin-Key`. **Set this on the public server**, or anyone can wipe the demo |
| `GARY_NAP_SECONDS` | Quiet time before Gary naps. Default 8 hours. `60` shows a nap and a welcome back inside a three-minute demo |
| `GARY_TZ` | Where days and weeks turn over. Default `America/Toronto` |
| `GARY_SEED` | The quests a fresh backend starts with |

## Tiger Data (issue #16)

1. In Tiger Console, create a service and copy the connection string it
   gives you. It looks like
   `postgres://tsdbadmin:...@....tsdb.cloud.timescale.com:.../tsdb?sslmode=require`.
2. Put it in `backend/.env` as `DATABASE_URL=...`.
3. Check it:

```
python3 check_db.py
```

It creates the tables and reports whether `events` is a hypertable and whether
the `time_bucket` query runs. Paste its output into issue #16.

What is stored (`schema.sql`):

| Table | What |
| --- | --- |
| `events` | One row per Sniff Test and per press of short or long. **A hypertable on `ts`** |
| `event_ids` | Ids already seen, so the same upload twice counts once. A hypertable cannot hold a unique index on `id` alone |
| `quests` | The quests, oldest first |
| `mood_checkins` | Private. Nothing that builds `/api/state` reads it |

The wellness view's outdoor minutes per day are one `time_bucket` query
(`OUTDOOR_TIME_BUCKET` in `store.py`): each 10-minute block with an outdoor
find counts as 10 minutes.

**Tested on plain PostgreSQL 16, not on Tiger Data.** The hypertable step and
the `time_bucket` query could not be run here. On a database without
TimescaleDB the code falls back to an ordinary table and plain SQL, and says so
in `/api/health` (`"hypertable": false`). `check_db.py` is the proof on the
real service.

## Deploy on Vultr (issue #22)

1. In Vultr, create a Cloud Compute instance: Ubuntu 24.04, the smallest plan,
   Toronto. Add your SSH key. Note its IP address.
2. From your laptop, in the repo:

```
sh backend/deploy/deploy.sh root@<ip address>
```

It builds the web page, copies `backend/`, `contract/` and `web/dist`, makes a
Python venv on the server, starts a service on port 80, opens port 80 in the
server's firewall, and checks `http://<ip address>/api/health`.

3. Secrets, on the server:

```
ssh root@<ip address>
nano /opt/gary/.env        # DATABASE_URL, SCOUT_KEY, GARY_ADMIN_KEY
systemctl restart gary
```

Then one address carries both: `http://<ip address>/` is the web page and
`http://<ip address>/api/...` is the API. Point the device at it with
`GARY_API=http://<ip address>` in `device/gary.env`.

Run `deploy.sh` again to update. Logs: `journalctl -u gary -f`.

**Not tested on a Vultr machine.** The server script was rehearsed here in a
container without systemd: the copy, the venv, the service user and the start
command work, and a restart kept the state on Postgres. The systemd unit and
the firewall line have not run.

The page is served over plain `http`. That is fine for the demo. Anything that
needs `https` (an Auth0 login, issue #23) needs a domain name first.

## The rules, in brief

Everything is in `rules.py`, as pure functions with tests. To change a number,
change the constant at the top and run the tests.

- **XP.** A quest: its own XP (20 short, 40 long). First find of an outdoor
  thing: 10. Of an indoor thing: 2. Seen before: 1. A friend in frame doubles
  that sniff. First sniff after a nap: +15.
- **Stages** at 0, 60, 150 and 300 XP. Every stage can be reached alone.
- **Naps.** Quiet for `GARY_NAP_SECONDS` and Gary naps. Nothing is ever taken away.
- **Which quest a sniff finishes.** Any open quest whose target is the thing
  found; a herd quest also needs a friend. If several fit: the one chosen on
  the web page, then the one the device named, then the oldest.
- **Short or long.** A press offers, in this order: the scout's quests dated
  today, anything else added today, the scout's older quests (newest first),
  then the built-in quests. Pressing again moves to the next one.
- **Map.** One tile per real place, newest 25. A tile clears when a quest
  there is done, and remembers what was found.
- **Herd Cup.** This week's quests finished with a friend, plus places
  uncovered together. Resets on Monday, local time. Rival herds are seeded
  demo data (`demo: true`). A tie goes to you, so your herd is never last.
  People are never ranked.
- **Wellness.** Private. Before and after check-ins are paired within one
  outing. The summary reports what the person said and never claims a cause.

**What a posted quest must be.** A quest's words can come from a web page,
through the scout, and they end up in a link on the page and in the device's
quest file. So `app.py` cleans every quest as it arrives (`check_quest`): the
id, title, place and note become one plain line each and are cut to a set
length; `source_url` is kept only if it is an `http` or `https` address; `xp`
must be between 1 and 100; and the target must be an outdoor thing Gary can
name. A quest is marked `source: "tinyfish"` only by the scout's live runs,
and the page says "Found by the scout" for those alone. Set `SCOUT_KEY` on the
server so that nobody else can post quests.

One limit to be honest about: **Gary has no GPS.** The Sniff Test proves the
thing, not the place. A quest's place is taken on trust.

**A device with a wrong clock.** A Pi that boots with no network may not know
the time. `sync.py` sends what the device's clock reads with each upload, and
the backend moves that upload's timestamps by the difference. The device's own
value is kept as `device_ts`.

## Test it

```
cd backend && pytest                      # in memory

# the same tests against Postgres as well. Use a throwaway database: every test wipes it
TEST_DATABASE_URL=postgresql://user@localhost:5432/gary_test pytest
```

After any change to `rules.py`, refresh the contract's example files and
commit them: `python3 ../scripts/make_examples.py`. A test fails until you do.

## Files

| File | What it holds |
| --- | --- |
| `rules.py` | Every rule. Pure functions, no HTTP, no storage |
| `app.py` | The endpoints, the checks on what arrives, the clock correction |
| `store.py` | `MemoryStore` and `PostgresStore`, with the same methods |
| `schema.sql` | The tables |
| `check_db.py` | Is the database ready, and is Tiger Data in use |
| `deploy/deploy.sh`, `deploy/setup.sh` | Vultr |
| `tests/` | The API and the rules, against memory and, when `TEST_DATABASE_URL` is set, against Postgres too |
