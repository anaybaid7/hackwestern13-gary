# Gary the Goat: build plan for four people

Hack Western 13. Hacking ends **Sun 22 Nov, 9:00 am**. Written Sat 21 Nov, 12:50 am.
Tasks live in the issue tracker, grouped by milestone. This page is the map.

## The product in one loop

Press the button. Gary's on-device model names what the webcam sees (the **Sniff
Test**). The find lands in his **discovery journal**, a patch of the
**fog-of-war map** clears, and he earns XP and grows. A friend in the frame
makes it **Herd Mode**, and herds compete in a weekly **Herd Cup**. Quests come
from a **TinyFish** agent reading live local sites. Missing a day costs nothing:
Gary naps.

Two parts must be real, because their tracks judge real use:

1. **QNX.** The Sniff Test runs on the Pi 5 under QNX with a QNX AI module.
2. **TinyFish.** The scout works on live sites.

Friends and mood history may stay seeded demo data, labelled as such.

## How the pieces connect

```
 Pi 5 on QNX  (device/)                  Vultr  (backend/)                Browser  (web/)
 ┌───────────────────────────┐          ┌────────────────────────┐      ┌───────────────────┐
 │ gary      camera → model   │ events   │ API + rules            │ state│ React + SVG Gary  │
 │   ▲ button (signal)        │ ───────► │ XP, stages, fog, herd  │ ───► │ map, journal,     │
 │   ▼ journal.jsonl          │ ◄─────── │ private mood store     │      │ quest, wellness   │
 │ sync.py   upload / fetch   │  quests  │ Tiger Data (Postgres)  │      └───────────────────┘
 │ gary_io.py  button, buzzer │          └───────────▲────────────┘
 └───────────────────────────┘                       │ quests
                                          scout/  TinyFish agent on live sites
```

The device records **facts** (what, when, friend or not). The backend owns every
**rule** (XP, stages, map). The web page only **draws** what the backend says.
The scout only **writes quests**.

## Who owns what

Pick a letter each. You only edit your own folder.

| | Pillar | Folder | You make real |
| --- | --- | --- | --- |
| A | Device and hardware | `device/` | Sniff Test on QNX, button, buzzer, sync |
| B | Backend, data, rules | `backend/` | API, XP and stages, fog map, Herd Mode, mood, Tiger Data, Vultr |
| C | Front end | `web/` | Gary and his stages, map, journal, quest card, Herd screen, wellness view |
| D | Scout and story | `scout/`, `docs/` | TinyFish on live sites, the required post, Devpost, demo script, video |

D writes less code than the others and carries the submission in exchange.

## The contract

This is the only thing the four pillars share. Phase 1 freezes it in
`contract/`. After that, changes are **additive only** (new optional fields).
A rename or removal needs all four to agree.

**Event**: device → backend, `POST /api/events` with `{"events": [...]}`.
Uploading the same `id` twice is harmless.

```json
{"id": "gary-01-1795238136597-3", "ts": "2026-11-21T05:20:00Z", "type": "discovery",
 "device": "gary-01", "label": "bench", "score": 0.93, "friend": true, "new": true,
 "quest_id": "q-12", "latency_ms": 41.0}
```

Other types: `miss` (sniffed, nothing nameable) and `mood` (`phase`: `before` or
`after`, `value`: 1 to 5).

**Quest**: scout → backend with `POST /api/quests`; anyone reads with
`GET /api/quests?time=short|long`.

```json
{"id": "q-12", "title": "Find a bench by the river at Harris Park", "place": "Harris Park",
 "time": "short", "minutes": 15, "target": "bench", "xp": 20, "herd": false,
 "source": "tinyfish", "source_url": "https://...", "day": "2026-11-21"}
```

`target` must be a name in `device/models/coco_labels.txt` or `gary_nature_labels.txt`. That is what lets
the Sniff Test confirm a quest. A `herd` quest completes only with a friend in frame.

**State**: backend → web, `GET /api/state`. Everything the page draws.

```json
{"gary": {"stage": "kid", "xp": 35, "next_stage_xp": 60, "napping": false, "welcome_back": false},
 "quest": {"id": "q-12", "title": "...", "time": "short", "target": "bench", "xp": 20, "herd": false},
 "journal": [{"id": "...", "ts": "...", "label": "bench", "friend": true, "new": true, "quest_id": "q-12", "xp": 40}],
 "guide": {"total": 80, "found": ["bench", "dog"]},
 "map": [{"place": "Harris Park", "quest_id": "q-12", "cleared": true},
         {"place": "Gibbons Park", "quest_id": "q-13", "cleared": false}],
 "herd": {"badges": ["first-herd"], "shared": 2,
          "cup": {"week": "2026-W47", "rank": 2,
                  "table": [{"herd": "Cliff Hangers", "score": 9},
                            {"herd": "Your herd", "score": 7, "you": true}]}}}
```

