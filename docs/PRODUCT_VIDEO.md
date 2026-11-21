# Product video: "A day in the life with G.A.R.Y"

A short commercial (about 90 seconds) for Devpost and the judges. It is shot
point-of-view from the camera on the hat, like a GoPro. Whenever Gary speaks,
a small pixel Gary pops up in the top corner, bounces while he talks, and has
a caption underneath.

## The idea

You wake up, Gary asks how you are, you have work, so you're stuck at a grey
desk. Then you ask Gary to get you out, he finds a quest, and the rest of the
video is the walk: naming things, finds, the map clearing, Herd Mode, the
quest done and Gary levelling up.

The desk-to-outside contrast is the health pitch (Sun Life): cold and grey
inside, warm and bright once you're out the door.

## Rules for the video

- **Gary's audio is made in post.** Live audio from the hat outdoors will be
  windy and tinny. Record every Gary line cleanly and lay it over the footage.
  He can be more expressive than the device (timing, little reactions).
- **Same voice as the device.** Use the ElevenLabs voice the device uses
  (`device/make_voice.py`), so Gary at the judging table sounds like the Gary
  in the video.
- **What he *does* stays real.** He names what the camera sees, finds quests,
  clears the map, notices a friend, and levels up. The wording can be
  polished, but no features he does not have.
- **Product rules still hold** (`CONTEXT.md` section 8): the quest shown
  should come from a real TinyFish run; Herd Mode is "a friend is in frame",
  never naming who; mood stays a private check-in, and Gary never diagnoses;
  no streak or guilt wording.
- **Your lines are recorded in post too** (into a phone in a quiet room), so
  the dialogue is clean and only the background sound comes from the footage.
- **Leave a half-beat gap before Gary answers.** That pause makes him feel alive.

## Script

### 0. Cold open (0–4s)
- **Picture:** black. White text fades in: *a day in the life with G.A.R.Y*
- **Sound:** silence, then faint room tone fades up. A clock ticks once or
  twice. A muffled bird outside.

### 1. Wake up (4–20s)
- **Picture:** hat POV, fisheye. Eyes "open": fade from black, blur to sharp.
  Ceiling, morning light through the blinds. Head turns to the nightstand.
- **Sound:** phone alarm, cut off by a hand slap. Duvet rustle, yawn, bed
  creak, birds outside, a distant car.
- **Dialogue:**
  - You (groggy): "Mmm… what's up, Gary."
  - Gary *(stretch noise)*: "Mornin'! How're we feeling today?"
  - You: "…Peachy."
  - Gary: "Peachy! Love that. Okay, let me pull up today's quests. There's a
    trail, a market, oh, and a—"
  - You: "Whoa, slow down, Gary. I have work today."
  - Gary *(deflating)*: "…Oh. Right. Work." *(tiny goat bleat)*

### 2. Hard cut: the desk (20–30s)
- **Picture:** sudden cut to a colder, greyer grade. Desk, laptop glow, you
  hunched over, coffee mug. Two or three jump cuts: staring, rubbing eyes,
  scrolling.
- **Sound:** the cut slams the birds to silence. Keyboard clacking, fridge or
  HVAC hum, mouse clicks, a notification ping, a sigh, the mug set down.
  **No music.** The quiet is the point.

### 3. The ask (30–40s)
- **Picture:** you lean back and push the laptop shut. Insert: the web app's
  quest card loading (a live TinyFish quest).
- **Sound:** laptop lid clap, chair creak, UI blip as the quest card appears.
  **Music starts here:** a light, plucky beat.
- **Dialogue:**
  - You: "Okay. Gary, let's get out of here."
  - Gary *(instantly back)*: "YES. Farmers' market at the park, open till two.
    Ten-minute walk. Go go go!"

### 4. Out the door (40–48s)
- **Picture:** the door opens and the grade warms instantly. Walking POV,
  quick steps.
- **Sound:** door handle, door swing, a burst of outdoor ambience (wind,
  birds, traffic, distant voices), footsteps on pavement. Music builds.

### 5. "What is this?" (48–60s)
- **Picture:** stop at a duck, tree or bird and hold on it. Quick cut to a
  third-person shot: a hand pressing the strap button, the hat, the pack.
  This proves the hardware is real.
