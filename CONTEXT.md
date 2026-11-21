# CONTEXT: read this first

For teammates and their coding agents. It says what Gary is, what is built,
what is not, how to run it, and the rules for changing it.

**Keep the status section current.** When a pull request finishes an issue,
update the table here in the same pull request.

Last updated: Sat 21 Nov 2026, 2:23 pm, with the Reset Gary button for testing.

**Phases 1 to 5 are merged into `main`** (pull requests #42 to #46, merged Sat
21 Nov between 8:10 and 8:22 am). What is still open needs a person: an
account, a key, the Pi, or four voices. `docs/RUNBOOK.md` puts that work in
order.

## 1. What Gary is

Gary the Goat is a pocket mountain goat on a Raspberry Pi 5 running QNX. Press
his button and an on-device model names what his webcam sees (the **Sniff
Test**). The find lands in his journal, a patch of the fog-of-war map clears,
and he earns XP and grows. A friend in the frame makes it **Herd Mode**. Quests
come from a **TinyFish** web agent reading live local sites. Missing a day
costs nothing: Gary naps.

Hack Western 13. Hacking ends **Sun 22 Nov 2026, 9:00 am**. Main targets: Best
Health Hack (Sun Life) and Most Adventurous. Also QNX, TinyFish, Tiger Data,
Vultr. The full plan is `docs/PLAN.md`. Tasks are GitHub issues, grouped by
milestone (Phase 1 to Phase 6).

Two parts must be real for their prize tracks, never mocked: the Sniff Test
running on QNX on the Pi, and the scout working on live sites.

## 2. Status