**Private**: `POST /api/mood` and `GET /api/wellness`. Mood never appears in
`/api/state` or in anything a friend could see.

**Labels**: `contract/labels.json` lists the 90 things Gary can recognise, each
marked outdoor or indoor, plus the label that means a person is in frame. The device, the rules and the field guide all read it.

Starting rules, owned by B in one file. XP follows the health goal, so the big
rewards need a quest, the outdoors or a friend:

- a quest done: 20 XP (short) or 40 XP (long)
- the first find of an outdoor thing: 10 XP; of an indoor thing: 2 XP
- a thing Gary has seen before: 1 XP
- a friend in frame doubles that sniff; the welcome-back bonus is 15 XP
- stages at 0, 60, 150 and 300 XP

Three things to collect, none of them a bare number:

- **Field guide.** The journal shows all 90 things, found or still locked.
- **Map.** Each tile is a real place the scout found. Its fog lifts when a quest
  there is done.
- **Herd Cup.** Each week herds are ranked by what they did together. It resets
  every Monday. Individuals are never ranked and last place is never shown.

No penalties anywhere. Every stage is reachable solo.

## Phases

| Phase | When | Who | Outcome |
| --- | --- | --- | --- |
| **1. Walking skeleton** | now → Sat 4 am | everyone, one thin slice each | The whole loop works end to end, ugly but real |
| **2. Device and hardware** | Sat 4 am → 10 pm | A | Button, buzzer, field kit, QNX numbers |
| **3. Backend, data, rules** | Sat 4 am → 10 pm | B | Tiger Data, full rules, Herd Mode, mood, Vultr |
| **4. Front end** | Sat 4 am → 10 pm | C | Gary's world: stages, map, journal, Herd, wellness |
| **5. Scout and story** | Sat 4 am → 10 pm | D | Live-site scout, evidence, post, Devpost, video |
| **6. Integration and demo** | Sat 10 pm → Sun 9 am | everyone | Freeze, rehearse, fallbacks, submit |

Phases 2 to 5 run at the same time and do not wait on each other.

**Phase 1 is done when:** you press Enter on the device while pointing at a
bottle, and within a few seconds the web page shows the discovery, a map tile
clears, and XP rises. The quest on screen came from a TinyFish run.

**Checkpoints on Saturday**

- **3 am, QNX gate.** `gary_qnx.cpp` builds and names an object on the Pi. If not,
  go to the QNX booth before anything else.
- **12 noon.** Real device → backend on Vultr → web page, with cached quests.
- **6 pm.** Scout verified on live sites. Hardware button working. Tiger Data in use.
- **10 pm.** Feature freeze.
- **Sun 6 am.** Devpost text, video and the TinyFish post are done.

## What keeps four people out of each other's way

1. **One folder each.** Nobody edits another pillar's folder. Ask its owner.
2. **The contract is the only meeting point.** Build against the examples in
   `contract/`, not against a teammate's running code.
3. **Every pillar ships a fake of itself in Phase 1**, so nobody waits:
   - Device: `gary_device.py` on a laptop webcam, or `fake_sniff.py bench --friend`
     to post a canned discovery. Nobody else needs the Pi.
   - Backend: runs in memory with seeded quests. One command, no database, no scout.
   - Web: mock mode when no API address is set.
   - Scout: `--dry-run` prints quests without a backend.
4. **Small pull requests into `main`, one pillar per PR.**
5. **Secrets stay out of git.** Keys go in a local `.env`.

## Hardware notes

- **Button and buzzer** are digital. They work on the Pi's GPIO. QNX ships a
  Python module for this, `rpi_gpio`. The button script sends Gary a signal, so it
  never touches the vision code.
- **The rotary knob is analog, and the Pi has no analog input.** Reading it needs
  the UNO Q in between. Cheaper option: do the mood tap and the short/long choice
  on the web page, and keep the knob as a stretch. Issue in Phase 2.
- **Grove plugs do not fit the Pi's pins.** Get Grove-to-jumper cables or a Grove
  base board from the hardware desk.
- **Small display.** The phone or laptop browser is Gary's face. A screen on the
  device is a stretch.
- **Outdoors there is no Wi-Fi.** The device writes its journal first and uploads
  when it can. A phone hotspot makes the walk demo live.
- **Sound.** A USB speaker is optional now that the buzzer carries feedback.

## Open decisions

1. Who takes A, B, C and D.
2. Backend language. Default: Python with FastAPI, because the TinyFish SDK and
   the device scripts are Python too. B may choose otherwise; the contract is
   what matters.
3. Mood tap and time choice: knob through the UNO Q, or the web page.
