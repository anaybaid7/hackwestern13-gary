# Gary's body: the field kit design

A proposal for how to put Gary together so he can go on a walk, built from
household supplies. It is for issue #13 (field kit). Nothing here has been built
or tested yet: read it, change it, and tick the checks in section 8 as you go.

## 1. The goal

Gary works on a walk: no keyboard, no screen on the device, no table. Issue #13
is done when someone walks outside for 5 minutes, sniffs three things, comes
back, and all three are on the web page.

- **The screen is the laptop or a phone**, showing the web page (`docs/PLAN.md`,
  "Hardware notes"). Gary himself has no screen.
- **The camera goes on a hat**, so Gary sees what you look at. Aiming is free.
- Everything else rides in a small pack on the hip or a strap.

## 2. What goes in

From `device/README.md` (sections 3 and 5) and `docs/PLAN.md`:

| Part | Where it goes | Notes |
| --- | --- | --- |
| Raspberry Pi 5, running QNX | Pack | Gets hot under the model. Needs its heatsink or fan and air |
| microSD card | In the Pi | Keep the spare from #39 in the pack's pocket |
| Logitech C270 USB webcam | Hat brim | Into a **blue** USB port. Its cable runs down the back |
| Grove button | In the hand, or on the hat | Grove-to-jumper cable, or a Grove Base HAT (socket D5) |
| Grove buzzer | Hat, near the ear, or the pack | Socket D16 (`GARY_BUZZER_PIN=16`). On/off part: one loudness |
| USB speaker (optional) | Pack or shoulder strap, facing up | Plays Gary's voice and the good / bad / unsure cues |
| USB-C power bank | Pack, its own compartment | 5 V / 3 A or more. The Pi 5 is fussy on weak banks |
| Phone | Pocket | Hotspot for the Pi, and the web page as Gary's face |

**Wiring rules that stay true in any case:** only the 3.3 V pins, never 5 V (the
Pi's inputs are 3.3 V); Grove plugs do not fit the Pi's pins, so use
Grove-to-jumper cables or the Base HAT. Full table: `device/README.md`
section 5.

## 3. The layout

```
   [cap]   webcam clipped to the brim, buzzer near the ear
     │     webcam cable: over the cap, down the back of the neck
     ▼
 [pack on the hip or a chest strap]
     Pi 5 (vents, fan)  │ divider │  power bank      speaker on the outside
     │
 [button in the hand, on a Grove cable]
```

## 4. The camera on a hat

The C270 already has a folding clip, made for the top of a monitor. That clip
holds it on a cap's brim.

1. **A baseball cap.** Clip the C270 to the brim, then add two zip ties or a
   rubber band through the clip and around the brim, so it cannot wobble.
   A headlamp strap (elastic) is steadier on a walk, if someone has one.
2. **Tilt it down about 15 to 20 degrees.** People look at things below eye
   level, and the brim lifts the view. Set it while wearing the cap: run
   `python3 gary_device.py --show` on a laptop, look at a water bottle on the
   table, and move the camera until the bottle is in the middle.
3. **Run the cable** over the top of the cap and down the back of the neck.
   Binder clips or safety pins hold it to the cap and the collar.
4. **Strain relief.** Tape a small loop of cable near the camera, so a tug pulls
   the tape and not the plug. Do the same where the cable enters the pack.

## 5. The pack

1. **A box:** a pencil case, a small food container or a shoebox. Two slits take
   a belt or a lanyard, so it is worn as a hip pack, or it is strapped to a
   backpack's shoulder strap.
2. **Heat first** (`device/README.md` says the model heats the Pi):
   - cut vent holes above and beside the Pi, and keep its fan;
   - never seal it in plastic;
   - a cardboard divider keeps the power bank's warmth away from the Pi.
3. **Padding and fixing:** sponge or folded cloth under the Pi, and velcro or
   double-sided tape for each part, so nothing slides when you walk.
4. **Ports reachable:** leave the power cable and one USB port reachable
   without opening the pack.

## 6. Button, buzzer and speaker

- **Button:** hot glue or tape it to a clothespin, a bottle cap or a popsicle
  stick, so it is found by feel. Or put it on the side of the cap: tap your
  temple to sniff, which looks good in the demo.
- **Buzzer:** on the cap near the ear, so the good / bad / unsure beeps are heard
  outdoors (one quick beep, three quick beeps, two puzzled ones). It cannot be
  made quieter in software; a piece of tape over its hole works.
- **Speaker:** clipped to the pack or a shoulder strap, facing up, so judges hear
  Gary's voice.
- **Cables:** tie the Grove cables together and hold them along a strap with
  velcro or binder clips.

## 7. Make him look like Gary

Cardboard or felt horns and ears on the cap, and a goat face drawn on the pack.
It costs nothing, people remember it, and it helps the Most Adventurous pitch.

## 8. Build order and checks

Each step ends with a check. The last ones are #13's own boxes.

| # | Step | Check |
| --- | --- | --- |
| 1 | Camera on the cap | `--show`: a bottle held at arm's length while you look at it is in the middle of the frame |
| 2 | Pi, divider, power bank, speaker in the pack | Pi boots on the power bank; no low-power warning |
| 3 | Cables routed, strain-relief loops taped | A gentle tug on the cable does not move the plug |
| 4 | Button and buzzer placed | One press = one journal line, and you hear the beep |
| 5 | Start at power-on, or the one-line SSH start | `sh start_gary.sh status` says Gary is up (`device/README.md` section 6) |
| 6 | Phone hotspot | The Pi joins it, and a sniff reaches the web page |
| 7 | Heat | `python3 gary_numbers.py --temp` after 15 minutes inside the closed pack |
| 8 | **The walk** | 5 minutes outside, three sniffs, all three on the web page |

## 9. Supplies

Baseball cap · zip ties · rubber bands · binder clips · safety pins · duct or
electrical tape · velcro or double-sided tape · a pencil case, food container
or shoebox · cardboard · sponge or cloth · a belt or lanyard · hot glue
(optional) · felt or paper for the horns and ears.

## 10. Open questions for the team

- Who builds it, and whose cap and power bank?
- Button in the hand or on the cap?
- Hip pack or chest strap? The chest is closer to the camera, so a shorter cable
  and less pulling; the hip is easier to wear.
- Is the webcam cable long enough from the brim to the hip? Measure before
  cutting anything. A USB extension cable fixes it if not.
- Does the power bank keep the Pi 5 running for a whole walk with the webcam
  and speaker on? Test it in step 2.