| # | Issue | State | Notes |
| --- | --- | --- | --- |
| **Phase 1** | **Walking skeleton** | | |
| #2 | Contract | **Done** | `contract/` |
| #3 | Device: button-first Sniff Test | **Done** | Both versions. The QNX one is proven only against stand-ins |
| #4 | QNX gate: build and run on the Pi | **Done** | Built and run on the loaner Pi 5 (QNX 8.0), 21 Nov. Packages: `apk add opencv-dev tflite-runtime-dev tflite-runtime flatbuffers-dev qnx-sf-base-dev`. Logitech C270 = camera unit 5. Both models: 285 ms a frame (3.5 fps), a press answered in about 170 ms |
| #5 | `sync.py`, `fake_sniff.py` | **Done** | |
| #6 | Backend, bare-bones | **Done** | In memory. Starting rules are in |
| #7 | Web, bare-bones | **Done** | One page. The React prototype arrives in #24 |
| #8 | Scout: one live TinyFish run | **Done** | Live runs in `scout/runs.jsonl`, each with its TinyFish run id; quests reach `GET /api/quests` |
| #9 | End-to-end check | **Partly** | `python3 scripts/e2e.py` passes. Still needed: real device, live scout, a 20-second recording |
| **Phase 2** | **Device and hardware (A)** | | |
| #10 | Button triggers the Sniff Test | **Done** | On the Pi, Grove Base HAT socket D5: `GARY_BUTTON_PIN=5` in `gary.env` |
| #11 | Buzzer reacts to each sniff | **Done** | Socket D16: `GARY_BUZZER_PIN=16`. Right answers are quick beeps, a miss a slow "wah... wahhh" |
| #12 | Mood tap and short or long: where | **Proposed: the web page** | Needs the team's yes. The knob is analog and the Pi has no analog input. `gary_io.py --mood before 3` is the hook if the knob comes later |
| #13 | Field kit | **Partly** | `start_gary.sh`, `stop_gary.sh`, journal first, clock stamp. Still needed on the Pi: start at power-on, hotspot, strap, heat |
| #14 | QNX numbers | **Tools done, needs the Pi** | `gary_numbers.py`, `cpu_load.py`. `docs/qnx-numbers.md` has the steps and an empty table |
| #15 | Stretch: bigger vocabulary, a screen | **Vocabulary: done on the Pi** | SSD (everyday things, people) plus YOLOv8s trained on Open Images, both on every frame (`device/models/make_model.py`): 90 things, the old 79 plus tree, flower, squirrel, duck, goose, rabbit, deer, butterfly, mushroom, trash can, street lamp. `device/bench_model.py` scores it on photos. Both versions of Gary read it; the old SSD model still works with `--model`. No screen |
| **Phase 3** | **Backend, data, rules (B)** | | |
| #16 | Tiger Data: events, quests, state in Postgres | **Done** | Verified on Tiger Data on 21 Nov: events hypertable, `time_bucket`, API writes, persistence across fresh backend processes, and duplicate handling. Connection stored in ignored `backend/.env` on the setup machine |
| #17 | Rules: XP, stages, naps, welcome back | **Done** | `backend/rules.py` |
| #18 | Fog-of-war map | **Done** | Tiles also carry `cleared_at` and `finds` |
| #19 | Herd Mode and the Herd Cup | **Done** | Rival herds are seeded demo data, marked `demo: true` |
| #20 | Private mood, wellness view | **Done** | `GET /api/wellness` |
| #21 | Quest choice | **Done** | `POST /api/quest/choose` |
| #22 | Deploy on Vultr | **Live, still in memory** | http://149.248.50.153 since Sat 21 Nov, 12:55 pm (Vultr, Toronto, 1 vCPU, 1 GB, Ubuntu 24.04): the page and the API on one address. `deploy.sh` ran from Moe's Mac, the three keys are set, `demo.py replay` passed all eight beats against it, and it came back by itself after a reboot. Left: `DATABASE_URL` on the server (it keeps its data in memory), and the real device posting to it. The server's SSH key and its keys are only on Moe's Mac, in `~/.gary-deploy/`; he redeploys with `sh ~/.gary-deploy/redeploy.sh` |
| #23 | Stretch: Auth0 login | Open | Not started. It needs `https`, so a domain name first |
| **Phase 4** | **Front end (C)** | | |
| #24 | The React prototype, mock and live | **Partly** | Mock and live services behind one interface; every screen works in both. Restyled as **Pocket Pixel**: handheld frame, pixel Gary, Home / Map / Journal / Cup / Settings, quest details sheet, quest-complete screen, check-in pop-ups, OpenStreetMap with fog and your own location. The prototype's own code was never in this repo |
| #25 | Gary: stages, naps, welcome back, his voice | **Done** | Gary is a 32 x 32 pixel sprite in `web/src/sprites.js`: one drawing plus a few edits per stage |
| #26 | Fog-of-war map view | **Done** | Also: a lime frontier round cleared ground, a reveal when a place clears, a trail between cleared places, a quest beacon, "Quest" and "All places", a key, the distance from you, and a note when street tiles cannot load. The map now has a height in browsers without `dvh`, and no longer covers the quest-complete pop-up |
| #27 | Discovery journal and field guide | **Done** | |
| #28 | Quest card, short or long | **Done** | |
| #29 | Herd Mode screen, Herd Cup table | **Done** | No friends list: Gary never identifies anyone |
| #30 | Wellness view, private mood check-in | **Done** | |
| **Phase 5** | **Scout and story (D)** | | |
| #31 | Scout on three or more live London sites | **Done** | 21 Nov: 5 live runs on 5 sites (london.ca parks and events, Tourism London trails and events, Upper Thames conservation areas), 12 quests accepted by the backend |
| #32 | Scout checks | **Done** | Gary can name the target, one quest per place, nothing closed or risky, a note on where to stand. The tests need no key |
| #33 | Scout evidence for the judges | **Done** | `scout/EVIDENCE.md`, written by `python3 scout/scout.py --report` from `scout/runs.jsonl` |
| #34 | The TinyFish post | **Draft done, needs a person** | `docs/TINYFISH_POST.md`. It needs a real run to film and someone to post it |
| #35 | Devpost page | **Draft done** | `docs/DEVPOST.md`. Seven claims in it are marked `[A]` to `[G]`: each is true only when its issue is closed |
| #36 | Demo script and backup video | **Script done, needs the device** | `docs/DEMO.md`. Replayed against the backend, never rehearsed. Its tabs and taps describe the page before the Pocket Pixel redesign and are to be rewritten once the page is final. The video needs the real device |
| #37 | Stretch: Gemini writes Gary's lines | **Code done, needs a key** | `python3 scout/scout.py --voice`. Never run against Gemini |
| **Phase 6** | **Integration and demo** | | |
| #38 | Feature freeze and full rehearsal | **Tools done, needs the team** | `python3 scripts/demo.py check` says what would go wrong in the demo. `replay` rehearses it with no device. The rehearsal itself needs the device and four people |
| #39 | Fallbacks ready | **Partly** | Tested here: cached quests, a device with no network, the demo story with no backend. Needs people: the spare SD card, the video on two laptops. One drill each in `docs/RUNBOOK.md`, section 5 |
| #40 | Submit | **Prepared, needs the team** | `README.md` is rewritten for judges. `sh scripts/check_secrets.sh` before the repo goes public. The checklist is `docs/RUNBOOK.md`, section 6 |

