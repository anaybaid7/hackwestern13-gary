# Devpost page: draft

Issue #35. Paste the sections under "The page" into Devpost. Read "Before you
paste" first: several sentences are only true once an open issue is closed.

## Before you paste

Each line below is a claim the page makes. Tick it only when it is true. If one
is not true by Sunday morning, change the sentence it guards (they are marked
`[A]` to `[G]` in the text) to say what is real.

| | Claim | True when | Issue |
| --- | --- | --- | --- |
| `[A]` | The Sniff Test runs on QNX on the Pi | `gary_qnx.cpp` built and ran on the Pi | #4 |
| `[B]` | The QNX timings it quotes | `docs/qnx-numbers.md` has rows measured on the Pi | #14 |
| `[C]` | Quests come from live sites | `scout/EVIDENCE.md` lists completed runs. Say "five pages" only if five have one | #8, #31, #33 |
| `[D]` | Data is on Tiger Data | `python3 backend/check_db.py` prints "events is a hypertable on ts: yes" and "time_bucket query ...: ok" | #16 |
| `[E]` | It is deployed on Vultr | **True since Sat 21 Nov, 12:55 pm:** http://149.248.50.153 serves the page and the API | #22 |
| `[F]` | The button and buzzer | They work on the Pi's pins | #10, #11 |
| `[G]` | The wellness view is behind a passphrase | **True since Sat 21 Nov:** `GARY_PRIVATE_KEY` is set on the server, and the wellness view in Settings says "Locked" until the passphrase is typed | #22 |

Fill in, wherever the text has square brackets: the video link, the repo link,
the TinyFish post link, the Vultr address, the QNX version (`uname -r` on the
Pi), the numbers from `docs/qnx-numbers.md`, and the two sections about what
went wrong and what you learned.

**The health evidence.** The three studies cited were opened and checked while
writing this. If you add another (for example the 2019 Scientific Reports
study on 120 minutes a week in nature), open it and check the wording first.

**Say how the team used AI coding tools.** Much of the code in this repo was
written with Claude Code, from the team's plan. Check Hack Western's rules and
the Devpost form for what they ask you to disclose, and write it in "How we
built it". Do not leave it out.

---

# The page

## G.A.R.Y the Goat

**G.A.R.Y: Go Anywhere, Rediscover Yourself.**

**Other apps count your steps. Gary counts your stories.**

A pocket mountain goat who grows when you go outside, find things, and bring a
friend. Miss a day and nothing happens: Gary naps.

## Inspiration

