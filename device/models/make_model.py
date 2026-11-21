"""Build Gary's detector: YOLOv8s trained on Open Images V7, as TFLite.

Open Images has 600 kinds of thing with hand-drawn boxes, nature included
(squirrel, duck, tree, butterfly), which COCO lacks. YOLO-World was tried
first: it called ducks "bird" and squirrels "bear" (bench_model.py).

Needs its own environment (torch, ultralytics), not the device venv:
    uv venv --python 3.12 /tmp/gm && uv pip install --python /tmp/gm/bin/python ultralytics
    /tmp/gm/bin/python device/models/make_model.py

Gary runs it beside the SSD model (everyday things and people), and keeps
only its nature names: on everyday things in a webcam frame SSD is far better.

Writes models/gary_detector.tflite and models/gary_nature_labels.txt: one line
per model class, our name for it, or "n/a" for a class Gary ignores. Every
name must be in contract/labels.json. Not run by the tests.
"""
import os
import shutil
import tempfile

from ultralytics import YOLO

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 320  # input pixels; smaller is faster on the Pi, larger sees smaller things

# Open Images name -> ours, where they differ.
RENAME = {"street light": "street lamp", "waste container": "trash can"}
# What this model adds to SSD's 80 things.
NATURE = {"tree", "flower", "squirrel", "duck", "goose", "rabbit", "deer", "butterfly", "mushroom",
          "trash can", "street lamp"}


def our_names(model_names):
    out = []
    for name in model_names:
        ours = RENAME.get(name.lower(), name.lower())
        out.append(ours if ours in NATURE else "n/a")
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
    with open(os.path.join(HERE, "gary_nature_labels.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(names) + "\n")
    print("wrote gary_detector.tflite and gary_nature_labels.txt:", len(set(names) - {"n/a"}), "things")