**State words.** *Done*: finished and tested here. *Code done, needs the Pi*
(or a key, or an account): the software is written and tested with stand-ins,
and a person has to run it on the real thing. *Partly*: some boxes of the
issue are ticked. *Open*: not started.

To finish Phase 6, follow `docs/RUNBOOK.md` from the top. In short: bring the
real system up (Tiger Data, Vultr, the scout, Gary), run
`python3 scripts/demo.py check --api http://<server>` until it says READY,
rehearse twice, then submit by Sun 8:30 am.

To finish Phase 1, three things need a person:

1. **#4** Build and run `device/qnx/gary_qnx.cpp` on the Pi. Paste any build errors into the issue.
2. **#8** `export TINYFISH_API_KEY=...`, then `python3 scout/scout.py --dry-run`, then run it without `--dry-run`. Commit `scout/runs.jsonl`.
3. **#9** Run device, sync, backend and web together and record 20 seconds.

To finish Phase 5, four things need a person:

1. **#8, #31, #33** `export TINYFISH_API_KEY=...`, then `python3 scout/scout.py --one --dry-run`, then `python3 scout/scout.py`, then `python3 scout/scout.py --report`. Commit `scout/runs.jsonl`, `scout/EVIDENCE.md` and `scout/cached_quests.json`. If the first command fails, paste what it prints into #8.
2. **#34** Film one run (`docs/TINYFISH_POST.md` has the shot list), post it, put the link in the Devpost page.
3. **#35** In `docs/DEVPOST.md`, tick the claims table and fill in every square bracket.
4. **#36** Put names in `docs/DEMO.md`, rehearse it twice on the device, record the backup video.

To finish Phase 3, deployment remains (steps in `backend/README.md`):

1. **#16 is verified.** Other machines still need `DATABASE_URL` in their own ignored `backend/.env`; the connection is not distributed through Git. Run `python3 backend/check_db.py` to verify each setup.
2. **#22 is live** at http://149.248.50.153, with `SCOUT_KEY`, `GARY_ADMIN_KEY` and `GARY_PRIVATE_KEY` set. Two things are left. Tiger Data: put `DATABASE_URL` in `/opt/gary/.env` on the server (on Moe's Mac, `sh ~/.gary-deploy/set-database-url.sh` asks for the string and sends it straight there). The device: `GARY_API=http://149.248.50.153` in `device/gary.env` on the Pi.

To finish Phase 2, on the Pi, in this order (each step is in `device/README.md`):

1. **#4** first. Nothing else on the device matters until Gary builds on QNX.
2. **#10, #11** Wire the button and buzzer (README section 5), then `python3 gary_io.py --demo` and `python3 gary_io.py`.
3. **#13** `sh start_gary.sh`, then the power-on line, then a 5-minute walk.
4. **#14** The three runs in `docs/qnx-numbers.md`.

## 3. How the pieces connect

```
 Pi 5 on QNX  (device/)                  Vultr  (backend/)                Browser  (web/)
 ┌───────────────────────────┐          ┌────────────────────────┐      ┌───────────────────┐
 │ gary      camera → model   │ events   │ API + rules            │ state│ React + SVG Gary  │
 │   ▲ button (signal)        │ ───────► │ XP, stages, fog, herd  │ ───► │ map, journal,     │
 │   ▼ journal.jsonl          │ ◄─────── │ private mood store     │      │ quest, wellness   │
 │ sync.py   upload / fetch   │  quests  │ (memory, or Postgres   │      └───────────────────┘
 │ gary_io.py  button, buzzer │          │  on Tiger Data)        │
 └───────────────────────────┘          └───────────▲────────────┘
                                                      │ quests
                                          scout/  TinyFish agent on live sites
```

Who decides what. Do not move logic across these lines:

- **Device** records facts: what, when, friend or not. It never decides XP.
- **Backend** owns every rule: XP, stages, naps, the map, the herd.
- **Web** draws what the backend says. It decides nothing, with one
  exception for privacy: whether you are at the quest's place is worked out in
  the browser, so a position never leaves it. The page sends only "visited
  quest X" (`POST /api/visit`); the backend decides what that earns.
- **Scout** only writes quests.

## 4. Repo map

