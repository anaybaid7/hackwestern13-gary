# Devpost page

Issue #35. Paste everything under "The page" into Devpost.

Before you paste:

- Fill in the one bracketed line in "How we built it" (how the team split the
  work, and what Hack Western asks you to disclose about AI coding tools).
- The Vultr server still keeps its data in memory. Tiger Data is verified
  (`python3 backend/check_db.py`) but not yet wired into that server. If that
  is still true, change the Tiger Data sentence to say so.
- QNX timings under CPU load are left out: those runs are not done (#14).
  Add them only from rows measured in `docs/qnx-numbers.md`.
- The three studies cited were opened and checked. Check any you add.

---

# The page

## Inspiration

Getting people moving for a week is easy. Keeping them moving is the hard part. When Pokémon GO came out, players walked 955 more steps a day in their first week, and by week six the gain was gone ([Howe et al., BMJ 2016](https://doi.org/10.1136/bmj.i6270)).

Two things do seem to last. One is walking with other people: a review of 42 studies of outdoor walking groups found better blood pressure, body fat and depression scores, with about 75% of people sticking with it ([Hanson and Jones, BJSM 2015](https://bjsm.bmj.com/content/49/11/710)). The other is a little friendly competition. In a trial of 602 adults, the group that competed moved the most, and only they were still ahead three months after the game ended ([Patel et al., JAMA Internal Medicine 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6735420)).

So we built something that rewards what lasts: small discoveries, outdoors, with someone else. We left out the parts that punish, like streaks you can lose, guilt, and being ranked below your friends. That became G.A.R.Y.: **Go Anywhere, Rediscover Yourself.** He's a pocket mountain goat who only grows when you go outside.

## What it does

Gary is a small device with a camera and one button, plus a web app that works as his handheld.

1. **A scout finds real quests.** Every morning a TinyFish web agent reads live London, Ontario pages: city parks, Tourism London trails and events, and Upper Thames conservation areas. It comes back with real places, and each one becomes a quest, like "See if a duck is lingering near Sifton Bog Trail today."
2. **You pick short or long.** Short means the nearest open quest within 5.2 km of you, so it never takes a big effort. Long is a trail walk.
3. **You have to actually go there.** The page checks in the browser whether you're within 1 km of the quest's place. Your position never leaves your phone; the server only hears "visited quest X".
4. **The Sniff Test.** Point Gary at something and press his button. A model running on the device, under QNX, names what the camera sees, and a buzzer tells you how it went. No photo is ever stored or sent, only the word.
5. **Gary reacts and grows.** The find goes into his journal with a line in his voice. The quest's place clears from the fog-of-war map, his field guide fills in, and he earns XP, growing from Kid to Scrambler, Ibex and finally Summit Elder.
6. **Talk to him.** Say "Go Gary, what am I looking at?" and he answers out loud with what his camera sees and a fact about it. He can also tell you how far you are from his next stage, or pick and make quests for you. It's hands free, in the browser.
7. **Herd Mode.** With a friend in the frame, a sniff counts double, co-op quests complete, and your herd climbs the weekly Herd Cup. Herds compete; people are never ranked.
8. **A private check-in.** Before and after a walk, you can tap how you feel from 1 to 5. Only you see it, and it never shows up in anything shared. The app tells you what you reported ("You reported feeling better after 2 of 3 outings") and never claims the walk caused it.

Gary never punishes. There are no streaks. After a quiet spell he naps, and your first sniff back earns a welcome-back bonus.

## How we built it

- **Device.**
  - Hardware: a Raspberry Pi 5 running QNX 8.0, a Logitech C270 webcam, and a Grove button and buzzer.
  - Vision: a C++ program using QNX's camera library, OpenCV and TensorFlow Lite. It runs two models on every frame: an SSD MobileNet detector for everyday things and people, and a YOLOv8s model trained on Open Images for nature (trees, flowers, squirrels, ducks, geese). Together they know 90 things.
  - Speed: both models together take 285 ms a frame, and the camera never stops, so a button press gets its answer in about 170 ms.
  - Reliability: every sniff is written to disk before Gary reacts, so pulling the power loses nothing. Sniffs made with no network upload later.
- **Backend.** Python and FastAPI. The device only reports facts: what, when, friend or not. Every rule (XP, stages, naps, the map, the herd, the quest range) lives in one file of pure functions with tests. Events live in a hypertable on Tiger Data, and "minutes outdoors per day" is a single `time_bucket` query. It's deployed on Vultr, and it also runs on the Pi itself.
- **Web.** React and Vite, styled as a pixel-art handheld. The page draws what the backend says and makes only one decision itself, for privacy: whether you're at the quest's place.
- **Scout.** A TinyFish agent runs on each source page, then every quest passes four checks:
  - Gary can name the target.
  - One quest per place.
  - Nothing closed or risky.
  - A note on where it's safe to stand.

  OpenStreetMap gives each place real coordinates. The scout runs on the Pi on a daily schedule, and there's a hidden control to rerun it.
- **Voice.** The browser hears "Go Gary" itself, offline, with Vosk, so nothing leaves the page until you call him. Then only your question goes to the server, which answers with Gemini, which gets only Gary's labels (never an image) and the app's state. ElevenLabs speaks the answer. The keys never reach the browser, and nothing said is stored.
- **Auth0** sign-in is built and optional, including pairing a device through Auth0's device flow.

The four parts (device, backend, web, scout) share only a small written contract of JSON shapes, so each was built and tested on its own.

[How the team split the work. Much of the code was written with Claude Code from the team's plan; check what Hack Western asks you to disclose and say it here.]

## Challenges we ran into

- **The webcam mic doesn't work on QNX.** QNX's sound service sees the C270's microphone but refuses it, because the device doesn't support a transfer mode QNX requires. The Pi has no speaker either. So we moved Gary's voice to the browser: the phone does the listening and speaking, and the Pi does the seeing.
- **A Pi with no network doesn't know the time.** A fresh sniff could look a year old and put Gary to sleep. The device now tells the backend what its clock reads, and the backend corrects the timestamps.
- **Gary kept hearing himself.** His own voice clips would set him off. The mic now ignores the room while he speaks, and the speech model is told never to invent the wake word.
- **A loud hackathon hall ate our AI quota.** At first every sound went to Gemini to check for "Go Gary", which was slow, used up a day's quota in an hour, and woke Gary on words nobody said. Now the browser listens for the wake word itself with Vosk, an offline recognizer that may only choose from a dozen words, and Gemini hears only real questions.
- **Browsers only allow location and the microphone over HTTPS**, and the Pi is just a local address. We tunnel it through Cloudflare, so a phone gets a secure link.
- **Building on QNX**: newer FastAPI needs a library that won't compile there, so the backend on the Pi pins older versions.
- **Text from the open web ends up in our app.** The backend cleans every quest as it arrives, and only a real agent run gets shown as "Found by the scout".

## Accomplishments that we're proud of

- Real-time vision running on QNX on a Pi, answering a button press in about 170 ms, with two models running at once.
- Quests that are real places a web agent found that morning, with each run's TinyFish ID recorded as evidence.
- Proving you went somewhere without tracking you: the location check happens in your browser, and the server only learns a quest ID.
- A goat you can just talk to, with no button, from your phone.
- A health feature that never guilts, never diagnoses and never shares your mood.

## What we learned

- Writing the contract first meant four people could build four parts without waiting on each other.
- Privacy is easier to design in than to bolt on. Deciding early that photos and positions never leave the device shaped the whole architecture, for the better.
- Real hardware is never what the datasheet says: camera units that don't release, clocks that start in the wrong year, a mic the OS won't open. You leave room to adjust.

## What's next for Pocket Gary

- A speaker and mic Gary can use himself, so he can talk without a phone.
- Real herds, so the Herd Cup has real rivals instead of seeded ones.
- Accounts for everyone, so each person gets their own Gary and their own private page.
- A bigger vocabulary, so Gary can finally name a mushroom.
- More cities: the scout only needs a list of local pages.

## Built with

QNX, Raspberry Pi 5, C++, TensorFlow Lite, OpenCV, Python, FastAPI, PostgreSQL on Tiger Data, Vultr, React, Vite, TinyFish, Gemini, ElevenLabs, Auth0, OpenStreetMap, Cloudflare Tunnel.
