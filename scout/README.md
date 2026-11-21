# Scout

Gary's scout is the TinyFish part. A web agent reads live local pages and comes
back with real places. `scout.py` turns each place into a quest that Gary can
confirm with a Sniff Test, and posts the quests to the backend.

## Run it

```
export TINYFISH_API_KEY=...                 # free student credits: tinyfish.ai/students
python3 scout/scout.py --dry-run            # live run on the first source, print the quests
python3 scout/scout.py                      # live run, then send the quests to the backend
python3 scout/scout.py --all                # every source in sources.json
python3 scout/scout.py --api http://my-server:8000
```

No key yet? Build quests from a saved reply. This is also the fallback if
TinyFish is slow during judging:

```
python3 scout/scout.py --from-file scout/sample_result.json --dry-run
python3 scout/scout.py --from-file scout/sample_result.json        # sends them to the backend
```

Nothing to install: standard library only. Keep the key in your shell or a
local `.env`. Never commit it.

## What a run does

1. Calls TinyFish with a page address and a plain-English goal from `sources.json`.
2. Prints what the agent is doing, including a link to watch it live.
3. Takes the places it returns and builds one quest per place:
   a real place, `short` or `long`, and a thing to find there.
4. Records the run in `scout/runs.jsonl`: run id, page, live-view link, quests.
   **Commit that file.** It is your evidence for the judges that the agent
   worked on live sites.

## The one rule

The thing to find (`target`) must be something Gary can recognise outdoors: a
name marked `"outdoor": true` in `contract/labels.json`. The backend refuses
anything else. `TARGET_RULES` in `scout.py` picks the target from words in the
place's name and description.

## Test it

```
python3 scout/tests/test_scout.py       # no key, no network
```

## Status

- **Tested:** reading the event stream, building quests, every command-line
  path, and a real call to TinyFish with a wrong key (it answers `401` cleanly).
- **Not tested:** a successful live run. That needs your key. If the agent's
  reply has a different shape than `{"places": [...]}`, `find_places()` is the
  place to look.

## Next (Phase 5)

More sources (#31), stricter checks and safe wording (#32), the evidence page
(#33), the required TinyFish post (#34).
