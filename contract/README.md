# The contract

The only thing the four pillars share. Build against these files, not against
a teammate's running code.

**Rule:** changes are **additive only**. A new optional field is fine. A rename
or a removal needs all four of you to agree, in an issue.

## Files

| File | What it is |
| --- | --- |
| `labels.json` | The 90 things Gary can recognise, each marked outdoor or indoor. `friend` names the label that means a person is in frame |
| `examples/event.discovery.json` | A Sniff Test that named something |
| `examples/event.miss.json` | A Sniff Test that found nothing nameable |
| `examples/event.mood.json` | A private mood check-in |
| `examples/quest.json`, `quests.json` | One quest, and the three seed quests |
| `examples/quests.scout.json` | Hand-written examples of what one scout run posts |
| `examples/state.json` | Everything the web page draws |
| `examples/wellness.json` | The private wellness view |
| `examples/story.json` | Ten states in a row: a Saturday and a Sunday with Gary. The web page's mock mode plays it |

`state.json`, `wellness.json` and `story.json` are written by
`python3 scripts/make_examples.py` from the real backend, with the clock
pinned. Do not edit them by hand. `backend/tests` fails if they are out of date.

- `state.json` is what the backend returns after the three example events are
  posted to a fresh backend.
- `wellness.json` is the wellness view after the same three events and one
  "after" check-in.

## Endpoints

| Call | Who uses it | Body | Returns |
| --- | --- | --- | --- |
| `POST /api/events` | device (`sync.py`) | `{"events": [Event], "sent_at": "..."}` | `{"accepted", "duplicates", "results": [{"id", "xp", "reaction", "new", "quest_id"}]}` |
| `GET /api/quests?time=short\|long` | device, web | | `{"quests": [Quest]}`, open ones only, **the active one first** and marked `"active": true`. `?all=true` adds finished ones |
| `POST /api/quests` | scout | `{"quests": [Quest]}`, header `X-Scout-Key` if the server sets `SCOUT_KEY` | `{"accepted": [ids], "rejected": [{"id", "why"}]}` |
| `POST /api/quest/choose` | web | `{"time": "short"\|"long"}` | `{"quest": Quest or null, "state": State}`. Makes a quest of that length the active one. Asking again gives the next one |
| `GET /api/state` | web | | State |
| `POST /api/visit` | web | `{"quest_id": "..."}` | `{"ok": true}`, `422` for an unknown quest. The page sends it when it works out, in the browser, that you are at that quest's place. **No position is ever sent**; only the quest id is kept. A quest finished from 2 hours after a visit to 30 minutes before one earns the Been there bonus (+10 XP, never doubled) |
| `POST /api/mood` | web | `{"phase": "before"\|"after", "value": 1..5}`, header `X-Private-Key` if the server sets `GARY_PRIVATE_KEY` | `{"ok": true}`. `401` without the passphrase |
| `GET /api/wellness` | web | header `X-Private-Key` if the server sets `GARY_PRIVATE_KEY` | Wellness. `401` without the passphrase |
| `POST /api/dev/reset` | demos, tests, the page's "Reset Gary" button | optional `{"keep_quests": true}`; header `X-Admin-Key` if the server sets `GARY_ADMIN_KEY` | with `keep_quests`: forgets events and moods, keeps every quest and opens them all again. Without it: forgets events and moods, reloads seed quests |
| `GET /api/health` | deploy checks | | `{"ok": true, "events", "quests", "last_event", "store": "memory"\|"postgres", ...}` |

`reaction` is one of `quest_complete`, `new_discovery`, `seen_before`, `miss`, `mood`.

`sent_at` is what the device's clock reads when it uploads. A Pi that starts
with no network may not know the time; the backend uses `sent_at` to move the
upload's timestamps onto its own clock. It is optional.

## Event (device → backend)

One JSON object per line of `device/journal.jsonl`. The device records facts
only. It never decides XP.

