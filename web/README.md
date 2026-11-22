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

Add `?mock` to the page address for the demo story, on any device. With
`npm run dev` only, `?api=http://host:8000` points the page at a backend
somewhere else. The built page ignores `?api`, so that a link can never send
someone's check-ins to another server.

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
| `src/whereAmI.js` | The browser's location, for the map and for "Been there". It stays in the browser |
| `src/screens/MapScreen.jsx` | The map screen: the header, the buttons, the key and the sheet under the map. It draws the map in 3D (`World3D.jsx`) where the browser has WebGL, and flat (`FlatWorld.jsx`) everywhere else, when the 3D map cannot start, or when you press "2D" (the choice is kept in this browser). Cleared places glow through the fog with a dashed lime frontier round their edge, and one that has just cleared opens up from nothing and is panned into view. A dotted trail joins the cleared places in the order they were uncovered. Each place is a pin; the quest's pin sends out a beacon. "Quest" and "All places" move the map; a row of cells under the title lights one per uncovered place; a key says what the marks mean. Your location is a dot, and the sheet says how far a place is from you, worked out in the browser (never sent anywhere), with "Walk there" for walking directions in the phone's maps app (the link carries only the place). Pins sit at the scout's real positions when a quest has them. Without a network it says the street map is missing; the fog and pins still work |
| `src/screens/World3D.jsx` | The 3D map, in MapLibre, loaded only when it is used: London tilted, with real building heights (OpenFreeMap's free vector tiles) and the Thames valley shaded (free terrain tiles), in the Pocket Pixel colours. The fog is a low bank of cloud with each cleared place cut out of it and a lime rim on its edge; the trail floats over it; the quest is a coral beacon. Tapping a pin flies down to it |
| `src/screens/FlatWorld.jsx` | The flat map: OpenStreetMap (Leaflet) with the fog painted on a canvas |
| `src/map/shapes.js`, `src/map/marks.js`, `src/map/look.js` | The 3D map's shapes (the fog with its holes, the rim, the dashed trail), the pins both maps share, and which map to draw |
| `src/screens/Guide.jsx` | The journal: finds, and the field guide (all 79 things), in two tabs |
| `src/screens/Herd.jsx` | The Herd Cup (a podium and the table, herds only), Herd Mode, the co-op quest, badges |
| `src/screens/Settings.jsx` | The check-in pop-up switch, the private wellness view (`You.jsx`), the connection, Gary's promises |
| `src/components/` | `Gary.jsx`, `Climb.jsx` (the XP bar), `QuestCard.jsx`, `QuestDetail.jsx`, `QuestComplete.jsx`, `CheckIn.jsx`, `Nav.jsx` (with the pixel icons), `FindRow.jsx`, `ThingIcon.jsx`, `StoryBar.jsx`, `Picks.jsx` (picks for you, from a live TinyFish run; live mode only) |
| `src/sprites.js` | Gary's 32 x 32 sprite as text: one drawing, a few edits per stage, and the napping pose |
| `src/places.js` | Where each place is, as latitude and longitude. Unknown places get a steady spot near downtown |
| `src/pixel.js` | Turns text drawings into SVG, and the five colours |
| `src/sound.js` | Gary's sounds in the browser: his spoken ElevenLabs clips (`device/sounds/say_*.wav`) by the device's rule, the chimes if a clip is missing. Off in Settings |
| `src/voice.js` | Gary's lines, a fact for each find, a quest's trail tidbit, and the one-sentence recap |
| `src/gary_lines.json` | A line and two facts for each thing, and pools of everyday lines: written once by Gemini (`scout/gary_lines.py`), read and corrected by a person |
| `src/things.js` | A picture for each of the 79 things |
| `src/words.js` | Names for stage and badge ids |
| `src/styles.css` | Every style, with the colours and faces at the top |

## Gary's hello

A device that has not met Gary gets `components/Welcome.jsx` first: five beats, one tap each,
under half a minute. It talks to no backend and saves nothing but `gary.met` in the browser.
Gary's lines are in `LINES`; a test keeps them under 90 words and the same as in
`device/make_voice.py`, which makes their spoken clips (`python3 device/make_voice.py`). "Meet Gary again" in
Settings replays it.

## What to change, and where

- **Gary's art.** `src/sprites.js`. Each character in `BASE` is one pixel;
  the patches add horns, the scarf and the beard per stage.
- **A place on the map.** Add its name and `[lat, lng]` to `KNOWN` in `src/places.js`.
- **The fog.** Flat map: `FOG_COLOUR`, `CLEAR_METRES`, `FRONTIER` (the edge's colour) and `REVEAL_MS` (how long a new place takes to open) at the top of `src/screens/FlatWorld.jsx`. 3D map: `FOG_TOP` (how high the fog is) and the colours at the top of `src/screens/World3D.jsx`, and `CLEAR_METRES` in `src/map/shapes.js`. With reduced motion on, places open at once and the 3D camera jumps instead of flying.
- **Gary's voice.** `src/gary_lines.json` (Gemini, read by a person): edit a line there, or run `scout/gary_lines.py` again and read the result.
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
- The page says "Private" about the check-ins only when they are behind a
  passphrase. If the server sets `GARY_PRIVATE_KEY`, the wellness view in
  Settings asks for it once per device and shows nothing until it is right,
  and a visitor without it is never shown the check-in pop-up. If the server
  sets none, the view says "Not locked". The passphrase is sent only with the
  two private calls (`services/live.js`), never with Gary's shared ones.
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
