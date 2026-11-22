# Device: camera → on-device model → Sniff Test

Gary watches a webcam and runs an object model on every frame, so he always
knows what is in view. Nothing is recorded until someone presses the button.
That press is the **Sniff Test**: Gary names what he sees, writes one line in
his journal, and reacts. A friend in the frame makes it **Herd Mode**.

No image is stored or uploaded. Only labels are written down. The device
records facts; XP, stages and the map belong to the backend.

| File | What it is | Status |
| --- | --- | --- |
| `qnx/gary_qnx.cpp` | The real one: C++ for QNX on the Pi 5 | Logic tested on Linux with stand-ins for the QNX camera and TFLite. Compiles against the real TFLite 2.21 headers. **Not yet run on a QNX Pi** (issue #4) |
| `gary_device.py` | The same behaviour in Python, for a laptop or Raspberry Pi OS | Tested on photos and on a video played as the camera |
| `gary_io.py` | The button and the buzzer | Tested with stand-in pins. **Not yet run on real pins** (issues #10, #11) |
| `sync.py` | Uploads the journal, fetches quests | Tested, including no network and a power cut |
| `start_gary.sh`, `stop_gary.sh` | Run all of it in the background, with no keyboard or screen | Tested on Linux. **Not yet run on QNX** (issue #13) |
| `gary_numbers.py`, `cpu_load.py` | The timing table for the judges | Tested on Linux (issue #14) |
| `fake_sniff.py` | Posts a pretend sniff, for teammates with no device | Tested |
| `models/ssd_mobilenet_v2_…tflite`, `coco_labels.txt` | The main detector: SSD MobileNet v2, 80 everyday things and people. 57 ms a frame on the Pi | From google-coral/test_data |
| `models/gary_detector.tflite`, `gary_nature_labels.txt` | The extra detector, run on the same frames: YOLOv8s trained on Open Images, of which Gary keeps only the nature names (tree, squirrel, duck, butterfly, rabbit, deer ...). 228 ms a frame on the Pi, float32, 46 MB. `--extra-model none` turns it off | Made by `models/make_model.py`. Scores: `bench_results.md` |
| `models/hand_detector.tflite`, `hand_landmarks_detector.tflite` | Hand signals (`--gestures`, section 8c): Google's MediaPipe palm detector and 21-point hand model, unchanged, Apache-2.0. 2.3 MB and 5.5 MB | From the `hand_landmarker.task` bundle at storage.googleapis.com/mediapipe-models |
| `gary_hands.py`, `qnx/hand.hpp` | The hand-signal rules, the same in both: find the palm, read 21 points, decide thumbs up or OK, sniff when the hand is lowered | Tested with numbers from real photos (`test/hand_vectors.json`), the same in `tests/test_device.py` and `qnx/hand_test.cpp` |
| `bench_model.py` | How well the model names things: scores it on labelled photos (`--fetch` downloads about 10 per thing from Wikimedia Commons into `bench_photos/`, not committed). Writes `bench_results.md` | Run on the laptop |
| `qnx/live.sh` | A live view of what Gary sees, with his boxes, at `http://<pi>:8090`. Needs `GARY_LIVE=live/frame.jpg` in `gary.env`; off unless set. Each frame replaces the last, nothing is kept. The web page links to it when started with `VITE_LIVE_URL` | Run on the Pi |
| `quests.seed.tsv` | Three seed quests, used until `sync.py` has run | |
| `sounds/` | Clips that match the buzzer: right answers rise, a miss slides down. Played only with `GARY_SOUND=on` in `gary.env` (a USB speaker on the Pi) | Replace with Gary's voice |

Both versions of Gary read the same files and write the same `journal.jsonl`.
Each line of it is an Event from [`../contract`](../contract/README.md).

## 1. Try it on a laptop first (5 minutes)

```
cd device
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

python3 gary_device.py --image test/pets.jpg     # one Sniff Test on a photo: "SNIFF: dog (99%)"
python3 gary_device.py --show                    # webcam; hold up a water bottle, press Enter
```

Enter is the button. Type `q` then Enter to quit.
Tested with Python 3.13, numpy 2.5, opencv-python 5.0, ai-edge-litert 2.4.
On Windows, if `ai-edge-litert` will not install, use WSL or `pip install tensorflow`.

## 2. Connect it to the backend

In a second terminal, with the backend running (see `../backend/README.md`):

```
python3 sync.py --api http://localhost:8000
```

Every few seconds it uploads new journal lines and fetches quests into
`quests.tsv`. With no network it waits and retries; Gary keeps working from his
journal and his cached quests. No event is lost and none is counted twice.

No device at all? `python3 fake_sniff.py bench --friend` posts a pretend sniff.

## 3. Hardware

1. Fit the heatsink or fan, then close the case. The model heats the Pi.
2. microSD card in, contacts facing the board.
3. Webcam into a **blue** USB port.
4. Button and buzzer on the pin header (section 5).
5. Optional: a USB headset or USB speaker for sound. The Pi 5 has no headphone jack.
6. First boot only: micro-HDMI to a monitor, plus a USB keyboard.
7. Power last. Wall supply at the table, power bank when walking.

## 4. QNX on the Pi

**A. Log in.** From a laptop on the same network:

```
ssh qnxuser@<hostname>.local                       # password: qnxuser
ssh -m hmac-sha2-256 qnxuser@<hostname>.local      # the same, from Windows
```

`sudo` works (root password `root`). The desktop is on HDMI, or over VNC at
`<hostname>.local:5900` with password `qnxuser`.

**B. Prove the camera and the model with QNX's own demo.** QNX verified it
with the Logitech C270. A USB webcam is camera unit 5. It opens a window, so
watch it on HDMI or VNC.

```
git clone https://github.com/qnx/QNX-AI-workshop ~/QNX-AI-workshop
cd ~/QNX-AI-workshop
sudo ./configure.sh      # date error? run: sudo ntpdate -bs pool.ntp.org
./build.sh
./start.sh --ros-args -p camera_unit:=5
```

A hand skeleton on screen means the camera and TFLite both work on this Pi.

**C. Copy this folder to the Pi.** Run on the laptop, from the repo root:

```
scp -r device qnxuser@<hostname>.local:~/gary
scp -r -o MACs=hmac-sha2-256 device qnxuser@<hostname>.local:~/gary     # from Windows
```

**D. Build, self-test, run.** On the Pi:

```
cd ~/gary
sh qnx/build_qnx.sh
./qnx/build/gary --image test/pets.jpg     # model only, no camera. Expect two dogs
./qnx/build/gary --mute                    # camera + model. Hold up a water bottle, press Enter
python3 sync.py --api http://<backend address> &
```

With USB audio plugged in, test it with `mmrplay sounds/quest.wav`, then drop `--mute`.

If the build prints errors, paste them into issue #4. This program has never
been compiled on QNX itself.

**Options worth knowing**

- `--unit 3` or `--unit 4`: a Pi camera on CAM/DISP 0 or 1, in place of USB.
- `--priority 20`: run the decision thread at a fixed real-time priority.
  `pidin | grep gary` then shows each thread's priority.
- `./qnx/build/gary < /dev/null &`: run with no keyboard attached.
- `--help` lists the rest.

## 5. Button and buzzer (`gary_io.py`)

A second, small program. It never touches the vision code: a press sends Gary
a signal, and the beeps follow his journal. If the button or buzzer is missing,
Gary carries on and Enter still sniffs.

**Wiring.** A Grove cable is red = power, black = ground, yellow = signal,
white = unused. Grove plugs do not fit the Pi's pins, so use Grove-to-jumper
cables from the hardware desk.

| Part | Red (power) | Black (ground) | Yellow (signal) |
| --- | --- | --- | --- |
| Button | pin 1 (3.3 V) | pin 6 | pin 11 (GPIO17) |
| Buzzer | pin 17 (3.3 V) | pin 9 | pin 13 (GPIO27) |

Never use the 5 V pins (2 and 4): the Pi's inputs are 3.3 V only.
With a Grove Base HAT, plug into two digital sockets and pass their numbers,
for example `--button-pin 5 --buzzer-pin 16` for D5 and D16.

**Run it** from the device folder, on QNX or Raspberry Pi OS:

```
python3 gary_io.py --demo     # plays good (one quick beep) and bad (three). Start here
python3 gary_io.py            # button on GPIO17, buzzer on GPIO27
python3 gary_io.py --fake     # on a laptop: Enter is the button, beeps are printed
```

On Raspberry Pi OS run it with the system `python3`, not the venv one: the
GPIO library lives with the system Python.

| You hear | It means |
| --- | --- |
| one short beep | Gary has seen one before |
| two short beeps | a new discovery |
| three beeps, each one longer | quest complete |
| a quick double chirp after it | a friend is in frame (Herd Mode) |
| one long buzz | nothing Gary can name |
| two long buzzes | the button was pressed but Gary is not running |
| one tick at start | `gary_io.py` is alive |

The Grove buzzer is an on/off part, so the patterns differ by rhythm. `--tones`
also varies the pitch through PWM; that is untested.

One push is one Sniff Test: the level must hold for 30 ms (`--debounce-ms`),
and pushes closer than 400 ms count as one (`--gap-ms`). If the button
connects the pin to ground when pressed, add `--active-low`.

**The mood tap and the short or long choice** (issue #12) are on the web page,
not on the device: the Grove rotary knob is an analog part and the Pi has no
analog input. If you later read the knob through the UNO Q, this is the only
call it needs, and `sync.py` uploads the line like any other:

```
python3 gary_io.py --mood before 3      # or: after 4
```

## 6. Field kit: no keyboard, no screen, no network

```
cp gary.env.example gary.env      # set GARY_API to the backend's address
sh start_gary.sh                  # starts Gary, sync.py and gary_io.py in the background
sh start_gary.sh status           # who is up, and Gary's last lines
sh stop_gary.sh
sh start_gary.sh --fresh          # set the old journal aside and start clean, for a rehearsal
```

From a laptop, in one line: `ssh qnxuser@<hostname>.local 'sh ~/gary/start_gary.sh'`.
You can log out; everything keeps running. If Gary stops, he is started again
after 3 seconds. Logs are in `logs/`.

### Run the backend on the Pi too

Then nothing but a browser is needed off the device: the camera, the model, the
rules, Gary's state and the page all live on the Pi, and a sniff becomes XP with
no network at all.

```
# once: the backend, the contract and the built page, beside ~/gary
(cd web && VITE_API_URL= npm run build)       # on the laptop: the page talks to its own address
tar czf - backend/*.py backend/schema.sql contract web/dist | ssh qnxuser@<pi> 'mkdir -p ~/server && tar xzf - -C ~/server'
ssh qnxuser@<pi> 'cd ~/gary && python3 -m venv venv && venv/bin/pip install "fastapi==0.99.1" "pydantic<2" uvicorn tzdata'
# gary.env on the Pi
GARY_API=http://localhost:8800
GARY_BACKEND=../server/backend
```

`sh start_gary.sh` then starts the backend too, and keeps Gary's state in
`gary.db` (SQLite), so pulling the plug loses nothing. Open
`http://<pi>:8800` on a laptop or phone. With `GARY_LIVE` set, the live view is at
`http://<pi>:8800/live/` (build the page with `VITE_LIVE_URL=/live/`). The scout posts quests to the same
address.

**Start at power-on (QNX).** QNX runs `/usr/etc/post_startup.sh` at the end of
start-up. Add one line to it, as root:

```
su root                                                     # password: root
echo "su - qnxuser -c 'sh \$HOME/gary/start_gary.sh'" >> /usr/etc/post_startup.sh
```

Then pull the power, plug it back in, wait a minute and press the button.
This line is **not tested on QNX**. If Gary does not come up, use the SSH line
above; issue #13 accepts either.

**No network.** Sniffs are written to `journal.jsonl` first, so they work with
no network at all. `sync.py` uploads everything once the network is back.
Nothing is lost and nothing is counted twice.

**The clock.** A Pi that starts with no network may not know the time.
`sync.py` tells the backend what the Pi's clock reads at upload time, so the
backend can put the timestamps right. With a network, `sudo ntpdate -bs
pool.ntp.org` sets the clock.

**Phone hotspot.** Join the Pi to the hotspot the same way as to Wi-Fi, set
`GARY_API` to the backend's public address, and the walk is live.

**Heat.** After 15 minutes: `python3 gary_numbers.py --temp` (on QNX it reads
`/dev/thermal`).

## 7. QNX numbers for the judges

Gary prints frames per second and frame-to-decision time every 5 seconds, each
sniff prints its button-to-answer time, and he writes `latency.csv` when he
stops. `gary_numbers.py` turns one run into a table row.

```
# 1. a normal run: press the button ten times, then q + Enter
./qnx/build/gary --mute
python3 gary_numbers.py --label "QNX, normal" --append ../docs/qnx-numbers.md

# 2. the same with every core busy and a real-time priority
python3 cpu_load.py --seconds 120 &
./qnx/build/gary --mute --priority 20
python3 gary_numbers.py --label "QNX, --priority 20, CPU loaded" --append ../docs/qnx-numbers.md

# 3. for contrast: every core busy, no priority
python3 cpu_load.py --seconds 120 &
./qnx/build/gary --mute
python3 gary_numbers.py --label "QNX, CPU loaded, no priority" --append ../docs/qnx-numbers.md

python3 gary_numbers.py --threads         # while Gary runs: his threads and priorities (pidin)
python3 gary_numbers.py --check-journal   # after pulling the power: is the journal intact?
```

"Frame" means the frame reaching the program. Time inside the camera and the
USB link is not included. The page to fill in is `../docs/qnx-numbers.md`.

## Pairing Gary with a person (optional)

`python3 pair.py` pairs this Gary with whoever approves the code it shows
(Auth0's device flow; see `docs/AUTH0.md`). The token is kept in `gary.token`,
which git ignores, and `sync.py` sends it with each upload. `pair.py --status`
says whether he is paired, `pair.py --forget` unpairs him. An unpaired Gary
works exactly as before. If the Pi's Python has no `https`, run `pair.py` on a
laptop and copy `gary.token` to the Pi.

## 8. Hooks for other programs

| Do this | Effect |
| --- | --- |
| `kill -USR1 $(cat gary.pid)` | One Sniff Test. `gary_io.py` sends this on a button press |
| `kill -HUP $(cat gary.pid)` | Reload the quests. `sync.py` sends this |
| watch `journal.jsonl` | One new line per sniff: `discovery` or `miss`. `gary_io.py` beeps from this |

## 8b. Talking to Gary ("Go Gary")

Say **"Go Gary"** (or hold the button for 0.8 s). Gary says "Go ahead!". Ask
something; he says one of five "let me think" lines and answers in his voice
in about 2 to 3 s. All in one breath works too: "Go Gary, what's that?".

What he can do:

| Say | Gary |
| --- | --- |
| "What am I looking at?" | Names it, with one true fact |
| "Good morning!" | Greets you, then asks: a short or a long quest? (just answer, no "Go Gary") |
| "What quests do I have?" / "Where's my quest?" | Today's quest, its place and note, the short and long options |
| "Give me a short task" / "a long one" | Picks it in the app (`/api/quest/choose`), then says what it is |
| "Create a task to find a duck at the pond" | Adds a quest (`/api/quests`, source `gary`). Only things he can find; a penguin is politely refused |
| "How close are you to growing?" / "Where's our herd?" | Stage, XP, finds, field guide, places uncovered, the Herd Cup (herds, never people) |
| "Where am I?" | The city, the quest's place, places you reached. Never your exact spot: the phone keeps it |
| "How am I feeling?" | Never reads a check-in out: points you to the private You tab |

He remembers the last few things said for two minutes (in memory only), so
"where is that?" works after a quest. When he asks you something he keeps
listening, so you just answer.

- **The app:** `--api http://<backend>` or `GARY_API`; with `--seeing <url>/api/seeing`
  he uses that backend. Its state is refreshed every 5 s in the background, so
  answers never wait for it. Making a quest needs `SCOUT_KEY` in `device/.env`
  when the server sets one.
- **The voice:** answers and the talk clips (go ahead, let me think, ears) use
  `eleven_flash_v2_5` at speed 1.2 (`TTS_SPEED`; `TALK_SETTINGS` in
  `make_voice.py`). The prompts are `GARY`, `RULES` and `HOW` in `gary_talk.py`.

- `gary_talk.py` runs beside Gary (`GARY_TALK=on` in `gary.env`; `start_gary.sh`
  starts it, log in `logs/talk.log`). Standard library only.
- **In a loud room** run it with `--strict` (or `GARY_TALK_STRICT=on`): every question then
  needs "Go Gary", also your answer to something Gary asked. Without it he takes the next
  voice he hears as your answer. `--min-level 1500` makes only a close voice count, and
  `--below-peak 0.45` ends your sentence when you stop even if people nearby keep talking.
  Too loud even for that? Press Enter in its terminal (or hold the button): that is "Go Gary"
  with no listening for it. `--verbose` says what he did with each sound, never the words. He also
  ignores the microphone for half a second after he stops speaking, so he never answers
  the tail of his own voice.
- **What Gary sees:** both versions of Gary write `seeing.json` twice a second:
  the labels he is sure of, never a picture. Gemini gets those labels.
- **Your voice** goes to Gemini (`gemini-3.1-flash-lite`, with `gemini-2.5-flash`
  as the backup when it is slow) to hear the question and answer it. It is never
  written to disk, logged or printed. "Go Gary" is checked in code from the words
  Gemini heard, so talking *about* Gary never wakes him.
- **Gary's answer** is spoken by ElevenLabs' fastest model (`eleven_flash_v2_5`,
  voice Maxim). "Go ahead", "let me think" and "my ears are fuzzy" are ready-made
  clips (`make_voice.py`).
- **Keys:** `GEMINI_API_KEY` and `ELEVENLABS_API_KEY` in `device/.env` (ignored by
  Git). It needs a network: the phone hotspot on a walk.
- **The microphone:** the Logitech C270 has one built in. Any command that writes
  raw 16-bit mono 16 kHz sound to its output works, set as `GARY_TALK_REC` in
  `gary.env`:
  - Raspberry Pi OS / Linux: `arecord -l` shows the webcam's card number, then
    `GARY_TALK_REC="arecord -q -D plughw:1,0 -f S16_LE -r 16000 -c 1 -t raw"`.
  - QNX: **not yet tried.** QNX 8 records through `io-snd`; find the webcam's
    capture device (`ls /dev/snd`) and a recorder that writes raw PCM to its
    output. Until then, talking works on the Raspberry Pi OS fallback or a laptop.
- **Try it with no microphone:** `python3 gary_talk.py --ask "what is a goose?"`
  (a typed question), or `--from-wav question.wav` (16-bit mono 16 kHz).
- The prompts (Gary's personality and the rules: true facts only, never name a
  bird's species, never describe a person, nothing about health or anything
  unsafe) are `GARY`, `RULES` and `HOW` at the top of `gary_talk.py`.

## 8c. Hand signals (`--gestures`)

A **thumbs up** or an **OK sign**, held close to the camera and then lowered,
is a Sniff Test: the same as pressing the button, with no hands on Gary.

```
show a thumbs up (or OK)   ->  "HAND: thumbs up. Lower your hand and Gary sniffs."
lower your hand            ->  "HAND: lowered. Sniffing."  ->  the usual SNIFF line
```

- **Turn it on:** add `--gestures` to `GARY_FLAGS` in `gary.env`
  (`GARY_FLAGS="--mute --gestures"`), or pass it to `gary_device.py` or
  `qnx/build/gary`. Off by default. If the two hand models do not load, Gary
  says so and runs without hand signals.
- **How:** a palm detector finds the surest hand; a second model finds 21
  points on it (knuckles and fingertips); plain rules on those points say
  thumbs up, OK or nothing (`gesture()` in `gary_hands.py` and `qnx/hand.hpp`).
  A signal in 3 of 5 frames arms Gary.
- **Why he waits for the hand to go:** he sniffs once no hand has been in view
  for 3 frames. So your hand never hides the thing, and is never taken for a
  friend (Herd Mode). A hand that stays up for 6 s is forgotten. After a sniff,
  no signal counts for 2 s.
- **Only your hands:** the palm must be at least a tenth of the frame's width
  (`--min-hand 0.10`): the wearer's own hand, close to the hat camera, is; a
  hand across the room is not. Gary never works out whose hand it is.
- **Not a thumbs up:** a thumb pointing down or sideways, an open hand, a fist.
- **Speed:** both models together take 10 to 25 ms a frame on a laptop. On the
  Pi they run after the decision, so a button sniff's answer is never slowed;
  frames per second drop a little. **Not yet measured on the Pi.**
- With hand signals on, the QNX Gary keeps camera frames at 640 x 480 (a hand
  needs more pixels than a bottle); each detector shrinks the frame itself.
- Nothing is stored or uploaded: the hand is read and forgotten, frame by frame.

## 9. Raspberry Pi OS instead (the fallback)

Use a second microSD card. Do not re-flash the QNX one.

```
sudo apt update && sudo apt install -y python3-venv alsa-utils
cd device
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 gary_device.py
```

`start_gary.sh` works here too: with no QNX build it starts the Python
version from `venv/`.

Sound on the wrong device? Run `aplay -l`, find the USB card number, and start
with `--audio-cmd "aplay -q -D plughw:2,0"` (2 = that number).

## 10. What to edit

- **Quests:** they come from the backend through `sync.py`. To test by hand,
  stop `sync.py` and edit `quests.tsv` (or `quests.seed.tsv`): one quest per
  line, TAB-separated: `id  target  xp  text`, plus `herd` as a fifth column
  for a quest that needs a friend in frame. `target` must be a name in
  `models/coco_labels.txt` or `models/gary_nature_labels.txt`. When two open quests want the same thing, the
  earlier line wins; `sync.py` puts the quest chosen on the web page first.
- **Gary's voice:** Gary speaks with the `sounds/say_*.wav` clips: "You found
  the water bottle!", "That's not what we're looking for. That's a bird.",
  "Hmm, I'm not seeing it right. Can you move closer?". They are made once, on
  a laptop, by `python3 make_voice.py` with ElevenLabs (the voice is Maxim; put
  `ELEVENLABS_API_KEY` in `device/.env`, and optionally `ELEVENLABS_VOICE_ID`).
  The Pi needs no key and no network to play them. The lines are in
  `make_voice.py`; `voice_clips()` (in both versions of Gary) picks which ones
  to play. To change a line, edit it there and run `python3 make_voice.py
  --force --only say_<clip>`. Intonation: the default model, `eleven_v3`, reads
  a cue in front of each line (`[excited] Yes! You found the water bottle!`,
  `[thoughtful] Hmm...`); the cues are `CUES` and `PREFIX_CUES` in
  `make_voice.py`. After making them all again, set `VOICE_RATE` in
  `web/src/sound.js` back to 1. Right before the voice, Gary plays a cue:
  `good.wav` (one quick beep and a "check"), `bad.wav` (three quick beeps and
  an "X") or, when he names nothing, `unsure.wav` (a puzzled "hm... hmm?"). The
  buzzer counts the same way. The voice starts when the cue is 75% through
  (`Speaker.LEAD`, `kLead` in the C++), so the player's start-up fills the last
  quarter and there is no gap. The cues are made by `ensure_sounds()` in
  `gary_device.py` and committed, because the QNX Gary does not make them. If
  any clip a sniff needs is missing, Gary plays the chimes (`hello`, `new`,
  `again`, `quest`, `herd`, `nothing`, `done`) instead.
- **Strictness:** the default threshold is 0.35. `--threshold 0.6` asks for more confidence. `--need 4` asks for
  4 of the last 5 frames. Raise these if Gary names the wrong things.
- **What Gary can recognise:** edit `NATURE` (or `RENAME`) in `models/make_model.py` and the
  same names in `contract/labels.json`, then rebuild the model (the command is
  at the top of the script; it needs its own Python 3.12 with `ultralytics`).
  `tests/test_device.py` checks the two lists agree. Do not export it as int8:
  that ruins the class scores, and 8-bit weights use an op older TFLite lacks.
- **Start over:** `sh start_gary.sh --fresh`, or delete `journal.jsonl` and `sync.state`.

## 11. What it writes

- `journal.jsonl`: one line per sniff, on disk before Gary reacts. Pull the
  power and restart: nothing is lost. If the power went in the middle of a
  line, that one line is skipped and the next sniff starts a new one.
- `quests.tsv`, `sync.state`: written by `sync.py`.
- `latency.csv`: per-frame timings, written when Gary stops.
- `gary.pid`: the running program's process id.
- `seeing.json`: what Gary is sure he sees right now (labels only), twice a second, for `gary_talk.py`.
- `logs/`: written by `start_gary.sh`.

None of these are tracked by git.

## 12. Tests

```
python3 tests/test_device.py        # the scripts: button, buzzer, sync, start and stop. No Pi
sh qnx/host_test/run.sh             # the C++ program against stand-ins (Linux, g++, libopencv-dev)
```

## 13. If something fails

| Symptom | Try |
| --- | --- |
| `camera unit 5 did not open` (QNX) | Webcam in a blue port? Does QNX's demo in step 4B work? Pi cameras are `--unit 3` or `4`. The camera list is `/etc/config/sensor/sensor_rpi5.conf` |
| Build cannot find `tensorflow-lite` or OpenCV (QNX) | Run `sudo ./configure.sh` in `~/QNX-AI-workshop` |
| Few frames per second (QNX) | QNX's camera wrapper asks for 720p. Lower `MIN_PIXELS` in `~/QNX-AI-workshop/rpi_cam.cpp` to `640 * 480` and rebuild |
| `Could not open camera 0` (Linux) | Run `ls /dev/video*`, then try `--camera 1` |
| The button does nothing | `python3 gary_io.py` in a terminal and press: it prints each press. "Gary is not running" means no `gary.pid`. No line at all means wiring: yellow on pin 11, red on pin 1 |
| The button fires by itself | A loose signal wire. Or the button pulls to ground: add `--active-low` |
| No beeps | `python3 gary_io.py --demo`. Check yellow on pin 13. On QNX, `pidin \| grep rpi_gpio` must show the GPIO manager running |
| No sound from a speaker | QNX: `mmrplay sounds/quest.wav` on its own. Linux: `aplay sounds/quest.wav` |
| Gary does not answer "Go Gary" | `tail logs/talk.log`. Keys in `device/.env`? A network? Try `python3 gary_talk.py --ask "hello"` first, then the recorder on its own |
| Pi is hot or slow | `python3 gary_numbers.py --temp`. Add the fan |
| "nothing Gary can name" | On a laptop, `--show` draws what the model sees. Get closer, add light, hold still for a second |
| Gary names things that are not there | `--threshold 0.6 --need 4` |
| `sync.py` says offline | Check `GARY_API` and that the backend runs with `--host 0.0.0.0` |
| Times on the web page are wrong | The Pi's clock. With a network: `sudo ntpdate -bs pool.ntp.org` |

## Credits

- Detector, label list and test photos: https://github.com/google-coral/test_data (Apache-2.0).
- Camera wrapper and build recipe on QNX: https://github.com/qnx/QNX-AI-workshop (Apache-2.0).
  `qnx/build_qnx.sh` clones it and compiles its `rpi_cam.cpp` unchanged.
