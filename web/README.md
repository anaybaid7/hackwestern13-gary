# Web

Gary's world, in a browser: Gary and his climb, the quest, the fog-of-war map,
the field guide and journal, the herd and the Herd Cup, and a private page for
mood check-ins.

The page draws what it is given and asks again every two seconds. Every number
on it comes from the backend. The page decides nothing.

## Run it

```
cd web
npm install

npm run dev                                       # mock mode: the demo story, no backend needed
VITE_API_URL=http://localhost:8000 npm run dev    # against the real backend
```

On a phone, add to the page address: `?mock` for the demo story, or
`?api=http://host:8000` for a backend somewhere else.

## Mock mode and live mode (issue #24)

One setting picks where the state comes from (`src/services/index.js`). Both
services offer the same calls, so every screen works in both modes:

| Call | Live (`services/live.js`) | Mock (`services/mock.js`) |
| --- | --- | --- |
| `getState()` | `GET /api/state` | the current step of the demo story |
| `chooseQuest(time)` | `POST /api/quest/choose` | picks one of the two offered quests |
| `postMood(phase, value)` | `POST /api/mood` | kept for this visit only |
| `getWellness()` | `GET /api/wellness` | the story's own, marked as demo data |
| `now()` | the real clock | the story's clock |

**The demo story** is `contract/examples/story.json`: ten states that the real
backend produced, a Saturday and a Sunday with Gary. Mock mode plays it one
step per press of "Next". It needs no backend, no device and no network, so it
is also the fallback if the Wi-Fi fails during judging: open the page with
`?mock`. `?mock&step=6` opens at step 6.

**The team's React prototype is not in here.** Its code was never added to
this repo, so these screens were built fresh on the same idea: mock services
and real services behind one interface. The prototype's components and art can
replace them one screen at a time.

## Build it

```
npm run build
```

This writes `web/dist`. The backend serves that folder at `/`, so after a
build, `http://localhost:8000/` is the page and the API on one address.
`backend/deploy/deploy.sh` does the build for you.

## Test it

```
npm test
```

The tests draw every screen from the contract's example files, in both modes.
They run in the `America/Toronto` timezone wherever the machine is.

## Where things are

The look is **Pocket Pixel**: a little handheld with a lime LCD, ink outlines,
hard shadows, Silkscreen and Space Mono. On a wide screen the page sits inside
the handheld; on a phone it fills the screen.

| File | What it holds |
| --- | --- |
| `src/App.jsx` | The frame: asks for the state, spots what is new, the handheld, the five screens, the check-in pop-up |
| `src/services/` | `index.js` (the switch), `live.js`, `mock.js`, `sample_wellness.js` (a made-up week, always labelled as demo) |
| `src/screens/Home.jsx` | Gary on his LCD, his line, the XP bar, today's quest, the recap |
| `src/screens/MapScreen.jsx` | OpenStreetMap (Leaflet) under fog. Cleared places glow through; each place is a pin; your location is a dot (never sent anywhere) |
| `src/screens/Guide.jsx` | The journal: finds, and the field guide (all 79 things), in two tabs |
| `src/screens/Herd.jsx` | The Herd Cup (a podium and the table, herds only), Herd Mode, the co-op quest, badges |
| `src/screens/Settings.jsx` | The check-in pop-up switch, the private wellness view (`You.jsx`), the connection, Gary's promises |
| `src/components/` | `Gary.jsx`, `Climb.jsx` (the XP bar), `QuestCard.jsx`, `QuestDetail.jsx`, `QuestComplete.jsx`, `CheckIn.jsx`, `Nav.jsx` (with the pixel icons), `FindRow.jsx`, `ThingIcon.jsx`, `StoryBar.jsx` |
| `src/sprites.js` | Gary's 32 x 32 sprite as text: one drawing, a few edits per stage, and the napping pose |
| `src/places.js` | Where each place is, as latitude and longitude. Unknown places get a steady spot near downtown |
| `src/pixel.js` | Turns text drawings into SVG, and the five colours |
| `src/voice.js` | Gary's lines and the one-sentence recap |
| `src/things.js` | A picture for each of the 79 things |
| `src/words.js` | Names for stage and badge ids |
| `src/styles.css` | Every style, with the colours and faces at the top |

## What to change, and where

- **Gary's art.** `src/sprites.js`. Each character in `BASE` is one pixel;
  the patches add horns, the scarf and the beard per stage.
- **A place on the map.** Add its name and `[lat, lng]` to `KNOWN` in `src/places.js`.
- **The fog.** `FOG_COLOUR` and `CLEAR_METRES` at the top of `src/screens/MapScreen.jsx`.
- **Gary's voice.** `src/voice.js`. A line tied to a thing goes in `BY_THING`.
  Keep him dry and kind: no nagging, no guilt, nothing about missed days.
- **A picture for a thing.** `src/things.js`. A thing with no picture shows
  its initials.
- **Colours and type.** The variables at the top of `src/styles.css`. The faces
  are Silkscreen and Space Mono, bundled with the page so it looks the same
  with no network.

## Rules this page keeps

- It never computes XP, stages, ranks or which tile clears. It draws them.
- Mood appears only in Settings and in the check-in pop-up. Each check-in
  can be skipped, and skipping sends nothing. The pop-up can be turned off.
- Seeded data is labelled where it is shown: the rival herds, the demo story,
  the sample week.
- A quest is credited to the scout ("Found by the scout on london.ca") only
  when its `source` is `tinyfish`, which only a live agent run sets. A sample
  quest and a built-in quest each say what they are. The link is made only
  from an `http` or `https` address.
- No individual rankings anywhere.

## Not checked

- No real phone has opened this page. It was looked at in headless Chrome at
  390 px and 1280 px wide, in mock mode and against the real backend.
- The field guide's pictures are emoji. They look a little different on each
  kind of phone, and a very old phone may show an empty box for a few of them.
