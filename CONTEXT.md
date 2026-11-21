# CONTEXT: read this first

For teammates and their coding agents. It says what Gary is, what is built,
what is not, how to run it, and the rules for changing it.

**Keep the status section current.** When a pull request finishes an issue,
update the table here in the same pull request.

Last updated: Sat 21 Nov 2026, 3:00 am, with the Phase 2 pull request.

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
| #4 | QNX gate: build and run on the Pi | **Open** | Needs the Pi. Steps in `device/README.md` section 4 |
| #5 | `sync.py`, `fake_sniff.py` | **Done** | |
| #6 | Backend, bare-bones | **Done** | In memory. Starting rules are in |
| #7 | Web, bare-bones | **Done** | One page. The React prototype arrives in #24 |
| #8 | Scout: one live TinyFish run | **Partly** | Code and tests done. The live run needs `TINYFISH_API_KEY` |
| #9 | End-to-end check | **Partly** | `python3 scripts/e2e.py` passes. Still needed: real device, live scout, a 20-second recording |
| **Phase 2** | **Device and hardware (A)** | | |
| #10 | Button triggers the Sniff Test | **Code done, needs the Pi** | `device/gary_io.py`, tested with stand-in pins. On the Pi: wire it, run `python3 gary_io.py`, press once, check for one journal line |
| #11 | Buzzer reacts to each sniff | **Code done, needs the Pi** | `python3 gary_io.py --demo` plays the five patterns |
| #12 | Mood tap and short or long: where | **Proposed: the web page** | Needs the team's yes. The knob is analog and the Pi has no analog input. `gary_io.py --mood before 3` is the hook if the knob comes later |
| #13 | Field kit | **Partly** | `start_gary.sh`, `stop_gary.sh`, journal first, clock stamp. Still needed on the Pi: start at power-on, hotspot, strap, heat |
| #14 | QNX numbers | **Tools done, needs the Pi** | `gary_numbers.py`, `cpu_load.py`. `docs/qnx-numbers.md` has the steps and an empty table |
| #15 | Stretch: bigger vocabulary, a screen | Open | Not started on purpose: only after #4 passes on the Pi |
| **Phase 3** | **Backend, data, rules (B)** | Open | #16 to #23. A first version of the rules already exists |
| **Phase 4** | **Front end (C)** | Open | #24 to #30 |
| **Phase 5** | **Scout and story (D)** | Open | #31 to #37 |
| **Phase 6** | **Integration and demo** | Open | #38 to #40 |

**State words.** *Done*: finished and tested here. *Code done, needs the Pi*
(or a key, or an account): the software is written and tested with stand-ins,
and a person has to run it on the real thing. *Partly*: some boxes of the
issue are ticked. *Open*: not started.

To finish Phase 1, three things need a person:

1. **#4** Build and run `device/qnx/gary_qnx.cpp` on the Pi. Paste any build errors into the issue.
2. **#8** `export TINYFISH_API_KEY=...`, then `python3 scout/scout.py --dry-run`, then run it without `--dry-run`. Commit `scout/runs.jsonl`.
3. **#9** Run device, sync, backend and web together and record 20 seconds.

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
 │ sync.py   upload / fetch   │  quests  │ (memory now, Postgres  │      └───────────────────┘
 │ gary_io.py  button, buzzer │          │  on Tiger Data later)  │
 └───────────────────────────┘          └───────────▲────────────┘
                                                      │ quests
                                          scout/  TinyFish agent on live sites
