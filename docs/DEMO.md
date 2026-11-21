# The three-minute demo

Issue #36. Eight beats, who does what, what to press, and what to do if a beat
fails. Rehearse it twice on the real device before the freeze (issue #38).

**About the eight beats.** The concept breakdown's own list of beats is not in
this repo, so these eight were written from the features. If the breakdown's
beats differ, swap them in and keep the timings.

**How this was checked.** Every "the screen shows" below is replayed against
the real backend by `python3 scripts/demo.py replay`, with pretend sniffs
standing in for Gary, and `sh scripts/check_all.sh` fails if the numbers here
stop matching the backend. It has not been rehearsed on the device, and nobody
has timed it out loud.

## Who does what

| Role | Does |
| --- | --- |
| **Talker** | Says the words. Never touches anything |
| **Holder** | Holds Gary, points the camera, presses the button |
| **Driver** | Drives the laptop that shows the web page |
| **Friend** | Steps into Gary's frame for beat 5. Watches the clock and gives a hand signal at 2:30 |

Write your names here before the first rehearsal:
Talker: ____ Holder: ____ Driver: ____ Friend: ____

## Ten minutes before

Do these in order. Each one matters to a beat.

```
# 1. Forget the rehearsal and put the scout's quests back. It asks before it forgets anything.
#    (If the server sets them, export GARY_ADMIN_KEY and SCOUT_KEY first.)
python3 scripts/demo.py reset --api http://<server>

# 2. On the Pi: a clean Gary.
sh start_gary.sh --fresh
```

3. **Driver:** open the page and tap **You**. If it asks for the passphrase,
   type it once (it is `GARY_PRIVATE_KEY` on the server; the laptop remembers
   it). Under "Before you head out" tap how you feel right now. Any number
   works: the page has a sentence for better, the same and worse. For the
   "better" sentence the first tap has to leave room to go up. Then go back to
   the **Gary** tab.
4. Check everything at once:

   ```
   export GARY_PRIVATE_KEY=<the passphrase>      # so that it can see the "before" check-in
   python3 scripts/demo.py check --api http://<server> --video <the backup video>
   python3 scripts/demo.py check --api http://<server> --device      # on the Pi
   ```

   It must end with **READY**. Read each WARN: it tells you which line of this
   script to change.
5. Do not press Gary's button until beat 4. Gary must still be napping at beat 1.

No live scout run yet? `python3 scripts/demo.py reset --samples --api http://<server>`
loads hand-written places instead. The page labels them as samples, and beats
2 and 3 change (see below).

On the table:

- A **water bottle** and a **backpack**, within reach. These are the two table quests.
- The page on the big screen, on the **Gary** tab. The status at the top says **Live**.
- A second browser tab with `scout/EVIDENCE.md` on GitHub.
- A third tab with the demo story, served from the Driver's own laptop so that
  it works when the server does not: `python3 -m http.server 8080 -d web/dist`,
  then open `http://localhost:8080/?mock`. (Build the page once first:
  `cd web && npm install && npm run build`.)
- The backup video, ready to play, with the laptop's volume up.

On the server, leave `GARY_NAP_SECONDS` unset. With a short nap, Gary is asleep
again before beat 8.

**To learn the words with no device:** `python3 scripts/demo.py replay --api http://localhost:8000`
plays these beats with pretend sniffs, one Enter at a time, on a backend on
your own laptop.

## What must be true before you say it

| Before you say | Check |
| --- | --- |
| "a web agent read these pages this morning" (beat 2) | `scout/EVIDENCE.md` lists completed runs from today. If it says no live runs are recorded, use the other beat 2 line below |
| "running on QNX" (beat 4) | Gary on the table is the QNX build: `sh start_gary.sh status`, then `ls qnx/build/gary`. If it is the Python version on Raspberry Pi OS, say "running on the device" |
| any QNX number (questions) | `docs/qnx-numbers.md` has rows measured on the Pi |
| "this page is locked with a passphrase" (beat 7) | The You tab says "Private. This page opens only with your passphrase." If it says "This page is not locked", set `GARY_PRIVATE_KEY` on the server, or use the other beat 7 line below |

## The script

| # | Time | Talker says | Holder and Driver do | The screen shows |
| --- | --- | --- | --- | --- |
| 1 | 0:00 | "Other apps count your steps. Gary counts your stories. This is Gary. He is asleep, and that is fine: miss a day and nothing happens." | Holder lifts Gary. Driver is on the Gary tab | Gary napping. "Zzz. Gary is napping. No guilt. He was tired anyway." |
| 2 | 0:20 | "Every morning a scout goes out for him. It is a TinyFish web agent that reads live London pages: city parks, trails, the events calendar. These are this morning's runs." | Driver flips to the EVIDENCE tab for five seconds, then back | The run table: the pages, the run ids, the quests made |
| 3 | 0:40 | "You only choose one thing: short or long." | Driver taps **Short** | The quest sign changes to a quest the scout found, with a line about where it is safe to stand. Under it: "Found by the scout on london.ca" (or the site that quest came from) |
| 4 | 0:55 | "That park is a walk from here, so we put two quests on this table. Now the Sniff Test. One button. A model on the device, running on QNX, names what the camera sees. No photo leaves the device, only the word." | Holder points at the **bottle**, holds still for a second, presses the button | Buzzer: three rising beeps. On the page Gary wakes up, the bottle is at the top of the journal with Gary's line and **+20 XP**. Driver points at "named on the device in N ms" |
| 5 | 1:25 | "Gary likes company. When a friend is in the frame it is Herd Mode: it counts double, and our herd climbs the Herd Cup. Herds compete. People are never ranked." | Friend steps beside the **backpack**. Holder points at both, presses | Buzzer: three rising beeps, then a double chirp. **+40 XP**. Gary grows from a Kid into a Scrambler. Driver taps **Herd**: "Your herd" has moved from 5th to 3rd |
| 6 | 1:55 | "Every quest is a place. Finish one and its fog lifts." | Driver taps **Map**, then taps an uncovered tile | Two places uncovered. The tile says what was found there and when |
| 7 | 2:15 | "And one private thing. Before we started, I tapped how I felt. Now I tap again. This page is locked with a passphrase, and none of it ever shows up in Gary's world or the herd. It reports what I said. It never claims the walk caused it." | Driver taps **You**. The card says "Now that you are back". Driver taps a number | "Noted", and under it the sentence, for example "You reported feeling better after your outing." |
| 8 | 2:40 | "Pokémon GO got people walking, and the gain was gone in six weeks. Walking with others lasts. That is what Gary rewards. A little adventure goes a long way." | Holder sets Gary down facing the judges. Driver back on the Gary tab | Gary, awake, a Scrambler |

End by 3:00. If the Friend signals 2:30 and you are not on beat 7, skip beat 6.

**Beats 2 and 3 with no live run recorded.** Say: "A scout fills his quest
list. It is built on a TinyFish web agent that reads London's park, trail and
event pages. We have not had a live run yet, so today's quests are places we
wrote in by hand." Show `scout/sources.json` instead of the evidence page. At
beat 3 the sign will read "A sample quest, written by hand. The scout did not
find this one." That is correct. Leave it.

**Beat 7 when the page is not locked.** Say "none of this ever shows up in
Gary's world or the herd" and leave out the passphrase. Do not say "private"
or "only I see this": on a server with no passphrase, anyone who has the
address can open that page, and the page says so itself.

**Why beat 5 has to follow beat 4.** Gary becomes a Scrambler at 60 XP. The
bottle quest gives 20 and the backpack quest with a friend gives 40. If either
quest does not complete, Gary stays a Kid at beat 5. Say what happened and
move on: the Herd screen still shows the herd find.

## Lines for the questions that will come

- **"How do you know I am really at Harris Park?"** "We do not. Gary has no
  GPS. The Sniff Test proves the thing, not the place. The quest says where,
  and we take your word for it."
- **"Is the Herd Cup real?"** "Our score is real. The rival herds are demo
  data, and the page says so."
- **"Is the mood data private?"** "It never appears in anything shared, each
  check-in can be skipped, and the page is behind a passphrase. There are no
  accounts yet: one Gary, one passphrase." (Only if the You tab says
  "Private". Otherwise: "It never appears in anything shared. The page has no
  lock on this server yet.")
- **"Why QNX?"** "The button has to answer at once, every time, on a battery.
  With every core busy, Gary at priority 20 answered in N ms." (Read the number
  from `docs/qnx-numbers.md`. If the table is empty, do not quote a number.)
