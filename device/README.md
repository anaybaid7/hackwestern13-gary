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
| `gary_device.py` | The same behaviour in Python, for a laptop or Raspberry Pi OS | Tested on photos and a simulated camera feed |
| `sync.py` | Uploads the journal, fetches quests | Tested against the backend, including no network |
| `fake_sniff.py` | Posts a pretend sniff, for teammates with no device | Tested |
| `models/` | SSD MobileNet v2 detector (80 everyday objects) and its labels | From google-coral/test_data |
| `quests.seed.tsv` | Three seed quests, used until `sync.py` has run | |
| `sounds/` | Placeholder chimes | Replace with Gary's voice |

Both versions read the same files and write the same `journal.jsonl`. Each
line of it is an Event from [`../contract`](../contract/README.md).

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
4. Optional: a USB headset or USB speaker for sound. The Pi 5 has no headphone jack.
5. First boot only: micro-HDMI to a monitor, plus a USB keyboard.
6. Power last. Wall supply at the table, power bank when walking.

The button and buzzer are Phase 2 (issues #10, #11). Until then, Enter is the button.

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
python3 sync.py --api http://<backend address>:8000 &
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

## 5. Hooks for other programs

These are how the button, the buzzer and the sync script work without touching
the vision code.

| Do this | Effect |
| --- | --- |
| `kill -USR1 $(cat gary.pid)` | One Sniff Test. A button script sends this (issue #10) |
| `kill -HUP $(cat gary.pid)` | Reload the quests. `sync.py` sends this |
| watch `journal.jsonl` | One new line per sniff: `discovery` or `miss`. A buzzer script reads this (issue #11) |

## 6. Raspberry Pi OS instead (the fallback)

Use a second microSD card. Do not re-flash the QNX one.

```
sudo apt update && sudo apt install -y python3-venv alsa-utils
cd device
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 gary_device.py
```

Sound on the wrong device? Run `aplay -l`, find the USB card number, and start
with `--audio-cmd "aplay -q -D plughw:2,0"` (2 = that number).

## 7. What to edit

- **Quests:** they come from the backend through `sync.py`. To test by hand,
  stop `sync.py` and edit `quests.tsv` (or `quests.seed.tsv`): one quest per
  line, TAB-separated: `id  target  xp  text`, plus `herd` as a fifth column
  for a quest that needs a friend in frame. `target` must be a name in
  `models/coco_labels.txt`.
- **Gary's voice:** replace the WAV files in `sounds/` (`hello`, `new`,
  `again`, `quest`, `herd`, `nothing`, `done`). Add `sounds/<label>.wav`, for
  example `bottle.wav`, and Gary plays it after the chime.
- **Strictness:** `--threshold 0.6` asks for more confidence. `--need 4` asks for
  4 of the last 5 frames. Raise these if Gary names the wrong things.
- **Start over:** delete `journal.jsonl` and `sync.state`.

## 8. What it writes

- `journal.jsonl`: one line per sniff, on disk before Gary reacts. Pull the
  power and restart: nothing is lost.
- `quests.tsv`, `sync.state`: written by `sync.py`.
- `latency.csv`: per-frame timings, written on exit. The console prints frames
  per second and frame-to-decision time every 5 seconds, and each sniff prints
  its button-to-answer time. "Frame" means the frame reaching the program. Time
  inside the camera and USB link is not included.
- `gary.pid`: the running program's process id.

None of these are tracked by git.

## 9. If something fails

| Symptom | Try |
| --- | --- |
| `camera unit 5 did not open` (QNX) | Webcam in a blue port? Does QNX's demo in step 4B work? Pi cameras are `--unit 3` or `4`. The camera list is `/etc/config/sensor/sensor_rpi5.conf` |
| Build cannot find `tensorflow-lite` or OpenCV (QNX) | Run `sudo ./configure.sh` in `~/QNX-AI-workshop` |
| Few frames per second (QNX) | QNX's camera wrapper asks for 720p. Lower `MIN_PIXELS` in `~/QNX-AI-workshop/rpi_cam.cpp` to `640 * 480` and rebuild |
| `Could not open camera 0` (Linux) | Run `ls /dev/video*`, then try `--camera 1` |
| No sound | QNX: `mmrplay sounds/quest.wav` on its own. Linux: `aplay sounds/quest.wav` |
| Pi is hot or slow | QNX: `cat /dev/thermal`. Add the fan |
| "nothing Gary can name" | On a laptop, `--show` draws what the model sees. Get closer, add light, hold still for a second |
| Gary names things that are not there | `--threshold 0.6 --need 4` |
| `sync.py` says offline | Check the `--api` address and that the backend runs with `--host 0.0.0.0` |

## Credits

- Detector, label list and test photos: https://github.com/google-coral/test_data (Apache-2.0).
- Camera wrapper and build recipe on QNX: https://github.com/qnx/QNX-AI-workshop (Apache-2.0).
  `qnx/build_qnx.sh` clones it and compiles its `rpi_cam.cpp` unchanged.
