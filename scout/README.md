# Scout

Gary's scout is the TinyFish part. A web agent reads live local pages and comes
back with real places. `scout.py` turns each place into a quest that Gary can
confirm with a Sniff Test, checks it, and posts the quests to the backend.

**No successful live run has been made yet.** There was no API key when this
was written. The whole path (the call, the event stream, the quests, the run
log, the evidence page) is tested against a stand-in for TinyFish that follows
their documents, and a real call with a wrong key got a clean `401`. A real
run may still differ from the documents. The first thing to do is the first
command below; if it fails, paste what it prints into issue #8.

## Run it

```
export TINYFISH_API_KEY=...                  # free student credits: tinyfish.ai/students

python3 scout/scout.py --one --dry-run       # 1. one live run on the first page. Prints quests, sends nothing
python3 scout/scout.py                       # 2. the day's quests: every page, then sent to the backend
python3 scout/scout.py --report              # 3. writes scout/EVIDENCE.md for the judges
git add scout/runs.jsonl scout/EVIDENCE.md scout/cached_quests.json && git commit -m "Scout: live runs"
```

Other ways to run it:

```
python3 scout/scout.py --source events       # only the pages whose name contains "events"
python3 scout/scout.py --api http://<server> # a backend somewhere else (or set GARY_API)
python3 scout/scout.py --max 2               # at most two quests per page
python3 scout/scout.py --wait 120            # give up on a page after 120 seconds (default 300)
```

A page that fails or takes too long is skipped, and the others still run. A
refused key stops the run at once.

If the server sets `SCOUT_KEY`, export the same value here and the scout sends it.

Nothing to install: standard library only. Keep keys in your shell or a local
`.env`. Never commit them.

## If TinyFish is slow, or there is no key

```
python3 scout/scout.py --cached              # posts the quests from the last live run. No agent run
python3 scout/scout.py --from-file scout/sample_result.json    # sample quests from hand-written places
```

`--cached` is the fallback for judging: the quests are real scout output, just
not from this minute. Every live run that makes quests rewrites
`scout/cached_quests.json`.

`--from-file` is for building with no key. Its quests are marked
`"source": "sample"`, and the web page says "A sample quest, written by hand.
The scout did not find this one." Only quests from a live run are marked
`tinyfish` and shown as "Found by the scout". Do not change that to make a
demo look better.

## The pages it reads (issue #31)

`sources.json`. Five live pages about London, Ontario:

| Kind | Page | Quests it makes |
| --- | --- | --- |
| parks | City of London: parks, `london.ca/parks-london` | short |
| trails | Tourism London: hiking trails, `londontourism.ca/best-of-london/hiking` | long |
| trails | Upper Thames River Conservation Authority: London's natural areas, `thamesriver.on.ca/.../londons-esas/` | long |
| events | City of London: events, `london.ca/events` | short |
| events | Tourism London: events this week, `londontourism.ca/events` | short |

The agent has not run on any of them yet. Two were re-read by hand on 21 Nov
to check that the goal fits the page: the parks page lists each park with its
address and features in the page's own text, and the hiking page names ten
trails with a photo caption each and no description. The other three were not
re-checked in that pass. On the first live run, read what comes back from each
page and adjust its goal if the answer is thin. To add a
page, add an entry with a `name`, a `kind`, a `url`, a `time` and a `goal`. The
goal is plain English and must ask for JSON in the form
`{"places": [{"name": ..., "about": ...}]}`. For an events page, ask for the
venue as the name.

## What a run does

1. Calls TinyFish with a page address and its goal.
2. Follows the agent's event stream. It prints each step, and a link to watch
   the agent's browser live.
3. Finds the list of places in the reply, whatever shape the agent chose.
4. Turns each place into a quest (below) and checks it.
5. Writes the run to `runs.jsonl`, saves the quests to `cached_quests.json`,
   and posts them to `POST /api/quests`.

## From a place to a quest