- **Overlay:** small caption *on-device vision · QNX*.
- **Sound:** footsteps stop, button click, Gary's good beep (`good.wav`).
- **Dialogue:**
  - You: "Go Gary, what is this?"
  - Gary: "Ooh, let me think… That's a mallard duck! See the green head?
    That's a boy. Journal entry: new!"

### 6. Montage (60–72s)
- **Picture:** fast cuts: another sniff, a journal entry sliding in, a
  fog-of-war tile clearing on the map, a friend jumping into frame (Herd
  Mode), the market stall.
- **Sound:** a beep and a UI whoosh on each cut. Market chatter, laughter, a
  register ding at the stall. Music at full energy.
- **Gary quips:** "Ooh, another one!" · "That's a new spot on the map!" ·
  "Herd Mode! The more the merrier!"

### 7. Quest complete and level up (72–82s)
- **Picture:** Gary's quest-done screen, the XP bar filling, pixel Gary
  growing a stage, sparkles.
- **Sound:** music dips. Checkmark sound (`done.wav`), an XP fill riser, a
  level-up fanfare.
- **Dialogue:** Gary: "Quest done! You know what that means…" *(fanfare)*
  "I'm getting bigger!"

### 8. End card (82–90s)
- **Picture:** walking toward the sunset, fade to black. *G.A.R.Y: Go
  Anywhere, Rediscover Yourself.* Small text: *Miss a day? Gary just naps.*
  Smaller: *on-device vision on QNX · live quests by TinyFish*.
- **Sound:** music resolves, birds and wind trail off.
- **Dialogue:** Gary *(sleepy)*: "Same time tomorrow? …If not, I'll just nap."
  *(snore)*

## Sound checklist

**Already in `device/sounds/`:** `good.wav`, `bad.wav`, `done.wav`,
`new.wav`, `herd.wav`, `quest.wav`, `hello.wav`, and the `say_*.wav` names
(e.g. `say_bird.wav`).

**Gary lines to generate** (same voice, `make_voice.py`):
1. "Mornin'! How're we feeling today?"
2. "Peachy! Love that. Okay, let me pull up today's quests. There's a trail, a market, oh, and a—"
3. "…Oh. Right. Work."
4. "YES. Farmers' market at the park, open till two. Ten-minute walk. Go go go!"
5. "Ooh, let me think… That's a mallard duck! See the green head? That's a boy. Journal entry: new!"
6. "Ooh, another one!"
7. "That's a new spot on the map!"
8. "Herd Mode! The more the merrier!"
9. "Quest done! You know what that means… I'm getting bigger!"
10. "Same time tomorrow? …If not, I'll just nap."

**Gary's noises:** stretch, goat bleat, deflate sigh, snore. These come from
an SFX library or from ElevenLabs prompts (e.g. `*yawns* Mornin'!`).

**SFX and ambience** (Pixabay or Freesound, free licence): phone alarm, bed
creak, duvet rustle, birds, room tone, clock tick, keyboard, notification
ping, fridge hum, laptop close, chair creak, door, footsteps, outdoor city,
market crowd, register ding, UI blips and whooshes, XP riser, level-up
fanfare.

**Music:** one royalty-free track that starts in shot 3 and builds to the
montage.

**Mix:** duck everything under Gary when he speaks. His lines are the loudest
thing in the mix.

## Shoot plan

- **Camera:** a phone on a hat clip, ultra-wide lens, for the GoPro look. Add
  a light fisheye and vignette in the edit.
- **Order:** the walk first (needs daylight), then the desk, then the bedroom
  (lights off and a lamp fake it any time).
- **Shots to get:** the bedroom ceiling and nightstand; the desk (three
  angles); the door opening; the walk; one thing to name (a duck is ideal);
  a third-person shot of the hat, button and pack; a friend stepping into
  frame; a market stall; sunset.
- **Screen captures** from the web app: the quest card, a journal entry, the
  map clearing, the XP bar and the level up.
- **Overlay:** pixel Gary from the web app, as a PNG with a "talking" frame
  to bounce or swap while he speaks.
