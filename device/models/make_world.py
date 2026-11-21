"""Build Gary's detector: YOLO-World with our own list of things, as TFLite.

YOLO-World is an open-vocabulary detector: we name the things, and the export
bakes that list into an ordinary TFLite model. Gary then detects exactly these.

Needs its own environment (torch, ultralytics, TensorFlow), not the device venv:
    uv venv --python 3.12 /tmp/yw && uv pip install --python /tmp/yw/bin/python ultralytics
    /tmp/yw/bin/python device/models/make_world.py

Writes models/gary_world.tflite and models/gary_labels.txt (class id = line).
Every name here must also be in contract/labels.json, except "person" (the friend).
Not run by the tests.
"""
import os
import shutil
import tempfile

from ultralytics import YOLO

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 320  # input pixels; smaller is faster on the Pi, larger sees smaller things

# The 80 COCO things the old SSD model knew ("person" first: it is the friend).
with open(os.path.join(HERE, "coco_labels.txt"), "r", encoding="utf-8") as f:
    COCO = [line.strip() for line in f if line.strip() not in ("", "n/a")]

# What a trail adds. Keep in step with contract/labels.json.
TRAIL = [
    "tree", "flower", "leaf", "mushroom", "rock", "pine cone", "squirrel", "chipmunk", "duck", "goose",
    "rabbit", "deer", "butterfly", "bridge", "trail sign", "picnic table", "trash can", "statue",
    "fountain", "playground", "street lamp", "mailbox", "canoe", "kayak", "waterfall",
]
NAMES = COCO + TRAIL

if __name__ == "__main__":
    work = os.path.join(tempfile.gettempdir(), "gary_world")  # downloads and export clutter
    os.makedirs(work, exist_ok=True)
    os.chdir(work)
    model = YOLO("yolov8s-worldv2.pt")
    model.set_classes(NAMES)
    # float32: int8 ruins the class scores, and 8-bit weights need ops older TFLite (QNX) lacks
    out = model.export(format="litert", imgsz=SIZE)
    shutil.copy(out, os.path.join(HERE, "gary_world.tflite"))
    with open(os.path.join(HERE, "gary_labels.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(NAMES) + "\n")
    print("wrote gary_world.tflite and gary_labels.txt:", len(NAMES), "things")