```

Who decides what. Do not move logic across these lines:

- **Device** records facts: what, when, friend or not. It never decides XP.
- **Backend** owns every rule: XP, stages, naps, the map, the herd.
- **Web** draws what the backend says. It decides nothing.
- **Scout** only writes quests.

## 4. Repo map

| Folder | Owner | What is in it |
| --- | --- | --- |
| `contract/` | shared | The JSON shapes and example files. The only shared surface |
| `device/` | A | `qnx/gary_qnx.cpp` (the real one), `gary_device.py` (laptop stand-in and fallback), `gary_io.py` (button, buzzer), `sync.py`, `start_gary.sh`, `gary_numbers.py`, `fake_sniff.py`, the model, sounds |
| `backend/` | B | `app.py` (endpoints, in-memory store), `rules.py` (every rule), tests |
| `web/` | C | React + Vite. `src/api.js` is the only file that talks to the backend |
| `scout/` | D | `scout.py` (TinyFish call, places to quests), `sources.json`, tests |
| `docs/` | D | `PLAN.md`, later the Devpost text and demo script |
| `scripts/` | shared | `e2e.py` (whole chain, no hardware), `check_all.sh` (every test) |

Each folder has its own README with run commands and file notes.

## 5. Run it

Four terminals, from the repo root. Nothing needs the Pi.

```
# 1. backend (starts with three seed quests, in memory)
cd backend && pip install -r requirements.txt && uvicorn app:app --reload --port 8000

# 2. web page, reading the backend
cd web && npm install && VITE_API_URL=http://localhost:8000 npm run dev

# 3. a pretend sniff: watch the page change
python3 device/fake_sniff.py bottle
python3 device/fake_sniff.py backpack --friend