| Folder | Owner | What is in it |
| --- | --- | --- |
| `contract/` | shared | The JSON shapes and example files. The only shared surface |
| `device/` | A | `qnx/gary_qnx.cpp` (the real one), `gary_device.py` (laptop stand-in and fallback), `gary_io.py` (button, buzzer), `sync.py`, `start_gary.sh`, `gary_numbers.py`, `fake_sniff.py`, the model, sounds |
| `backend/` | B | `rules.py` (every rule), `app.py` (endpoints), `store.py` (memory or Postgres), `schema.sql`, `deploy/` (Vultr), tests |
| `web/` | C | React + Vite. `src/services/` is the only place that talks to the backend: `live.js`, and `mock.js` for the demo story. `src/screens/` has the five screens |
| `scout/` | D | `scout.py` (TinyFish call, places to quests, the checks, the evidence page), `sources.json` (the pages), `gary_voice.py` (optional Gemini step), tests |
| `docs/` | D | `PLAN.md`, `RUNBOOK.md` (from now to the submission), `DEMO.md` (the three-minute script), `DEVPOST.md` (the page, as a draft), `TINYFISH_POST.md`, `qnx-numbers.md`, `img/` (screenshots for the README) |
| `scripts/` | shared | `demo.py` (is the demo ready, reset it, replay it with no device), `check_secrets.sh` (keys in git, before the repo goes public), `e2e.py` (whole chain, no hardware), `check_all.sh` (every test), `make_examples.py` (writes the contract's example files from the backend) |

Each folder has its own README with run commands and file notes.

## 5. Run it

Four terminals, from the repo root. Nothing needs the Pi.

```
# 1. backend (starts with three seed quests, in memory. DATABASE_URL in backend/.env switches to Postgres)
cd backend && pip install -r requirements.txt && uvicorn app:app --reload --port 8000

# 2. web page, reading the backend
cd web && npm install && VITE_API_URL=http://localhost:8000 npm run dev

# 3. a pretend sniff: watch the page change
python3 device/fake_sniff.py bottle
python3 device/fake_sniff.py backpack --friend

# 4. sample quests from hand-written places (a live scout run needs TINYFISH_API_KEY: see scout/README.md)
python3 scout/scout.py --from-file scout/sample_result.json
```

The laptop version of the device, with a real webcam:

```
cd device && pip install -r requirements.txt
python3 gary_device.py --show                     # Enter = Sniff Test
python3 sync.py --api http://localhost:8000       # in another terminal
```

Web page with no backend at all: `cd web && npm run dev` (mock mode: a demo
story you click through). On any running page, add `?mock` to the address.

## 6. Test it

```
sh scripts/check_all.sh          # every suite below, skipping what this machine cannot run
```

| Suite | Command | Needs |
| --- | --- | --- |
| Backend against the contract | `cd backend && pytest` | Python. With `TEST_DATABASE_URL` set to a throwaway database, the same tests also run on Postgres |
| Scout | `python3 scout/tests/test_scout.py` | Python. No key, no network |
| Web | `cd web && npm test` | Node |
| Device scripts | `python3 device/tests/test_device.py` | Python. No Pi. The two tests of Gary himself also need the device requirements |
| QNX program, on a laptop | `sh device/qnx/host_test/run.sh` | Linux, g++, libopencv-dev |
| Whole chain | `python3 scripts/e2e.py` | Python with the backend and device requirements |
| Demo tools | `python3 scripts/tests/test_demo.py` | Python with the backend requirements. Also proves that the numbers quoted in `docs/DEMO.md` are what the backend gives |
| No keys in git | `python3 scripts/tests/test_check_secrets.py` | git |

None of these ever reads `backend/.env`: a test backend sets
`GARY_NO_ENV_FILE=1`, so it can never reach the real database named there.

Run `check_all.sh` before every push.

## 7. The contract

Full detail: `contract/README.md`. In brief:

- **Event** (device → `POST /api/events`): one journal line. `type` is
  `discovery`, `miss` or `mood`. A discovery has `label`, `score`, `friend`,
  `new`, `quest_id`, `latency_ms`. Sending the same `id` twice counts once.
- **Quest** (scout → `POST /api/quests`; anyone reads `GET /api/quests`):
  `id`, `title`, `place`, `time` (`short` or `long`), `target`, `xp`, `herd`,
  `note`, `source`, `source_url`, `day`. **`target` must be a name in
  `contract/labels.json`**, because the Sniff Test is what confirms a quest.
  `source` is `tinyfish` only for a quest from a live agent run; the page says
  "Found by the scout" for those and for nothing else.
- **State** (`GET /api/state` → web): `gary`, `quest`, `quest_choice`,
  `quest_options`, `journal`, `guide`, `map`, `herd`. Mood is never in it.
- **Choice** (`POST /api/quest/choose` with `{"time": "short"}`): makes a
  quest the active one. `GET /api/quests` then lists it first.
- **Wellness** (`GET /api/wellness`, private): check-ins, before and after
  pairs, a ready-made summary sentence, estimated outdoor minutes per day, and
  `locked`. With `GARY_PRIVATE_KEY` set on the server, this call and
  `POST /api/mood` need the passphrase in an `X-Private-Key` header.
- **Labels** (`contract/labels.json`): the 90 things Gary recognises, each
  marked outdoor or indoor, plus `friend` = `person`.

**Changes are additive only.** A new optional field is fine. A rename or a
removal needs all four owners to agree, in an issue.

## 8. Rules for coding agents

1. **Read first:** this file, then the README in the folder you will change,
   then `contract/README.md`, then the issue.
2. **Stay in your pillar's folder.** If you need something from another
   pillar, build against `contract/examples/` and say what you need in the issue.
3. **Do not move logic across the lines in section 3.**
4. **Product rules that code must never break:**
   - No penalties, no guilt, no streaks. Missed days cost nothing.
   - No individual rankings. Herds may be ranked (the Herd Cup); people never.
   - Mood is private. It never appears in `/api/state` or in anything shared.
   - No image is stored or uploaded. Only labels.
   - A friend is "a person is in frame". Never identify anyone.
   - The page says "private" about the check-ins only when they are behind
     the passphrase (`locked: true`). Otherwise it says the page is not locked.
   - Quest targets come from `contract/labels.json`. Quest wording is safe:
     public, accessible places only.
   - Only a quest from a live agent run is marked `tinyfish`. Never relabel a
     sample or hand-made quest to make a demo look better.
   - Health wording is careful: "you reported feeling better after two
     walks", never "the walk fixed your mood". Gary never diagnoses.
   - Every stage must be reachable solo.
5. **Keep the two device versions in step.** A change to `gary_device.py`
   needs the same change in `qnx/gary_qnx.cpp`, and the other way round.
   **Never name a Python file after one of Python's own modules** (`io.py`,
   `numbers.py`, `json.py` ...). It replaces that module for every script in
   the folder. `device/tests` checks this.
