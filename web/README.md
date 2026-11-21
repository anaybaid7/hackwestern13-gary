# Web

One page that draws whatever the backend's `GET /api/state` returns, and asks
again every two seconds. Every number on it comes from the backend; the page
decides nothing. This is the Phase 1 bare-bones version. Phase 4 turns it into
Gary's world.

## Run it

```
cd web
npm install

npm run dev                                       # mock mode: no backend needed
VITE_API_URL=http://localhost:8000 npm run dev    # against the real backend
```

Mock mode draws `contract/examples/state.json`.

At run time you can also add `?api=http://host:8000` or `?mock` to the page
address. That is handy on a phone.

## Build it

```
npm run build
```

This writes `web/dist`. The backend serves that folder at `/`, so after a
build, `http://localhost:8000/` is the page and the API on one address.

## Test it

```
npm test
```

The tests render the page from the contract's example state.

## Files

| File | What it holds |
| --- | --- |
| `src/api.js` | The only file that talks to the backend. Mock mode lives here |
| `src/App.jsx` | The page: Gary, XP, quest, field guide, journal, map, Herd Cup |
| `src/Gary.jsx` | A placeholder SVG goat. Horns grow with the stage; he closes his eyes to nap |
| `src/styles.css` | Styles |
| `src/App.test.jsx` | Tests |

## What Phase 4 changes

Bring the React prototype in and point its mock-service interface at `api.js`
(#24). Real stage images and Gary's voice (#25). The map view (#26), the field
guide (#27), the quest card with the short or long choice (#28), the Herd Mode
screen and Herd Cup table (#29), the wellness view and private mood tap (#30).

Rules that hold on every screen: no guilt, no penalties, no individual
rankings, and mood is private.
