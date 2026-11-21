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
| `GARY_PRIVATE_KEY` | A passphrase for the private side. If set, the check-ins and the wellness view open only with it (`X-Private-Key`), and the page asks for it once per device. **Set this on the public server**: without it anyone who has the address can read the check-ins, and the page says so |
| `GARY_NAP_SECONDS` | Quiet time before Gary naps. Default 8 hours. A short value such as `60` shows a nap within minutes. Leave it out for the three-minute demo: Gary would be asleep again before the end |
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

**Verified on live Tiger Data on 21 Nov 2026**, using PostgreSQL 18.7 and
TimescaleDB 2.32.1 on a shared development service. `check_db.py` confirmed
the events hypertable and the `time_bucket` query. A temporary event posted
through Gary's API survived a fresh backend process, and uploading it again
counted once. The temporary event was removed after the check.

The connection is saved in ignored `backend/.env` on the setup machine.
Other teammates must configure their own local file; Git does not share it.
On the Windows setup machine, use the installed virtual environment:

```powershell
.\backend\venv\Scripts\python.exe backend/check_db.py
.\backend\venv\Scripts\python.exe -m uvicorn app:app --app-dir backend --reload --port 8000
```

On a database without TimescaleDB the code falls back to an ordinary table
and plain SQL, and says so in `/api/health` (`"hypertable": false`).

## Deploy on Vultr (issue #22)

**Gary is live at http://149.248.50.153** since Sat 21 Nov 2026, 12:55 pm: one
Vultr Cloud Compute instance in Toronto (shared CPU, 1 vCPU, 1 GB, Ubuntu
24.04). That one address is the web page (`/`) and the API (`/api/...`).

To update it after a merge, on the laptop that holds the server's SSH key:

```
git pull
sh backend/deploy/deploy.sh root@149.248.50.153
```

To set up a machine like it from nothing:

1. In Vultr, create a Cloud Compute instance: Shared CPU, the 1 GB plan
   (`vc2-1c-1gb`), Toronto, Ubuntu 24.04. **Pick your SSH key on that same
   screen.** A key added to the account afterwards is not put on a machine that
   already exists. Note the IP address.
2. From your laptop, in the repo:

```
sh backend/deploy/deploy.sh root@<ip address>
```

It builds the web page, copies `backend/`, `contract/` and `web/dist`, makes a
Python venv on the server, starts a service on port 80, opens port 80 in the
server's firewall, and checks `http://<ip address>/api/health`. With a key
that is not your default one, name it:
`GARY_SSH="ssh -i $HOME/path/to/key" sh backend/deploy/deploy.sh root@<ip address>`.

3. Secrets, on the server:

```
ssh root@<ip address>
nano /opt/gary/.env        # SCOUT_KEY, GARY_ADMIN_KEY, GARY_PRIVATE_KEY, DATABASE_URL
systemctl restart gary
```

`/api/health` then says which keys are set (`"keys"`), never what they are,
and where the data is kept (`"store"`).

4. Close the door. Logins with the key only, and a new root password, because
   Vultr shows the first one on the instance page:

```
ssh root@<ip address>
printf '%s\n' 'PasswordAuthentication no' 'KbdInteractiveAuthentication no' 'PermitRootLogin prohibit-password' > /etc/ssh/sshd_config.d/00-gary.conf
sshd -t && systemctl restart ssh
passwd
```

If the machine was made without your key, log in once with the password from
the instance page to add it: `ssh-copy-id -i ~/path/to/key.pub root@<ip address>`.

Point the device at the address with `GARY_API=http://<ip address>` in
`device/gary.env`, and the scout with `GARY_API` and `SCOUT_KEY` in `scout/.env`.
Logs: `journalctl -u gary -f`.

**What has run on the Vultr machine (21 Nov 2026):**

- `deploy.sh` from a Mac: the build, the copy, the venv, the service, the
  firewall line, the health check. The server came back by itself after a reboot.
- With the three keys set, posting quests, the reset and the private side each
  answer `401` without their key. Checked from a second network.
- `python3 scripts/demo.py replay` passed all eight beats against it, and
  `demo.py check` says READY. The scout posted its saved live-run quests with
  the scout key.

**Not yet:** `DATABASE_URL` is not set on the server, so it keeps its data in
memory and a restart forgets it (then `python3 scout/scout.py --cached` puts
the scout's quests back). The real device has not posted to it.

The page is served over plain `http`. That is fine for the demo. Anything that
needs `https` (an Auth0 login, issue #23, or the "where am I" dot on the map,
which browsers only allow on `https`) needs a domain name first.

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
- **Wellness.** Kept apart: nothing that builds `/api/state` reads it. With
  `GARY_PRIVATE_KEY` set it is also locked behind that passphrase. Before and
  after check-ins are paired within one outing. The summary reports what the
  person said and never claims a cause. Gary's own mood tap arrives with his
  other events: the device can write a check-in and can never read one.

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
