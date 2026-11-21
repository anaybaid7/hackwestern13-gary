# The contract

The only thing the four pillars share. Build against these files, not against
a teammate's running code.

**Rule:** changes are **additive only**. A new optional field is fine. A rename
or a removal needs all four of you to agree, in an issue.

## Files

| File | What it is |
| --- | --- |
| `labels.json` | The 79 things Gary can recognise, each marked outdoor or indoor. `friend` names the label that means a person is in frame |
| `examples/event.discovery.json` | A Sniff Test that named something |
| `examples/event.miss.json` | A Sniff Test that found nothing nameable |
| `examples/event.mood.json` | A private mood check-in |
| `examples/quest.json`, `quests.json` | One quest, and the three seed quests |
| `examples/state.json` | Everything the web page draws |

`state.json` is exactly what the backend returns after the three example
events are posted to a fresh backend. `backend/tests` checks that.

## Endpoints

| Call | Who uses it | Body | Returns |
| --- | --- | --- | --- |
| `POST /api/events` | device (`sync.py`) | `{"events": [Event]}` | `{"accepted", "duplicates", "results": [{"id", "xp", "reaction", "new", "quest_id"}]}` |
| `GET /api/quests?time=short\|long` | device, web | | `{"quests": [Quest]}`, open ones only. `?all=true` adds finished ones |
| `POST /api/quests` | scout | `{"quests": [Quest]}`, header `X-Scout-Key` if the server sets `SCOUT_KEY` | `{"accepted": [ids], "rejected": [{"id", "why"}]}` |
| `GET /api/state` | web | | State |
| `POST /api/mood` | web | `{"phase": "before"\|"after", "value": 1..5}` | `{"ok": true}` |
| `GET /api/wellness` | web | | private numbers. Never shown to anyone else |
| `POST /api/dev/reset` | demos, tests | | forgets events, reloads seed quests |
| `GET /api/health` | deploy checks | | `{"ok": true}` |

`reaction` is one of `quest_complete`, `new_discovery`, `seen_before`, `miss`, `mood`.

## Event (device → backend)

One JSON object per line of `device/journal.jsonl`. The device records facts
only. It never decides XP.

| Field | Meaning |
| --- | --- |
| `id` | Unique. Sending the same id twice counts once |
| `ts` | When it happened, UTC, `2026-11-21T05:20:00Z` |
| `type` | `discovery`, `miss` or `mood` |
| `device` | Which Gary |
| `label` | discovery: the thing, a name from `labels.json` |
| `score` | discovery: the model's confidence, 0 to 1 |
| `friend` | A person was in frame (Herd Mode) |
| `new` | discovery: first time this device saw that label. A hint; the backend recounts |
| `quest_id` | discovery: the quest the device thinks this completes, or `null`. The backend decides |
| `latency_ms` | Button press to answer, on the device |
| `phase`, `value` | mood: `before` or `after`, and 1 to 5 |

## Quest (scout → backend → device and web)

| Field | Meaning |
| --- | --- |
| `id` | Unique. Posting a known id replaces that quest |
| `title` | What Gary says: "Find a bench by the river at Harris Park" |
| `place` | A real place. Each place is one map tile |
| `time`, `minutes` | `short` or `long`, and a rough length |
| `target` | The thing to find. **Must be a name in `labels.json`**, or the backend refuses the quest |
| `xp` | 20 for short, 40 for long |
| `herd` | `true` means it only completes with a friend in frame |
| `source`, `source_url` | `tinyfish` and the page the agent read, or `seed` |
| `day` | `2026-11-21` |

## State (backend → web)

| Field | Meaning |
| --- | --- |
| `gary.stage` | `kid`, `scrambler`, `ibex` or `summit-elder`. Swap the image by this |
| `gary.xp`, `stage_xp`, `next_stage_xp` | For the progress bar. `next_stage_xp` is `null` at the last stage |
| `gary.napping` | It has been quiet. Show the napping pose. Never sad |
| `gary.welcome_back` | The last sniff ended a nap. Show the welcome-back line |
| `quest`, `quests_open` | The quest to show now, and how many are open |
| `journal` | Finds, newest first, each with the `xp` it earned |
| `guide` | Field guide: `total` things, and the names `found` |
| `map` | Up to 25 tiles: `place`, `quest_id`, `cleared`. Pad to 5 × 5 with fog |
| `herd.badges`, `herd.shared` | Herd Mode badges and how many finds had a friend in frame |
| `herd.cup` | Weekly Herd Cup: `week`, your `rank`, and a short `table` of herds. `demo: true` means the rivals are seeded |

Mood never appears in State.