Getting people moving for a week is easy. Keeping them moving is the hard
part. Pokémon GO is the best-known example: players walked 955 more steps a
day in their first week, and by the sixth week the gain could no longer be seen
([Howe et al., BMJ 2016](https://doi.org/10.1136/bmj.i6270)).

Two things do seem to last. People keep turning up when they walk with others:
a review of 42 studies of outdoor walking groups found that blood pressure,
body fat and depression scores all improved, and that adherence averaged 75%
where it was reported
([Hanson and Jones, British Journal of Sports Medicine 2015](https://bjsm.bmj.com/content/49/11/710)).
And a little friendly competition helps: in a trial of 602 adults, the group
that competed moved the most, and it was the only group still ahead of the
control group in the three months after the game ended
([Patel et al., JAMA Internal Medicine 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6735420)).
That trial's game also took points away for missed days. Gary does not.

So we built something that rewards what lasts: small discoveries, outdoors,
with someone else. And we left out the parts that punish: streaks to lose,
guilt, and being ranked below your friends.

## What it does

Gary is a small device with a camera and one button.

1. **A scout finds quests.** `[C]` Each morning a TinyFish web agent reads live
   London, Ontario pages (city parks, trails, the events calendar) and comes
   back with real places. Each becomes a quest: "Find a bench at Harris Park."
2. **You pick short or long.** That is the only choice. Gary takes the next
   quest on the scout's list.
3. **The Sniff Test.** Point Gary at something and press his button. `[A]` A
   model running on the device, under QNX, names what the camera sees, and the
   buzzer `[F]` tells you what happened. No photo is stored or sent: only the word.
4. **Gary reacts.** The find lands in his journal with a line in his voice
   ("A bench. I respect anything that holds still."). The quest's place loses
   its fog on the map, his field guide fills in, and he earns XP and grows.
5. **Herd Mode.** If a friend is in the frame, the sniff counts double, co-op
   quests complete, and your herd climbs the weekly Herd Cup. Herds compete.
   People are never ranked.
6. **A private check-in.** Before and after an outing you can tap how you
   feel, 1 to 5. `[G]` It sits behind a passphrase and never appears in
   Gary's world or the herd. The page reports what you said ("You reported feeling
   better after 2 of 3 outings") and never claims the walk caused it.

Gary never punishes. There are no streaks to lose. After a quiet spell he naps,
and the first sniff back earns a small welcome-back bonus.

## How we built it

```
 Pi 5 on QNX                              Vultr                            Browser
 ┌───────────────────────────┐          ┌────────────────────────┐      ┌───────────────────┐
 │ gary      camera → model   │ events   │ API + rules            │ state│ React + SVG Gary  │
 │   ▲ button                 │ ───────► │ XP, stages, fog, herd  │ ───► │ map, journal,     │
 │   ▼ journal                │ ◄─────── │ private mood store     │      │ quest, wellness   │
 │ sync      upload / fetch   │  quests  │ Postgres on Tiger Data │      └───────────────────┘
 │ gary_io   button, buzzer   │          └───────────▲────────────┘
 └───────────────────────────┘                       │ quests
                                          scout: a TinyFish agent on live sites
```

- **Device.** A Raspberry Pi 5 running QNX [version], a Logitech C270 webcam,
  a Grove button and buzzer. The vision program is C++: QNX's camera library
  (through the wrapper in QNX's open-source AI workshop), TensorFlow Lite, and
  an SSD MobileNet v2 detector that knows 79 everyday things. The camera and
  the model run all the time, so the answer is ready the moment the button is
  pressed. Every sniff is written to a journal on disk before Gary reacts, so
  pulling the power loses nothing, and sniffs made with no network are
  uploaded later.
- **Backend.** Python and FastAPI. The device only reports facts (what, when,
  friend or not); every rule lives in one file of pure functions with tests.
  `[D]` Events are a hypertable on Tiger Data, and the wellness view's outdoor
  minutes per day are one `time_bucket` query.
- **Web.** React. The page draws what the backend says and decides nothing.
  It also has a mock mode that plays a ten-step story the real backend wrote.
- **Scout.** A TinyFish agent per page, then four checks on every quest: Gary
  can name the thing, one quest per place, nothing closed or risky, and a line
  about where it is safe to stand.

The project is four folders (device, backend, web, scout) joined only by a
small written contract of JSON shapes, so each part is built and tested on its
own.

[How the team worked, and how AI coding tools were used.]

## What is real and what is demo data

Real:

- `[A]` The Sniff Test: a real model on the Pi under QNX, on a live camera.
- `[C]` The quests: read from live sites by a TinyFish agent. The run ids are in
  `scout/EVIDENCE.md`.
- XP, stages, the map, the journal, the field guide, Herd Mode and mood
  check-ins: all computed from real events by the backend.
- `[D]` `[E]` Storage on Tiger Data and hosting on Vultr.

Demo data, and labelled as such on the page:

- The rival herds in the Herd Cup. Your herd's score is real; theirs are seeded.
- The "sample week" in the wellness view, and everything in mock mode.
- The two table quests used on stage ("find a water bottle at your table").

Limits we know about:

- Gary recognises 79 things. A bench, a dog and a bicycle, yes. A mushroom, no.
- Gary has no GPS. The Sniff Test proves the thing, not the place: a quest's
  place is taken on trust.
- There is one Gary and there are no accounts. Mood never appears in anything
  shared, and `[G]` the wellness view in Settings is behind one passphrase,
  set on the server.
- "Minutes outdoors" is an estimate from sniffs, and the page says so.

## Tracks

**Best Health Hack (Sun Life).** Gary is built around two habits that are hard
to keep up: getting outdoors, and doing it with other people. The design
follows the evidence above: rewards go to quests, outdoor finds and finds with
a friend, never to raw counts, and nothing is ever taken away. The mood
check-in is kept out of everything shared, optional, and worded so it never
diagnoses.

**Most Adventurous.** The theme is "Discover the unknown". Gary's map starts
as fog and clears one real place at a time. `[C]` The quests are real corners
of London that a web agent found this morning.

**QNX.** `[A]` The Sniff Test runs on a Raspberry Pi 5 under QNX, built with
the camera wrapper and TensorFlow Lite recipe from QNX's open-source AI workshop.
Real-time matters here: the button has to answer at once, every time, on a
battery in someone's hand. `[B]` With every core busy, the button-to-answer
time at priority 20 stayed at [N] ms against [N] ms idle (`docs/qnx-numbers.md`).
The journal survives a pulled power cable.

**TinyFish.** `[C]` Our "AI employee" is a scout. Every morning it opens five
live pages, reads them like a person would, and files today's quests. Its job
is done start to finish: page, places, checks, quests in the game.
`scout/EVIDENCE.md` lists each run with its id. Our post: [link].

**Tiger Data.** `[D]` Every sniff is a row in a hypertable on `ts`. The
wellness view's "minutes outdoors per day" is a single `time_bucket` query
over it.

**Vultr.** `[E]` The API and the web page run on one Vultr instance in
Toronto, at http://149.248.50.153, set up by one script.

## Challenges we ran into

- [Fill in from the weekend. Candidates: building C++ on QNX itself; the camera;
  the Grove plugs not fitting the Pi's pins; the rotary knob being analog.]
- A Pi with no network does not know what time it is, so a fresh sniff can look
  hours old and Gary seems asleep. The device now tells the backend what its
  clock reads, and the backend corrects the timestamps.
- In a test that cuts the power in the middle of a journal line, the next
  sniff was glued onto the broken one and lost. Gary now ends a torn line when
  he starts.
- Text from the open web ends up on our page and in the device's quest file.
  The backend now cleans every quest as it arrives, and only a real agent run
  may be shown as "Found by the scout".

## What we learned

- [Fill in. One candidate, if it turned out true for the team: writing the
  contract first let each part be built without waiting for the others.]

## What's next

- A bigger vocabulary, so Gary can name a mushroom.
- Real herds, so the Herd Cup has real rivals.
- Accounts, so that each person has their own Gary and their own private page.

## Built with

QNX, Raspberry Pi 5, C++, TensorFlow Lite, OpenCV, Python, FastAPI,
PostgreSQL on Tiger Data, Vultr, React, Vite, TinyFish.

(Leave out any of these that did not end up in the demo. Add Gemini only if
`--voice` was used for the quests on screen.)
