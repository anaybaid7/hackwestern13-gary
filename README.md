# hackwestern13-gary
A pocket mountain goat on a QNX handheld that only grows when you go outside, discover new places &amp; bring a friend. :)

## Start here

- **[CONTEXT.md](CONTEXT.md)**: what is built, what is not, how to run it, and the rules for changing it. Coding agents read this first.
- **[docs/PLAN.md](docs/PLAN.md)**: the plan and the phases. Tasks are in the issue tracker, grouped by milestone.

| Folder | What |
| --- | --- |
| [`device/`](device/README.md) | Gary himself: camera, on-device model, the Sniff Test. C++ for QNX, Python for laptops |
| [`backend/`](backend/README.md) | The API and every rule: XP, stages, the map, the herd |
| [`web/`](web/README.md) | The page that draws Gary's world |
| [`scout/`](scout/README.md) | The TinyFish agent that turns live local pages into quests |
| [`contract/`](contract/README.md) | The JSON shapes the four share |

## Try it in two minutes, with no hardware

```
cd backend && pip install -r requirements.txt && uvicorn app:app --port 8000     # terminal 1
cd web && npm install && VITE_API_URL=http://localhost:8000 npm run dev          # terminal 2
python3 device/fake_sniff.py backpack --friend                                    # terminal 3: watch the page
```