- **The thing to find** comes from the words about the place (`TARGET_RULES`):
  a dog park asks for a dog, a paved path for a bicycle, woods for a bird,
  gardens for a bench. With no clue it picks from bench, bird, dog and bicycle.
  The same place always gets the same thing. The rules only ask for things
  that are there in any season, so a quest can always be finished.
- **Short or long** comes from the page: parks and events are short (about 15
  minutes, 20 XP), trails are long (about 40 minutes, 40 XP).
- **Every third quest is for two**: it only completes with a friend in frame.
- **The id** is `q-<day>-<place>`, so running the scout twice in a day replaces
  the quests instead of piling them up.

## The checks (issue #32)

A place becomes a quest only if all of these hold. Anything left out is
printed with the reason, and recorded in `runs.jsonl`.

| Check | How |
| --- | --- |
| Gary can name the thing | The target must be an outdoor name in `contract/labels.json` **and** in the device's own `device/models/coco_labels.txt` |
| One quest per place | Across all pages in a run. "Kains Woods ESA" and "Kains Woods" are one place |
| Not closed, private or risky | `RISKS` in `scout.py`: closed, by permit only, no public access, construction, flooded, a quarry, a rail yard, a cancelled or sold-out event and so on |
| It says where to stand | Every quest carries a `note`: "Stay on the marked trail. Any safe, accessible spot counts." For an event: "...outside included. No ticket needed." The web page shows it on the quest card |
| Nothing odd from the page gets through | A name longer than 70 characters is not a place name and is left out. Only an `http` or `https` address is kept as the quest's link |

The backend checks the target again and refuses a quest Gary could not confirm.

## Evidence for the judges (issue #33)

`runs.jsonl` gets one line per live run: the time, the page, the TinyFish run
id, the link to the live view, what the agent said it was doing, the places it
read, the quests made, and what was left out and why.

`python3 scout/scout.py --report` turns that into [`EVIDENCE.md`](EVIDENCE.md),
a page you can show in 20 seconds. Commit both after each live session. The run
ids can also be looked up in the TinyFish dashboard.

## Stretch: Gary's voice from Gemini (issue #37)

```
export GEMINI_API_KEY=...        # a free key from Google AI Studio
python3 scout/scout.py --voice
```

Gemini rewords each quest's title the way Gary would say it. The quest itself
still comes from the scout: the place, the thing, the length and the note are
never touched. A rewording is kept only if it still names the place and the
thing, is short, keeps "friend" on a quest for two, and says nothing risky or
pushy (`gary_voice.py`). Otherwise the plain title stays.

**Not run against the real Gemini API**: there was no key. Model names change
often; if the default is refused, set `GEMINI_MODEL` to a current one from
ai.google.dev.

## Test it

```
python3 scout/tests/test_scout.py      # or: pytest scout
```

No key and no network needed. The tests run against saved replies in
`tests/replies/` (hand-written in the agent's shape, and they say so), and
against a stand-in for TinyFish on this machine that sends the documented
event stream: a run that works, one that fails, one that hangs up, one that
goes quiet, and a refused key.

## Files

| File | What it holds |
| --- | --- |
| `scout.py` | The TinyFish call, places to quests, the checks, the evidence page |
| `sources.json` | The pages and the goal for each |
| `gary_voice.py` | The optional Gemini step |
| `sample_result.json` | Hand-written places, for a run with no key |
| `runs.jsonl`, `EVIDENCE.md`, `cached_quests.json` | Written by live runs. Commit them |
| `tests/` | Tests and saved replies |

## TinyFish, in brief

`POST https://agent.tinyfish.ai/v1/automation/run-sse` with an `X-API-Key`
header and a JSON body of `url` and `goal`. The reply is a stream of events:
`STARTED`, `STREAMING_URL`, `PROGRESS`, then `COMPLETE` with a `result`.
`401` means a bad key, `402` and `403` mean no credits.

The track's rule: to qualify, the demo must be posted on X or LinkedIn with
TinyFish tagged. The draft is in [`../docs/TINYFISH_POST.md`](../docs/TINYFISH_POST.md).