| Field | Meaning |
| --- | --- |
| `id` | Unique. Sending the same id twice counts once |
| `ts` | When it happened, UTC, `2026-11-21T05:20:00Z` |
| `type` | `discovery`, `miss` or `mood`. Anything else is refused |
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
| `id` | Unique. Posting a known id replaces that quest, in place |
| `title` | What Gary says: "Find a bench by the river at Harris Park". One line, at most 140 characters |
| `place` | A real place. Each place is one map tile. Capitals and spacing do not matter. At most 80 characters |
| `time`, `minutes` | `short` or `long`, and a rough length |
| `target` | The thing to find. **Must be a name in `labels.json`**, or the backend refuses the quest |
| `xp` | 20 for short, 40 for long. The backend refuses anything outside 1 to 100 |
| `herd` | `true` means it only completes with a friend in frame |
| `note` | Optional. One line from the scout about where to stand: "Stay on the marked trail. Any safe, accessible spot counts." |
| `source`, `source_url` | `tinyfish` and the page the agent read: only these are shown as "Found by the scout". `seed` for the built-in quests. `sample` for hand-written places posted with `scout.py --from-file`. `source_url` must be an `http` or `https` address, or the backend drops it |
| `lat`, `lng` | Optional. The place's real position in decimal degrees: the scout looks it up on OpenStreetMap. The page uses it to tell when you are there. Anything that is not a number in range is dropped |
| `day` | `2026-11-21`, the local day. "Today's" quests are the ones dated today. Short or long offers today's scout quests first, then anything else added today, then the scout's older quests (newest first), then the built-in ones |
| `active` | Only in `GET /api/quests`: this is the quest on the card |

## State (backend → web)

| Field | Meaning |
| --- | --- |
| `gary.stage` | `kid`, `scrambler`, `ibex` or `summit-elder`. Swap the image by this |
| `gary.xp`, `stage_xp`, `next_stage_xp` | For the progress bar. `next_stage_xp` is `null` at the last stage |
| `gary.napping` | It has been quiet. Show the napping pose. Never sad |
| `gary.welcome_back` | The last sniff ended a nap. Show the welcome-back line |
| `quest` | The quest to show now: the chosen one, or the oldest open one if nothing was chosen. `null` when all are done |
| `quest_choice` | `short`, `long`, or `null` if the person has not chosen |
| `quest_options` | `{"short": Quest or null, "long": Quest or null}`: what each button would give |
| `quests_open` | How many quests are open |
| `journal` | Finds, newest first (at most 50), each with the `xp` it earned, the `place` of the quest it finished (or `null`), and `been_there`: the page said you were at that place |
| `guide` | Field guide: `total` things, and the names `found` |
| `map` | Up to 25 tiles. Pad to 5 × 5 with fog. Each: `place`, `quest_id`, `cleared`, `cleared_at`, `finds`: what was found there (`label`, `ts`, `friend`, `quest_id`), `lat`/`lng` (or `null`), and `visited`: the page has said you were there |
| `herd.badges` | Earned together, never taken away: `first-herd`, `herd-quest`, `herd-of-five`, `trail-mates` |
| `herd.shared` | How many finds had a friend in frame |
| `herd.quest` | An open co-op quest, or `null` |
| `herd.cup` | The weekly Herd Cup: `week`, your `rank` out of `herds`, a `table` of the top three herds plus yours, and `ahead`: the herd just above yours and the `gap` to pass it. Your row also has `quests` and `places`. `demo: true` means the rivals are seeded |

Mood never appears in State.

## Wellness (backend → web, private)

| Field | Meaning |
| --- | --- |
| `private` | Always `true`: none of this may ever be shown in Gary's shared world |
| `locked` | `true` when a passphrase guards this reply. The page may say "private" only then. When `false`, anyone who has the address can read it, and the page says that instead |
| `checkins` | Every check-in, oldest first: `ts`, `phase`, `value`, `source` (`web` or `device`) |
| `pairs` | A "before" and the "after" of the same outing: `day`, `before`, `after`, `change`, `minutes` |
| `summary` | One careful sentence, ready to show: "You reported feeling better after 2 of 3 outings." |
| `outdoor`, `outdoor_minutes` | Estimated minutes outdoors per local day, and the total |
| `outdoor_note` | How that estimate is made. Show it with the number |
| `finds`, `solo`, `shared` | How many finds, alone and with a friend in frame |
