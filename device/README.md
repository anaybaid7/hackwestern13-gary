# Gary device: camera → on-device model → feedback

Gary looks through a webcam, recognises everyday objects with a model that runs
on the device, checks them against today's quests, and answers with a sound.
No image is stored or uploaded. Only labels are written down.

| File | What it is | Status |
| --- | --- | --- |
| `gary_device.py` | The loop for a laptop, Raspberry Pi OS or macOS | Tested on photos and a simulated camera feed |
| `qnx/gary_qnx.cpp` | The same loop in C++ for QNX on the Pi 5 | Logic tested on Linux with stand-ins for the QNX camera and TFLite. Compiles against the real TFLite 2.21 headers. **Not yet run on a QNX Pi** |
| `models/` | SSD MobileNet v2 detector (80 everyday objects) and its label list | From google-coral/test_data |
| `quests.tsv` | Today's quests | Edit freely |
| `sounds/` | Placeholder chimes | Replace with Gary's voice |

Both versions read the same files and write the same `finds.jsonl`.

> **Where this stands against the team plan.** This version spots quest items by
> itself, and the button asks Gary what he sees. The team plan makes the button
> the main action (the Sniff Test). That change is the first Phase 1 task.

## 1. Try it on a laptop first (5 minutes)

```
cd device
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

python3 gary_device.py --image test/pets.jpg     # should print: dog 99%, dog 97%
python3 gary_device.py --show                    # webcam; hold up a water bottle
```

Press Enter to ask Gary what he sees. Type `q` then Enter to quit.
Tested with Python 3.13, numpy 2.5, opencv-python 5.0, ai-edge-litert 2.4.
On Windows, if `ai-edge-litert` will not install, use WSL or `pip install tensorflow`.

## 2. Hardware

1. Fit the heatsink or fan, then close the case. The model heats the Pi.
2. microSD card in, contacts facing the board.
3. Webcam into a **blue** USB port.
4. Optional: a USB headset or USB speaker for sound. The Pi 5 has no headphone jack.
5. First boot only: micro-HDMI to a monitor, plus a USB keyboard.
6. Power last. Wall supply at the table, power bank when walking.

## 3. QNX on the Pi

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
./qnx/build/gary --mute                    # camera + model. Hold up a water bottle
```

With USB audio plugged in, test it with `mmrplay sounds/found.wav`, then drop `--mute`.

If the build prints errors, paste them into the chat. This program has never
been compiled on QNX itself.

**Options worth knowing**

- `--unit 3` or `--unit 4`: a Pi camera on CAM/DISP 0 or 1, in place of USB.
- `--priority 20`: run the decision thread at a fixed real-time priority.
  `pidin | grep gary` then shows each thread's priority.
- `kill -USR1 $(cat gary.pid)`: ask Gary from another program. This is how a
  hardware button gets wired in without touching this code.
- `./qnx/build/gary < /dev/null &`: run with no keyboard attached.
- `--help` lists the rest.

## 4. Raspberry Pi OS instead (the fallback)

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

## 5. What to edit

- **Quests:** `quests.tsv`, one per line, TAB-separated: `id  label  points  text`.
  `label` must be a name in `models/coco_labels.txt`. A new `id` is a new quest.
- **Gary's voice:** replace the WAV files in `sounds/`. Add `sounds/<label>.wav`
  (for example `bottle.wav`, `fire_hydrant.wav`) and Gary plays it after the chime.
- **Strictness:** `--threshold 0.6` asks for more confidence. `--need 4` asks for
  4 of the last 5 frames. Raise these if Gary cheers at the wrong things.
- **Start over:** delete `finds.jsonl`.

## 6. What it writes

- `finds.jsonl`: one line per completed quest, on disk before the sound plays.
  Pull the power and restart: nothing is lost.
- `latency.csv`: per-frame timings, written on exit. The console prints frames
  per second and frame-to-decision time every 5 seconds. "Frame" means the frame
  reaching the program. Time inside the camera and USB link is not included.
- `gary.pid`: the running program's process id.

## 7. If something fails

| Symptom | Try |
| --- | --- |
| `camera unit 5 did not open` (QNX) | Webcam in a blue port? Does QNX's demo in step B work? Pi cameras are `--unit 3` or `4`. The camera list is `/etc/config/sensor/sensor_rpi5.conf` |
| Build cannot find `tensorflow-lite` or OpenCV (QNX) | Run `sudo ./configure.sh` in `~/QNX-AI-workshop` |
| Few frames per second (QNX) | QNX's camera wrapper asks for 720p. Lower `MIN_PIXELS` in `~/QNX-AI-workshop/rpi_cam.cpp` to `640 * 480` and rebuild |
| `Could not open camera 0` (Linux) | Run `ls /dev/video*`, then try `--camera 1` |
| No sound | QNX: `mmrplay sounds/found.wav` on its own. Linux: `aplay sounds/found.wav` |
| Pi is hot or slow | QNX: `cat /dev/thermal`. Add the fan |
| Gary never finds the object | On a laptop, `--show` draws what the model sees. Get closer, add light |
| Gary finds things that are not there | `--threshold 0.6 --need 4` |

## Credits

- Detector, label list and test photos: https://github.com/google-coral/test_data (Apache-2.0).
- Camera wrapper and build recipe on QNX: https://github.com/qnx/QNX-AI-workshop (Apache-2.0).
  `qnx/build_qnx.sh` clones it and compiles its `rpi_cam.cpp` unchanged.
