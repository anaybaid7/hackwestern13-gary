# The three-minute demo

Issue #36. Eight beats, who does what, what to press, and what to do if a beat
fails. Rehearse it twice on the real device before the freeze (issue #38).

**About the eight beats.** The concept breakdown's own list of beats is not in
this repo, so these eight were written from the features. If the breakdown's
beats differ, swap them in and keep the timings.

**How this was checked.** Every "the screen shows" below was replayed against
the real backend with `device/fake_sniff.py` standing in for Gary. It has not
been rehearsed on the device, and nobody has timed it out loud.

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
# 1. Forget the rehearsal. (Add  -H "X-Admin-Key: <key>"  if the server sets GARY_ADMIN_KEY.)
curl -X POST http://<server>/api/dev/reset

# 2. Put the scout's quests back. The reset keeps only the three built-in quests.
#    (If the server sets SCOUT_KEY, export the same value first.)
python3 scout/scout.py --cached --api http://<server>
#    No live run yet? This posts hand-written places instead, and beat 2 changes (see below):
#    python3 scout/scout.py --from-file scout/sample_result.json --api http://<server>

# 3. On the Pi: a clean Gary.
sh start_gary.sh --fresh
sh start_gary.sh status        # Gary: up. button and buzzer: up. sync: up
```

4. **Driver:** open the page, tap **You**, and under "Before you head out" tap
   how you feel right now. Use 3 or lower, honestly if you can: beat 7 needs
   room to go up. Then go back to the **Gary** tab.
5. Do not press Gary's button until beat 4. Gary must still be napping at beat 1.

On the table:

- A **water bottle** and a **backpack**, within reach. These are the two table quests.
- The page on the big screen, on the **Gary** tab. The status at the top says **Live**.
- A second browser tab with `scout/EVIDENCE.md` on GitHub.
- A third tab with the page in mock mode (add `?mock` to the address). This is the fallback.
- The backup video, ready to play, with the laptop's volume up.

## What must be true before you say it

| Before you say | Check |
| --- | --- |
| "a web agent read these pages this morning" (beat 2) | `scout/EVIDENCE.md` lists completed runs from today. If it says no live runs are recorded, use the other beat 2 line below |
| "running on QNX" (beat 4) | Gary on the table is the QNX build: `sh start_gary.sh status`, then `ls qnx/build/gary`. If it is the Python version on Raspberry Pi OS, say "running on the device" |
| any QNX number (questions) | `docs/qnx-numbers.md` has rows measured on the Pi |

## The script

| # | Time | Talker says | Holder and Driver do | The screen shows |
| --- | --- | --- | --- | --- |
| 1 | 0:00 | "Other apps count your steps. Gary counts your stories. This is Gary. He is asleep, and that is fine: miss a day and nothing happens." | Holder lifts Gary. Driver is on the Gary tab | Gary napping. "Zzz. Gary is napping. No guilt. He was tired anyway." |
| 2 | 0:20 | "Every morning a scout goes out for him. It is a TinyFish web agent that reads live London pages: city parks, trails, the events calendar. These are this morning's runs." | Driver flips to the EVIDENCE tab for five seconds, then back | The run table: the pages, the run ids, the quests made |
| 3 | 0:40 | "You only choose one thing: short or long." | Driver taps **Short** | The quest sign changes to a quest the scout found, with a line about where it is safe to stand. Under it: "Found by the scout on london.ca" (or the site that quest came from) |
| 4 | 0:55 | "That park is a walk from here, so we put two quests on this table. Now the Sniff Test. One button. A model on the device, running on QNX, names what the camera sees. No photo leaves the device, only the word." | Holder points at the **bottle**, holds still for a second, presses the button | Buzzer: three rising beeps. On the page Gary wakes up, the bottle is at the top of the journal with Gary's line and **+20 XP**. Driver points at "named on the device in N ms" |
| 5 | 1:25 | "Gary likes company. When a friend is in the frame it is Herd Mode: it counts double, and our herd climbs the Herd Cup. Herds compete. People are never ranked." | Friend steps beside the **backpack**. Holder points at both, presses | Buzzer: three rising beeps, then a double chirp. **+40 XP**. Gary grows from a Kid into a Scrambler. Driver taps **Herd**: "Your herd" has moved from 5th to 3rd |
| 6 | 1:55 | "Every quest is a place. Finish one and its fog lifts." | Driver taps **Map**, then taps an uncovered tile | Two places uncovered. The tile says what was found there and when |
| 7 | 2:15 | "And one private thing. Before we started, I tapped how I felt. Now I tap again. Only I see this page. It reports what I said. It never claims the walk caused it." | Driver taps **You**. The card says "Now that you are back". Driver taps a number | "Noted", and under it the sentence, for example "You reported feeling better after your outing." |
| 8 | 2:40 | "Pokémon GO got people walking, and the gain was gone in six weeks. Walking with others lasts. That is what Gary rewards. A little adventure goes a long way." | Holder sets Gary down facing the judges. Driver back on the Gary tab | Gary, awake, a Scrambler |

End by 3:00. If the Friend signals 2:30 and you are not on beat 7, skip beat 6.

**Beats 2 and 3 with no live run recorded.** Say: "A scout fills his quest
list. It is built on a TinyFish web agent that reads London's park, trail and
event pages. We have not had a live run yet, so today's quests are places we
wrote in by hand." Show `scout/sources.json` instead of the evidence page. At
beat 3 the sign will read "A sample quest, written by hand. The scout did not
find this one." That is correct. Leave it.

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
- **"Is the mood data private?"** "It never appears in anything shared, and
  each check-in can be skipped. There is no login yet, so the page itself is
  not behind a password."
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
| The backend is unreachable (the status says Offline) | Driver switches to the mock-mode tab and presses **Next**. Say: "This is the same page playing states our backend recorded earlier" |
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
