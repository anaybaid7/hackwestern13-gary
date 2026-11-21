# Runbook: from now to the submission

> **Partly out of date since the Pocket Pixel redesign (pull request #48).**
> Where this page names a tab or a tap ("the You tab"), it means the old
> layout: the private view is now in Settings. The order of the work, the
> commands and the fallbacks still hold. To be updated once the page is final.

Issues #38 (freeze and rehearsal), #39 (fallbacks) and #40 (submit).
Hacking ends **Sun 22 Nov, 9:00 am**.

The code for Phases 1 to 5 is merged. What is left needs people: accounts,
keys, the Pi, the camera, and four voices. This page puts that work in order.

**How this page was checked.** Every command was run on a Linux laptop against
a throwaway backend, except the ones marked *not run here*: those need the Pi,
Vultr, Tiger Data or a TinyFish key, and nobody has run them yet.

## 1. The order, with the plan's checkpoints

| By | What | Issues | Proof that it is done |
| --- | --- | --- | --- |
| **Now** (it was due Sat 3 am) | Gary's C++ program builds and names an object on the Pi, on QNX | #4 | On the Pi, `./qnx/build/gary --image test/pets.jpg` names two dogs (`device/README.md`, section 4) |
| **Sat 12 noon** | Real device, to a backend on Vultr, to the web page | #22, #9 | `python3 scripts/demo.py check --api http://<ip>` says READY |
| **Sat 6 pm** | The scout has read live sites. The button works. Tiger Data is in use | #8, #31, #33, #10, #11, #16 | `scout/EVIDENCE.md` lists runs. `check_db.py` prints "events is a hypertable on ts: yes" |
| **Sat 6 pm** | The TinyFish post is drafted. The QNX numbers are measured | #34, #14 | `docs/qnx-numbers.md` has rows |
| **Sat 10 pm** | **Feature freeze.** First full rehearsal on the real device | #38 | A time under 3:00, and a list of glitches |
| **Sun 6 am** | Devpost text, backup video, the TinyFish post | #35, #36, #34 | The video is on two laptops |
| **Sun 8:30 am** | Submit | #40 | The Devpost page is public |

**If #4 does not work by Saturday afternoon**, go to the QNX booth before
anything else, and prepare the spare SD card (section 5, row 4) in parallel.
Everything else in the demo works with the Python version of Gary. Only the
words "on QNX" depend on #4.

## 2. Bring the real system up

Do it in this order. Each step has its own page with the details.

**1. Tiger Data** (#16, `backend/README.md`). *Not run here.*

```
# put DATABASE_URL=... in backend/.env, then:
cd backend && python3 check_db.py
```

It must print `events is a hypertable on ts: yes` and
`time_bucket query for outdoor minutes per day: ok`. If it prints `NO`, the
API still works on that database, but the Tiger Data paragraph in the Devpost
page is not true yet. Paste the output into #16.

**2. Vultr** (#22, `backend/README.md`). *Not run here.*

```
sh backend/deploy/deploy.sh root@<ip>
ssh root@<ip>
nano /opt/gary/.env          # DATABASE_URL, SCOUT_KEY, GARY_ADMIN_KEY, GARY_PRIVATE_KEY. Leave GARY_NAP_SECONDS out
systemctl restart gary
```

Set all three keys. The address is public: without them anyone who finds it
can wipe Gary, post quests while the judges watch, or read the check-ins.
`GARY_PRIVATE_KEY` is a passphrase a person types into the You tab once, so
make it something you can say out loud to a teammate.

**3. The scout** (#8, #31, #33, `scout/README.md`). *Not run here.*

```
export TINYFISH_API_KEY=...            # and SCOUT_KEY, the same value as on the server
python3 scout/scout.py --one --dry-run # the first live run ever. If it fails, paste the output into #8
python3 scout/scout.py --api http://<ip>
python3 scout/scout.py --report
git add scout/runs.jsonl scout/EVIDENCE.md scout/cached_quests.json && git commit -m "Scout: live runs" && git push
```

Run it again on Sunday morning, so that "this morning's runs" is true.

**4. Gary** (#4, #10, #11, #13, `device/README.md`). *Not run here.*

```
cd device
cp gary.env.example gary.env           # set GARY_API=http://<ip>
sh start_gary.sh
sh start_gary.sh status
```

**5. Check it all.**

```
python3 scripts/demo.py check --api http://<ip>            # from a laptop
sh start_gary.sh status                                    # on the Pi: Gary, the button and buzzer, and sync are up
```

On the Pi you can also copy `scripts/demo.py` next to `start_gary.sh` and run
`python3 demo.py check --api http://<ip> --device`: it adds whether the journal
is empty and whether this Gary is the QNX build.

`check` changes nothing. FAIL means fix it. WARN means it changes what you may
say: each one names the line.

## 3. The freeze and the rehearsals (#38)

At **Sat 10 pm**: no new features. From then on, only fixes for things that
break the demo.

1. **Learn the words first, with no device.** On a laptop:

   ```
   cd web && npm install && npm run build               # once, so that the backend can serve the page
   cd backend && uvicorn app:app --port 8000            # one terminal
   python3 scripts/demo.py replay --samples --api http://localhost:8000    # another. Enter starts each beat
   ```

   Open http://localhost:8000 beside it and say the lines of `docs/DEMO.md`
   out loud: say the line, then press Enter, and watch the page do it.
2. **Rehearsal 1, on the real device**, against the deployed backend, with a
   stopwatch. Follow "Ten minutes before" in `docs/DEMO.md` exactly, then the
   eight beats.
3. Write every glitch down as a GitHub issue. Fix only what breaks the demo.
4. **Rehearsal 2**, after the fixes.

| | Time | Who held Gary | What went wrong |
| --- | --- | --- | --- |
| Rehearsal 1 | | | |
| Rehearsal 2 | | | |

## 4. Ten minutes before the judges

`docs/DEMO.md`, section "Ten minutes before". In short:

```
export GARY_ADMIN_KEY=... SCOUT_KEY=... GARY_PRIVATE_KEY=...   # the values on the server
python3 scripts/demo.py reset --api http://<ip>      # asks first, then forgets the rehearsal
# on the Pi:  sh start_gary.sh --fresh
# the Driver taps a "before" number on the You tab
python3 scripts/demo.py check --api http://<ip> --video <the backup video>
```

## 5. Fallbacks (#39)

Do each drill once on Saturday, so that the first time is not in front of a judge.

| # | If this fails | Do this | How it was checked here | The drill |
| --- | --- | --- | --- | --- |
| 1 | TinyFish is slow or down | `python3 scout/scout.py --cached --api http://<ip>` posts the quests of the last live run. `demo.py reset` does it for you | Tested against a stand-in for TinyFish | After the first live run, run the command once |
| 2 | The Pi loses the network | Nothing: Gary writes each sniff to his journal first and `sync.py` uploads it when the network is back. On stage, the Driver sends the same event by hand, `python3 device/fake_sniff.py bottle --api http://<ip>`, and says so | Tested: sniffs made with no network arrive later, once each | Turn the hotspot off, press the button twice, turn it on, watch both arrive |
| 3 | The backend or the server is down | The demo story, served from the Driver's laptop: `python3 -m http.server 8080 -d web/dist`, then `http://localhost:8080/?mock` | Opened in headless Chrome with no backend at all: the story plays | Build the page (`cd web && npm install && npm run build`), start it, press **Next** ten times |
| 4 | Gary will not run on QNX | A second SD card with Raspberry Pi OS and the Python version (`device/README.md`, section 9). Then say "on the device", not "on QNX" | The Python version is tested on Linux, on photos and a video. *Not run on a Pi* | Make the card on Saturday. Boot it, sniff once |
| 5 | Vultr is unreachable from the venue | Run the backend on the Driver's laptop: `cd backend && uvicorn app:app --host 0.0.0.0 --port 8000`, set `GARY_API=http://<laptop's address>:8000` in `device/gary.env`, and put the laptop and the Pi on one phone hotspot | The backend and the page are tested on a laptop | Do it once, end to end |
| 6 | Everything | The backup video | | Copy it to two laptops and play it once on each |

Never pretend. If you fall back, say so in one sentence.

## 6. Submit (#40), by Sun 8:30 am

- [ ] **Devpost text.** `docs/DEVPOST.md`: tick the claims table at its top
  (`[A]` to `[G]`), change any sentence whose claim is not true, fill in every
  square bracket, and say how the team used AI coding tools.
- [ ] **Tracks.** Enter a track only if its claim is true (table below).
- [ ] **The video.** Recorded on the real device. `docs/DEMO.md` has the shots.
- [ ] **The TinyFish post.** `docs/TINYFISH_POST.md`. Its link goes in the Devpost page.
- [ ] **The repo link.** The repo is private: see "Before the repo goes public" below.
- [ ] **The README.** Fill in the links at the top of `README.md`.
- [ ] Press submit before 8:30. Then stop pushing.

**Which tracks to enter**

| Track | Enter it only if |
| --- | --- |
| Best Health Hack (Sun Life) | always |
| Most Adventurous | always |
| QNX | Gary ran on QNX on the Pi (#4) |
| TinyFish | `scout/EVIDENCE.md` lists completed runs, and the post is up (#34) |
| Tiger Data | `check_db.py` printed "events is a hypertable on ts: yes" (#16) |
| Vultr | the demo ran on the Vultr address (#22) |
| Gemini | `--voice` wrote the quest titles that were on screen (#37) |
| Auth0 | not built (#23). Do not enter it |

**Before the repo goes public**

```
sh scripts/check_secrets.sh
```

It searches every commit on every branch for keys and passwords, and prints
where it found one, never the value. If it finds one, change that key at its
source (TinyFish, Google, Tiger Data) first: a key in an old commit stays
readable after the file is deleted. If the team would rather keep the repo
private, invite the judges to it instead and say so on the Devpost page.

## 7. Two decisions that are waiting for the team

- **#12** The mood tap and the short or long choice are on the web page, not on
  a knob on the device: the Grove knob is analog and the Pi has no analog
  input. Say yes to that, or wire a Grove Base HAT.
- **#24** The web page was built fresh, because the React prototype's code was
  never in the repo. Keep these screens, or port the prototype in.

## 8. What nobody has run yet

- Anything on the Pi or on QNX: the C++ build, the camera, the button, the
  buzzer, `start_gary.sh`, the power-on line.
- A live TinyFish run. A call to Gemini.
- The hypertable and `time_bucket` on Tiger Data. The deploy script on Vultr.
- The page on a real phone.
- The demo, out loud, with a stopwatch.

Each of these has an issue. When one is done, write what happened in it.
