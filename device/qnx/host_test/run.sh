#!/bin/sh
# Build gary_qnx.cpp on a Linux laptop against stand-ins for the QNX camera
# and TFLite, play a scripted scene, and check the journal. No Pi needed.
#
#   sudo apt install g++ libopencv-dev git      (once)
#   sh device/qnx/host_test/run.sh
#
# This checks Gary's logic and threading. It does not check the real camera,
# the real model or the QNX build: that is issue #4, on the Pi.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DEVICE="$(cd "$HERE/../.." && pwd)"
WORKSHOP_DIR="${WORKSHOP_DIR:-$HOME/QNX-AI-workshop}"
if [ ! -f "$WORKSHOP_DIR/rpi_cam.hpp" ]; then
  echo "Cloning QNX-AI-workshop into $WORKSHOP_DIR (for rpi_cam.hpp)"
  git clone --quiet --depth 1 https://github.com/qnx/QNX-AI-workshop "$WORKSHOP_DIR"
fi
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
# OpenCV goes in as a system include, so its own warnings do not fail our build.
OPENCV="$(pkg-config --cflags-only-I opencv4 2>/dev/null | sed 's/-I/-isystem /g')"
[ -n "$OPENCV" ] || OPENCV="-isystem /usr/include/opencv4"

echo "Building..."
if ! g++ -std=c++20 -O1 -Wall -Wextra -Werror ${GARY_HOST_FLAGS:-} -I"$HERE/stubs" -I"$WORKSHOP_DIR" $OPENCV \
    "$DEVICE/qnx/gary_qnx.cpp" "$HERE/fake_impl.cpp" \
    -lopencv_imgcodecs -lopencv_imgproc -lopencv_core -lpthread -o "$OUT/gary" 2> "$OUT/build.log"; then
  grep -E "error" "$OUT/build.log" | head -20
  echo "Build FAILED"
  exit 1
fi

# The herd backpack quest is listed first, as it would be if it were the active
# quest. Alone, Gary must still finish the solo backpack quest behind it.
printf 't-bottle\tbottle\t10\tFind a bottle\nt-backpack\tbackpack\t10\tFind a backpack, with a friend\therd\nt-backpack-solo\tbackpack\t10\tFind a backpack\nt-laptop\tlaptop\t10\tFind a laptop\n' > "$OUT/quests.tsv"

# Six presses, placed by run number so the result does not depend on speed:
#   15 bottle | 45 backpack, no friend | 50 backpack again | 75 nothing
#   100 laptop + person | 115 laptop again
# The stand-in model speaks SSD, with class ids from coco_labels.txt.
SSD="--model models/ssd_mobilenet_v2_coco_quant_postprocess.tflite --labels models/coco_labels.txt --extra-model none"
echo "Running the scene..."
cd "$DEVICE"
GARY_FAKE_PRESSES=15,45,50,75,100,115 GARY_FAKE_QUIT=125 GARY_FAKE_MODEL_MS=2 GARY_FAKE_FRAME_MS=3 \
    "$OUT/gary" --mute $SSD --quests "$OUT/quests.tsv" --log "$OUT/journal.jsonl" < /dev/null > "$OUT/first.txt"
cp latency.csv "$OUT/latency.csv"
# A second start must rebuild its state from the journal alone.
GARY_FAKE_QUIT=3 GARY_FAKE_MODEL_MS=2 GARY_FAKE_FRAME_MS=3 \
    "$OUT/gary" --mute $SSD --quests "$OUT/quests.tsv" --log "$OUT/journal.jsonl" < /dev/null > "$OUT/second.txt"
# The power is pulled in the middle of a write: the journal ends in half a
# line. The next sniff must still land on a line of its own.
cp "$OUT/journal.jsonl" "$OUT/torn.jsonl"
printf '{"id": "gary-01-1-99", "ts": "20' >> "$OUT/torn.jsonl"
GARY_FAKE_PRESSES=15 GARY_FAKE_QUIT=20 GARY_FAKE_MODEL_MS=2 GARY_FAKE_FRAME_MS=3 \
    "$OUT/gary" --mute $SSD --quests "$OUT/quests.tsv" --log "$OUT/torn.jsonl" < /dev/null > "$OUT/third.txt"
rm -f latency.csv gary.pid

python3 - "$OUT" <<'PY'
import json, sys
out = sys.argv[1]
events = [json.loads(line) for line in open(out + "/journal.jsonl")]
got = [(e["type"], e.get("label"), e.get("quest_id"), e["friend"], e.get("new")) for e in events]
want = [
    ("discovery", "bottle", "t-bottle", False, True),            # a quest, alone
    ("discovery", "backpack", "t-backpack-solo", False, True),   # the herd quest is first, but only the solo one can be finished alone
    ("discovery", "backpack", None, False, False),               # only the herd quest is left: found, not completed
    ("miss", None, None, False, None),                           # nothing he can name
    ("discovery", "laptop", "t-laptop", True, True),             # a quest, with a friend in frame
    ("discovery", "laptop", None, True, False),                  # seen before
]
for i, (g, w) in enumerate(zip(got, want), 1):
    print("  %s  sniff %d: %s" % ("ok  " if g == w else "FAIL", i, g))
assert got == want, "\nwanted:\n" + "\n".join(map(str, want))
assert len({e["id"] for e in events}) == len(events), "event ids must be unique"
assert all(e["device"] == "gary-01" and e["ts"].endswith("Z") and "latency_ms" in e for e in events)
assert all("xp" not in e and "points" not in e for e in events), "the device never decides XP"
first, second = open(out + "/first.txt").read(), open(out + "/second.txt").read()
assert "Sniffs: 6 (5 discoveries, 3 new, 1 misses)" in first, first[-400:]
assert "Quests done: 3 of 4." in first
assert "That quest needs a friend in frame." in first
assert "3 kinds of thing in the journal. 4 quests, 3 done." in second, second[:300]
print("  ok    a restart rebuilds its state from the journal")

rows = [line.strip().split(",") for line in open(out + "/latency.csv")]
assert rows[0] == ["frame", "frame_to_decision_ms", "model_ms", "t_ms"], rows[0]
times = [float(r[3]) for r in rows[1:]]
assert len(times) > 100 and times == sorted(times), "t_ms must rise frame by frame"
print("  ok    latency.csv has %d frames with the time of each" % len(times))

lines = open(out + "/torn.jsonl").read().split("\n")
assert lines[-1] == "", "the journal must end with a newline"
bad = [i for i, line in enumerate(lines[:-1]) if not line.startswith("{") or not line.endswith("}")]
assert bad == [len(events)], "only the torn line may be unreadable, got %r" % bad
last = json.loads(lines[-2])
assert (last["type"], last["label"], last["new"]) == ("discovery", "bottle", False), last
print("  ok    after a torn line (power cut), the next sniff is on its own line")
print("Host test PASSED")
PY