6. **Run `sh scripts/check_all.sh` before you push.** Add a test with every
   rule or behaviour you add. After a change to `backend/rules.py`, run
   `python3 scripts/make_examples.py` and commit the example files it rewrites.
7. **Secrets stay out of git.** Keys go in a local `.env`. Do not commit
   `journal.jsonl`, `quests.tsv`, `sync.state`, `node_modules` or `dist`.
8. **One branch and one pull request per issue** (or a small group). Write
   `Closes #N`. Update the status table in section 2 in the same pull request.
9. **Say what you could not verify.** If a change needs the Pi, the TinyFish
   key or a real phone to prove, say so in the pull request. Do not guess.

## 9. Where each phase starts

**Phase 2, device and hardware (A)**

- #4: follow `device/README.md` section 4 on the Pi.
- #10, #11: `device/gary_io.py` is written. It polls the button pin, sends
  `SIGUSR1` to the pid in `gary.pid`, and beeps from new lines of
  `journal.jsonl`. It uses only `setup`, `input` and `output`, so it does not
  depend on edge detection or PWM. On QNX the GPIO module is `rpi_gpio`. To
  change a pattern, edit `PATTERNS`; `tests/test_device.py` checks that the
  five still differ.
- #12: proposed, not yet agreed: mood and the short or long choice live on the
  web page. A `mood` line in `journal.jsonl` is uploaded by `sync.py` as it is,
  so a knob can be added later without touching anything else.
- #13: `start_gary.sh` and `stop_gary.sh`. Settings go in `device/gary.env`.
- #14: `gary_numbers.py` reads `latency.csv` (written when Gary stops) and the
  journal. `--priority 20` is the flag to compare.
- #15: a classifier beside `Detector` in both versions. New names would be an
  additive change to `contract/labels.json`.

**Phase 3, backend, data, rules (B)**

- `rules.py` holds every rule as pure functions: `compute()` for the state,
  `choose()` and `candidates()` for the active quest, `wellness()` for the
  private view. Constants are at the top. Tune there; do not start over.
- `app.py` checks what arrives, corrects a wrong device clock (`event_time`),
  and calls the store and the rules. `store.py` has `MemoryStore` and
  `PostgresStore` with the same methods; add a method to both or to neither.
