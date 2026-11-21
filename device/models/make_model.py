"""Build Gary's detector: YOLOv8s trained on Open Images V7, as TFLite.

Open Images has 600 kinds of thing with hand-drawn boxes, nature included
(squirrel, duck, tree, butterfly), which COCO lacks. YOLO-World was tried
first: it called ducks "bird" and squirrels "bear" (bench_model.py).

Needs its own environment (torch, ultralytics), not the device venv:
    uv venv --python 3.12 /tmp/gm && uv pip install --python /tmp/gm/bin/python ultralytics
    /tmp/gm/bin/python device/models/make_model.py

Writes models/gary_detector.tflite and models/gary_labels.txt: one line per
model class, our name for it, or "n/a" for a class Gary ignores. Every name
but "person" must be in contract/labels.json. Not run by the tests.
"""
import os
import shutil
import tempfile

from ultralytics import YOLO

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 320  # input pixels; smaller is faster on the Pi, larger sees smaller things

# Open Images name -> ours, where they differ. Anyone in frame is the friend.
RENAME = {
    "man": "person", "woman": "person", "boy": "person", "girl": "person", "human face": "person",
    "cattle": "cow", "flying disc": "frisbee", "ski": "skis", "ball": "sports ball", "coffee cup": "cup",
    "mug": "cup", "doughnut": "donut", "houseplant": "potted plant", "kitchen & dining room table": "dining table",
    "television": "tv", "remote control": "remote", "computer keyboard": "keyboard", "mobile phone": "cell phone",
    "microwave oven": "microwave", "hair dryer": "hair drier", "street light": "street lamp",
    "waste container": "trash can",
}
# The 79 COCO things Gary has always known, and what Open Images adds for trails.
with open(os.path.join(HERE, "coco_labels.txt"), "r", encoding="utf-8") as f:
    COCO = {line.strip() for line in f if line.strip() not in ("", "n/a")}
NATURE = {"tree", "flower", "squirrel", "duck", "goose", "rabbit", "deer", "butterfly", "mushroom",
          "trash can", "street lamp"}
KEEP = COCO | NATURE


def our_names(model_names):
    out = []
    for name in model_names:
        ours = RENAME.get(name.lower(), name.lower())
        out.append(ours if ours in KEEP else "n/a")
    return out


if __name__ == "__main__":
    work = os.path.join(tempfile.gettempdir(), "gary_model")  # downloads and export clutter
    os.makedirs(work, exist_ok=True)
    os.chdir(work)
    model = YOLO("yolov8s-oiv7.pt")
    # float32: int8 ruins the class scores, and 8-bit weights need ops older TFLite (QNX) lacks
    out = model.export(format="litert", imgsz=SIZE)
    shutil.copy(out, os.path.join(HERE, "gary_detector.tflite"))
    names = our_names(model.names.values())
    with open(os.path.join(HERE, "gary_labels.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(names) + "\n")
    print("wrote gary_detector.tflite and gary_labels.txt:", len(set(names) - {"n/a"}), "things Gary names")