- **"What can it recognise?"** "79 everyday things. A bench, a dog, a bicycle.
  Not a mushroom, yet."
- **"Did the table quests come from the scout?"** "No. Those two are ours, for
  this room. The park, trail and event quests are the scout's."

## If a beat fails

| What went wrong | Do this, and keep talking |
| --- | --- |
| Gary names nothing (one long low buzz) | Hold still, closer, more light, press again. A miss costs nothing, so say so: "He missed. No penalty. Again." |
| Gary names the wrong thing | It lands in the journal as a find and no quest completes. Say what he saw, and try once more |
| The find does not reach the page | Driver runs `python3 device/fake_sniff.py bottle --api http://<server>` (and `backpack --friend` for beat 5). Say: "The device is offline, so I am sending the same event by hand" |
| The backend is unreachable (the status says Offline) | Driver switches to the demo story tab (the one served from the laptop) and presses **Next**. Say: "This is the same page playing states our backend recorded earlier" |
| TinyFish is slow or down | Do not run it live. The quests on screen are from this morning's run, and the evidence page shows it |
| Gary will not start | Play the backup video |
| The buzzer is silent | Ignore it. The page is the proof |

Never pretend. If you switch to mock mode, the hand-sent event or the video,
say so in one sentence.

## The backup video (by Sun 6 am)

Record it on the real device, in one take if you can, 3 minutes at most.

1. Wide shot: the four of you, Gary on the table. Five seconds.
2. Over the Holder's shoulder: the bottle, the press, the buzzer. Keep the page
   visible in the same shot, so the find is seen arriving.
3. The Friend steps in. The backpack. The page: Gary grows, the herd moves up.
4. Screen capture: the evidence page, then the map, then the You tab.
5. Close on Gary.

Put the file on two laptops and in the Devpost page (issues #39 and #40).