- A press of short or long is stored as a `choice` event in the same stream as
  the sniffs, so a restart keeps it and old sniffs are never re-attributed.
- #16 is verified on Tiger Data. #22 is live at http://149.248.50.153, in memory until `DATABASE_URL` is set there: see the two steps under the status table.
- #23: not started. `/api/mood` and `/api/wellness` have no login.

**Phase 4, front end (C)**

- `web/src/services/index.js` is the one switch between mock and live. Both
  services offer the same calls. A new backend call goes into `live.js` and
  `mock.js` together.
- Mock mode plays `contract/examples/story.json`, which the backend wrote. Do
  not hand-edit it: change the story in `scripts/make_examples.py`.
- `App.jsx` asks for the state, compares it with the last one (`whatChanged`)
  and passes what is new to the screens, which animate it.
- The page never computes a rule. If a screen needs a number that is not in
  the state, ask for it in the contract.
- Gary's art, his lines, the pictures and the colours each live in one place:
  see "What to change, and where" in `web/README.md`.

**Phase 5, scout and story (D)**

- #8 first: the live run, with your key. Everything below it is written and
  waits for that run.
- #31: the pages are in `scout/sources.json`. To add one, add an entry with a
  `kind`, a `time` and a `goal` that asks for
  `{"places": [{"name": ..., "about": ...}]}`.
- #32: `TARGET_RULES` (which thing to find where), `RISKS` (what gets a place
  left out) and `NOTES` (where to stand) in `scout/scout.py`. `check_quests()`
  is the last look before anything is sent.
- #33: `scout/runs.jsonl` is the evidence and `--report` turns it into
  `scout/EVIDENCE.md`. Commit both after live runs.
- If TinyFish answers in a shape the code does not expect, the two places to
  look are `parse_sse()` and `find_places()`. `scout/tests/test_scout.py` has
  a stand-in for TinyFish (`FakeTinyFish`): add the real shape there first.
- #34 to #36 are documents in `docs/`. They are drafts: the claims in them
  that are not true yet are marked.
- #37: `scout/gary_voice.py`. `acceptable()` decides whether a reworded title
  is kept.

## 10. What is verified, and what is not

**Verified here, on a Linux machine**

- Backend: every rule and endpoint, in memory and on a real PostgreSQL 16
  (a restart keeps the state; the SQL for outdoor minutes matches the Python
  sum; a dropped connection is reopened). The contract's example files are
  checked against the backend.
- Deploy: the server script, rehearsed in a container with no systemd.
- Device, Python: Sniff Tests on photos and on a simulated camera feed, with
  key presses and signals.
- Device, C++: its logic and threading, against stand-ins for the QNX camera
  and TFLite, also under the address, undefined-behaviour and thread
  sanitizers. It compiles against the real TFLite 2.21 headers.
- Sync: upload, no network, lost state file, torn journal line.
- Button and buzzer script: debounce, the five patterns, following the
  journal, a stale `gary.pid`, all with stand-in pins. One real run: the
  Python Gary on a video file, pressed through `gary_io.py`.
- Start and stop scripts, on Linux, with a stand-in Gary: restart after a
  crash, survives a hangup, a clean stop, a fresh run.
- Scout: the whole path from the call to the backend, the run log and the
  evidence page, against a stand-in for TinyFish that sends the documented
  event stream (a good run, a failed one, one that hangs up, one that goes
  quiet, a refused key). A real call to TinyFish with a wrong key gets a
  clean `401`.
- Demo script: every "the screen shows" in `docs/DEMO.md` was replayed against
  the real backend, with `fake_sniff.py` standing in for Gary.
- Web: every screen drawn from the contract's example files, in mock and in
  live mode, with a stand-in service. The built page looked at in headless
  Chrome at 340, 390 and 1280 px, in mock mode and against the real backend.
- Whole chain: `scripts/e2e.py`.

**Also verified on Windows against live Tiger Data, 21 Nov 2026**

- PostgreSQL 18.7 and TimescaleDB 2.32.1 on a shared development service.
- `backend/check_db.py`: `events` is a hypertable and the `time_bucket` query succeeds.
- A temporary event posted through Gary's API survived a fresh backend process;
  uploading the same event again counted once. The temporary event was removed.
- API health reports `store: postgres`, `hypertable: true`, and `outdoor_query: time_bucket`.
- Backend tests: 63 passed; four requiring a separate throwaway database were skipped.

**Not verified**

