# Backend

A small API in front of `rules.py`. Phase 1 keeps everything in memory, so a
restart starts fresh. The shapes are in [`../contract`](../contract/README.md).

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
scout and no device are needed.

## Try it with curl

```
# what the web page draws
curl -s localhost:8000/api/state

# a sniff arrives (the contract's example: a bench, with a friend, at Harris Park)
curl -s -X POST localhost:8000/api/events -H 'Content-Type: application/json' \
     -d @../contract/examples/event.discovery.json

# open quests, all of them or by length
curl -s localhost:8000/api/quests
curl -s 'localhost:8000/api/quests?time=short'

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

## Test it

```
cd backend && pytest
```

## Files

| File | What it holds |
| --- | --- |
| `rules.py` | Every rule: XP, stages, naps, the map, the herd. Pure functions, no HTTP |
| `app.py` | The endpoints and the in-memory `Store` |
| `tests/` | The API checked against the contract's example files |

## Settings

| Variable | Effect |
| --- | --- |
| `GARY_NAP_SECONDS` | How long before Gary naps. Default 8 hours. Use `60` for a demo |
| `SCOUT_KEY` | If set, `POST /api/quests` needs a matching `X-Scout-Key` header |
| `GARY_SEED` | A different seed quests file |

If `web/dist` exists (`cd web && npm run build`), this server also serves the
web page at `/`, so one address carries both.

## What Phase 3 changes

Storage moves to Postgres on Tiger Data (#16). The rules get deeper (#17, #18,
#19). Mood gets a real private store (#20). The short or long choice picks the
active quest (#21). Deploy on Vultr (#22).