# 4. quests from the scout's saved reply (a live run needs TINYFISH_API_KEY)
python3 scout/scout.py --from-file scout/sample_result.json
```

The laptop version of the device, with a real webcam:

```
cd device && pip install -r requirements.txt
python3 gary_device.py --show                     # Enter = Sniff Test
python3 sync.py --api http://localhost:8000       # in another terminal
```

Web page with no backend at all: `cd web && npm run dev` (mock mode).

## 6. Test it

```
sh scripts/check_all.sh          # every suite below, skipping what this machine cannot run
```

| Suite | Command | Needs |
| --- | --- | --- |
| Backend against the contract | `cd backend && pytest` | Python |
| Scout | `python3 scout/tests/test_scout.py` | Python. No key, no network |
| Web | `cd web && npm test` | Node |
| Device scripts | `python3 device/tests/test_device.py` | Python. No Pi. The two tests of Gary himself also need the device requirements |
| QNX program, on a laptop | `sh device/qnx/host_test/run.sh` | Linux, g++, libopencv-dev |
| Whole chain | `python3 scripts/e2e.py` | Python with the backend and device requirements |

Run `check_all.sh` before every push.

## 7. The contract

Full detail: `contract/README.md`. In brief:

- **Event** (device → `POST /api/events`): one journal line. `type` is
  `discovery`, `miss` or `mood`. A discovery has `label`, `score`, `friend`,
  `new`, `quest_id`, `latency_ms`. Sending the same `id` twice counts once.
- **Quest** (scout → `POST /api/quests`; anyone reads `GET /api/quests`):
  `id`, `title`, `place`, `time` (`short` or `long`), `target`, `xp`, `herd`,
  `source`, `source_url`, `day`. **`target` must be a name in
  `contract/labels.json`**, because the Sniff Test is what confirms a quest.
- **State** (`GET /api/state` → web): `gary`, `quest`, `journal`, `guide`,
  `map`, `herd`. Mood is never in it.
- **Labels** (`contract/labels.json`): the 79 things Gary recognises, each
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
   - Quest targets come from `contract/labels.json`. Quest wording is safe:
     public, accessible places only.
   - Health wording is careful: "you reported feeling better after two
     walks", never "the walk fixed your mood". Gary never diagnoses.
   - Every stage must be reachable solo.
5. **Keep the two device versions in step.** A change to `gary_device.py`
   needs the same change in `qnx/gary_qnx.cpp`, and the other way round.
   **Never name a Python file after one of Python's own modules** (`io.py`,
   `numbers.py`, `json.py` ...). It replaces that module for every script in
   the folder. `device/tests` checks this.
6. **Run `sh scripts/check_all.sh` before you push.** Add a test with every
   rule or behaviour you add.
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

- Everything Phase 1 built is in `backend/rules.py` (pure functions) and
  `backend/app.py` (endpoints and the in-memory `Store`).
- #16: replace `Store` with Postgres on Tiger Data when `DATABASE_URL` is set.
  Keep the in-memory path for tests and for teammates. `rules.compute()` takes
  plain lists, so it does not change.
- #17, #18, #19: a first version exists in `rules.compute()`: XP, stages,
  naps, the welcome-back bonus, real-place map tiles, herd badges, and a Herd
  Cup with seeded rivals. Tune, extend and test. Do not start over.
- #20: `/api/mood` and `/api/wellness` exist in a minimal form.
- #21: add `POST /api/quest/choose`. Today `state.quest` is the first open quest.
- #22: `app.py` already serves `web/dist` at `/` when it exists.

**Phase 4, front end (C)**

- `web/src/api.js` is the seam. Mock mode draws `contract/examples/state.json`.
- #24: bring the React prototype in and point its mock-service interface at
  `api.js`. Keep mock mode working.
- #25 to #30: split `App.jsx` into screens. Every number comes from State.
  For the field guide, the full list of things is `contract/labels.json`.

**Phase 5, scout and story (D)**

- #8 first: the live run, with your key.
- #31: add pages to `scout/sources.json`. Each needs a `goal` that asks for
  `{"places": [{"name": ..., "about": ...}]}`.
- #32: `TARGET_RULES` and `build_quests()` in `scout/scout.py`, with tests in
  `scout/tests/`.
- #33: `scout/runs.jsonl` is the evidence. Commit it after live runs.

## 10. What is verified, and what is not

**Verified here, on a Linux machine**

- Backend: 18 tests, including the contract's example files against each other.
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
- Scout: stream parsing and quest building. A real call to TinyFish with a
  wrong key gets a clean `401`.
- Web: 3 tests, and the page looked at in headless Chrome at desktop and
  phone widths.
- Whole chain: `scripts/e2e.py`.

**Not verified**

- The C++ program has never been built or run on QNX (#4).
- No successful live TinyFish run (#8).
- No real webcam, speaker, button or buzzer has been used.
- `gary_io.py` has never touched real GPIO pins, on QNX or on Raspberry Pi OS.
- `start_gary.sh` has not run under QNX's shell, and the power-on line in
  `/usr/etc/post_startup.sh` is untested.
- `docs/qnx-numbers.md` has no numbers in it yet.
- The web page has not been opened on a real phone.

**Known limits**

- The backend keeps everything in memory. A restart starts fresh until #16.
- Gary recognises 79 things. Mushrooms, moss and bridges are not among them (#15).
- The Herd Cup's rival herds are seeded demo data, marked `demo: true`.

## 11. Decisions so far

| When | Decision |
| --- | --- |
| 21 Nov, 12:50 am | Four pillars, one folder each, joined only by the contract |
| 21 Nov, 1:20 am | XP rewards quests, outdoor finds and finds with a friend. Map tiles are real places. The journal is also a field guide. Herds compete weekly; individuals are never ranked |
| 21 Nov, 2:00 am | Backend: Python with FastAPI, in memory for Phase 1. Web: React with Vite. Scout: standard library, TinyFish `run-sse`. The device talks only through `journal.jsonl` and `sync.py` |
| 21 Nov, 3:00 am | The button script is `gary_io.py`, not `io.py`: that name hides Python's own `io` module. Buzzer patterns differ by rhythm, because the Grove buzzer is on/off. `sync.py` sends the device's clock with each upload |
| Open | Who takes A, B, C and D |
| Proposed | Mood tap and short or long choice: on the web page (#12). Needs the team's yes |

## 12. Words

| Word | Meaning |
| --- | --- |
| Sniff Test | One button press: Gary names what is in view and writes one journal line |
| Journal | `device/journal.jsonl`, and the list of finds on the web page |
| Field guide | The 79 things Gary can recognise, found or still locked |
| Herd Mode | A person is in the frame during a sniff. That sniff's XP doubles |
| Herd quest | A quest that only completes in Herd Mode |
| Herd Cup | The weekly ranking of herds. Never of people |
| Scout | The TinyFish agent and `scout/scout.py` |
| Nap | Gary's state after a quiet spell. Not a penalty |