- The C++ program has never been built or run on QNX (#4).
- No successful live TinyFish run (#8). The stand-in follows TinyFish's
  documents; the real service may differ.
- The Gemini step (`--voice`) has never called Gemini.
- The demo has not been rehearsed on the device or timed out loud.
- `docs/DEVPOST.md` makes seven claims that are not true yet. They are marked.
- No real webcam, speaker, button or buzzer has been used.
- `gary_io.py` has never touched real GPIO pins, on QNX or on Raspberry Pi OS.
- `start_gary.sh` has not run under QNX's shell, and the power-on line in
  `/usr/etc/post_startup.sh` is untested.
- `docs/qnx-numbers.md` has no numbers in it yet.
- The web page has not been opened on a real phone: location on the map, pinch zoom and the fog's zoom animation are checked only in tests and headless Chrome.
- The map's street tiles come from openstreetmap.org, so they need a network. Without one, the fog, pins and sheets still work, and the map says the street map is missing.
- The map's reveal, frontier, trail and "All places" were looked at in desktop Chrome 94 at 1280 px and 390 px. The distance line and the reduced-motion path are checked only in tests.

**Verified on the Vultr machine, 21 Nov 2026** (http://149.248.50.153, Ubuntu 24.04)

- `backend/deploy/deploy.sh` from a Mac: build, copy, venv, the systemd unit, the firewall line, the health check.
- The page and the API answer from a second network. The built page was looked at in headless Chrome against the live data: Home, Map, and Settings with the wellness view locked.
- Without their key, posting quests, the reset and the private side each answer `401`.
- `python3 scripts/demo.py replay` passed all eight beats against it; `demo.py check` says READY.
- After a reboot the service came back by itself, with the firewall and the key-only login unchanged.
- Not tried there: Tiger Data (`DATABASE_URL` is not set on the server yet, so a restart forgets everything), and the real device posting to it. The page is plain `http`.

**Known limits**

- With no `DATABASE_URL` the backend keeps everything in memory, and a restart
  starts fresh.
- Gary has no GPS. The Sniff Test proves the thing, not the place: a quest's
  place is taken on trust.
- There are no accounts. Mood never appears in the state or in anything
  shared. With `GARY_PRIVATE_KEY` set on the server, the check-ins and the
  wellness view open only with that passphrase, and the page says "Private".
  Without it, anyone who has the server's address can open `/api/wellness`,
  and the page says that instead.
- Anyone who has the server's address can post a sniff: `POST /api/events`
  has no key.
- Gary recognises 90 things (`device/models/make_model.py`). On photos (`device/bench_results.md`) he is good at squirrels, trees, butterflies and ducks, and weak at benches, dogs and backpacks (about 25%): the bottle and backpack in `docs/DEMO.md` need a rehearsal with the real camera.
- The Herd Cup's rival herds are seeded demo data, marked `demo: true`.

## 11. Decisions so far

| When | Decision |
| --- | --- |
| 21 Nov, 12:35 am | Four pillars, one folder each, joined only by the contract |
| 21 Nov, 1:15 am | XP rewards quests, outdoor finds and finds with a friend. Map tiles are real places. The journal is also a field guide. Herds compete weekly; individuals are never ranked |
| 21 Nov, 1:40 am | Backend: Python with FastAPI, in memory for Phase 1. Web: React with Vite. Scout: standard library, TinyFish `run-sse`. The device talks only through `journal.jsonl` and `sync.py` |
| 21 Nov, 2:40 am | The button script is `gary_io.py`, not `io.py`: that name hides Python's own `io` module. Buzzer patterns differ by rhythm, because the Grove buzzer is on/off. `sync.py` sends the device's clock with each upload |
| 21 Nov, 2:55 am | The Herd Cup counts quests finished with a friend plus places uncovered together; a tie goes to you, so your herd is never last. A sniff finishes any open quest that wants that thing; the quest chosen on the page wins a tie. The backend corrects a device clock that is wrong. Days and weeks turn over in `America/Toronto` |
| 21 Nov, 3:20 am | The web page was built fresh: the React prototype was never in the repo. Mock mode plays a ten-step story written by the real backend. Progress is drawn as a mountain; the quest is a trail sign. Typefaces are bundled, so the page works with no network |
| 21 Nov, 4:00 am | Only a quest from a live agent run is marked `tinyfish` and shown as "Found by the scout"; places from a file are `sample`. Short or long offers the scout's quests first, yesterday's too, and the built-in quests last. A quest carries the scout's line about where to stand (`note`). The demo script's eight beats were written from the features, because the concept breakdown's own list is not in the repo. The times in this table are commit times (an earlier version had some an hour or two late) |
| 21 Nov, 9:13 am | The private side can be locked with one passphrase (`GARY_PRIVATE_KEY`), and the page says "private" only when it is. The built page ignores `?api=`, so a link cannot send check-ins to another server. Tests never read `backend/.env`. `scripts/demo.py check` is the gate before a rehearsal or the demo |
| 21 Nov, 9:30 am | The page is restyled as Pocket Pixel. The map is OpenStreetMap (Leaflet) under fog; place positions are hand-placed in `web/src/places.js` (presentation only, not a contract change; optional `lat`/`lng` on quests is the upgrade). The browser's location is shown on the map and never sent anywhere. The leaderboard is the Herd Cup only. A long quest is shown as a trail walk. After a quest, a reward screen, then an optional "after" check-in |
| 21 Nov, 9:43 am | Phase 6 merged with the Pocket Pixel redesign. The passphrase form sits in the wellness view in Settings; the view wears "Private" only behind a passphrase and "Not locked" otherwise; a visitor without the passphrase is never shown the check-in pop-up. `docs/DEMO.md`, `docs/RUNBOOK.md` and the hints in `scripts/demo.py` still name the old tabs: left as they are until the page is final. Two layout rules that the new stylesheet had lost are back, in their own block: the spacing inside the wellness view (`.you`) and the small line under "Your herd" in the Cup table (`.cup-detail`). The highlight on the "Your herd" row and the rank-up animation (`.cup-row.moved`) are also gone from the stylesheet and were left for the web owner to decide |
| 21 Nov, 11:30 am | Gary's detector is YOLOv8s trained on Open Images, for nature: on photos it names squirrels 88%, trees 88%, ducks 60%, where YOLO-World (tried first) and SSD named none. It is weaker on benches and dogs (25%), so the scout's quests are now trees, squirrels, ducks, birds and bicycles. float32, because int8 ruins the class scores |
| 21 Nov, 1:04 pm | Gary's public address is http://149.248.50.153 (Vultr, Toronto), plain `http`, no domain. The server takes logins with one SSH key only; that key and the server's three keys are kept on Moe's Mac in `~/.gary-deploy/`, outside the repo |
| 21 Nov, 2:23 pm | Settings has a "Reset Gary" button for testing: it forgets every sniff and check-in and keeps the quests, which all open again (`POST /api/dev/reset` with `{"keep_quests": true}`). It asks first, and on a server with `GARY_ADMIN_KEY` it asks for that key. Gary on the Pi keeps his own list of finished quests, so there `sh start_gary.sh --fresh` is still needed |
| 21 Nov, 8:15 pm | The backend, the rules and the built page run on the Pi beside Gary, started by `start_gary.sh` (`GARY_BACKEND`). On QNX: FastAPI 0.99 with pydantic 1 (pydantic-core does not build), Gary's state in SQLite (`GARY_DB`, no Postgres driver), and asyncio's `SC_IOV_MAX` set to 1024 because QNX reports -1 and large replies were cut short. The live view is served by the backend at `/live/`. Gary's confidence threshold is 0.35 (a backpack scored 0.35-0.5); the 3-of-5-frame check still guards against false finds |
| 21 Nov, 9:30 pm | Been there: a quest finished at its place earns +10 XP. A bonus, not a gate, so Gary never punishes a sniff made elsewhere. The page compares the browser's location with the quest's `lat`/`lng` (within 150 m, or the fix's accuracy up to 500 m) and sends only the quest id; no position reaches the backend. The scout looks up positions on OpenStreetMap from the agent's street address. Hand-placed spots in `web/src/places.js` count as real; made-up map spots never do. Browsers give location only over HTTPS or on localhost |
| Open | Who takes A, B, C and D |
| Proposed | Mood tap and short or long choice: on the web page (#12). Needs the team's yes |

## 12. Words

| Word | Meaning |
| --- | --- |
| Sniff Test | One button press: Gary names what is in view and writes one journal line |
| Journal | `device/journal.jsonl`, and the list of finds on the web page |
| Field guide | The 90 things Gary can recognise, found or still locked |
| Herd Mode | A person is in the frame during a sniff. That sniff's XP doubles |
| Herd quest | A quest that only completes in Herd Mode |
| Herd Cup | The weekly ranking of herds. Never of people |
| Active quest | The quest on the card: the one chosen with short or long. With no choice, the oldest open quest |
| Scout | The TinyFish agent and `scout/scout.py` |
| Nap | Gary's state after a quiet spell. Not a penalty |
