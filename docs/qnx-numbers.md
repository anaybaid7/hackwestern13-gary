# QNX numbers

Issue #14. The Sniff Test runs on a Raspberry Pi 5 under QNX 8, with the model
on the device. This page shows how fast Gary answers, and that the answer time
holds when the CPU is busy.

**Status: not measured yet.** The table below is empty until someone runs the
three commands on the Pi. Do not copy numbers from a laptop into it.

## What is measured

| Column | Meaning |
| --- | --- |
| Frames per second | Frames Gary's model finished per second |
| Model, mean | Time inside the TFLite model for one frame |
| Frame to decision | From a frame reaching Gary to "this is what I see". Time inside the camera and the USB link is not included |
| Button to answer | From the button press to the line written in the journal. Gary already knows what is in view, so this is short |

p50 is the middle value; p95 is the value 95 in 100 runs stay under.

## The runs

Run these on the Pi, in `~/gary`. In each run press the button about ten
times, then quit Gary with `q` and Enter. Each command adds one row below.

```
# 1. normal
./qnx/build/gary --mute
python3 gary_numbers.py --label "QNX, normal" --append ../docs/qnx-numbers.md

# 2. every core busy, Gary at real-time priority 20
python3 cpu_load.py --seconds 120 &
./qnx/build/gary --mute --priority 20
python3 gary_numbers.py --label "QNX, --priority 20, CPU loaded" --append ../docs/qnx-numbers.md

# 3. for contrast: every core busy, no priority
python3 cpu_load.py --seconds 120 &
./qnx/build/gary --mute
python3 gary_numbers.py --label "QNX, CPU loaded, no priority" --append ../docs/qnx-numbers.md
```

If the folder on the Pi is only `device/` (copied with `scp`), `../docs` is not
there: leave `--append` off and paste the printed row here by hand.

| Run | Frames | Frames per second | Model, mean | Frame to decision, p50 | p95 | max | Sniffs | Button to answer, p50 | p95 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

What to look for: row 2 should stay close to row 1, and row 3 should be
slower. That difference is the point: QNX always runs the highest-priority
ready thread, so Gary at priority 20 is not kept waiting by ordinary programs
at priority 10.

## Thread priorities

While run 2 is going, in a second terminal:

```
python3 gary_numbers.py --threads        # the same as: pidin | grep gary
```

Paste the output here, or add a screenshot as `docs/img/qnx-threads.png`.

```
(not captured yet)
```

## Power pull

1. Start Gary with `sh start_gary.sh`. Press the button three times.
2. Pull the power while he is running.
3. Plug it back in. Then:

```
python3 gary_numbers.py --check-journal
```

Paste the line it prints. "Journal intact" or "N events are intact. 1 damaged
line" both pass: at most the one line being written when the power went is
lost, and Gary starts a new line after it.

```
(not run yet)
```

## Heat

After 15 minutes of running: `python3 gary_numbers.py --temp`.

```
(not measured yet)
```

## Screenshots for the Devpost page

- [ ] The table above, with three rows
- [ ] `pidin | grep gary` during run 2
