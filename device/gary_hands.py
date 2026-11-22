#!/usr/bin/env python3
"""gary_hands.py - hand signals: a thumbs up or an OK sign is a Sniff Test, hands-free.

    your hand, close to the camera  ->  thumbs up, or OK  ->  lower it  ->  Gary sniffs

How it works (qnx/hand.hpp is the same, line for line):
    1. A palm detector finds the surest hand in the frame.
    2. A second model finds 21 points on that hand (knuckles, fingertips).
    3. Plain rules on those points say "like" (thumbs up), "ok", or nothing.
    4. A signal seen in 3 of 5 frames arms Gary. He sniffs once the hand has
       left the frame, so the hand never hides the thing or counts as a friend.

"Only my hands": the hand must be big in the frame (close to the camera, as
the wearer's own hand is). A hand across the room is too small to count. Gary
never works out whose hand it is: no one is identified.

The two models are Google's MediaPipe hand models (Apache-2.0), unchanged:
    models/hand_detector.tflite           the palm detector, 192 x 192
    models/hand_landmarks_detector.tflite the 21 points, 224 x 224
from https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task

Off unless Gary is started with --gestures. Nothing here is stored or uploaded.
"""
import math

PALM_SIZE = 192          # the palm detector's input, pixels
HAND_SIZE = 224          # the 21-point model's input, pixels
ANCHORS = 2016           # the palm detector's anchors
MIN_PALM_SCORE = 0.5
MIN_HAND_SCORE = 0.5
MIN_HAND = 0.10          # a palm narrower than this share of the frame's width is someone else's
WINDOW, NEED = 5, 3      # a signal in 3 of the last 5 frames arms Gary
GIVE_UP = 6.0            # seconds: armed this long with the hand still up, Gary forgets it
QUIET = 2.0              # seconds after a sniff before the next signal counts


def anchor(i):
    """Centre (x, y), 0..1, of the palm detector's anchor i: a 24 x 24 grid with
    2 anchors a cell, then a 12 x 12 grid with 6 (strides 8, 16, 16, 16)."""
    if i < 1152:
        cell, grid = i // 2, 24
    else:
        cell, grid = (i - 1152) // 6, 12
    return ((cell % grid) + 0.5) / grid, ((cell // grid) + 0.5) / grid


def sigmoid(v):
    return 1.0 / (1.0 + math.exp(-max(-50.0, min(50.0, v))))


def decode_palm(row, i):
    """One anchor's 18 raw numbers -> the palm, in 0..1 of the square the model
    saw: its box, the wrist and the middle finger's knuckle."""
    ax, ay = anchor(i)
    return {"cx": row[0] / PALM_SIZE + ax, "cy": row[1] / PALM_SIZE + ay,
            "w": row[2] / PALM_SIZE, "h": row[3] / PALM_SIZE,
            "wrist": (row[4] / PALM_SIZE + ax, row[5] / PALM_SIZE + ay),
            "middle": (row[8] / PALM_SIZE + ax, row[9] / PALM_SIZE + ay)}


def palm_roi(palm, side, pad_x, pad_y):
    """The square around the whole hand, in frame pixels: (cx, cy, size, rot).
    `side` is the padded square's width in pixels, `pad` what was added on the
    left and the top. rot turns the crop so the fingers point up."""
    (x0, y0), (x2, y2) = palm["wrist"], palm["middle"]
    rot = math.pi / 2 - math.atan2(-(y2 - y0), x2 - x0)
    rot -= 2 * math.pi * math.floor((rot + math.pi) / (2 * math.pi))
    w, h = palm["w"] * side, palm["h"] * side
    cx = palm["cx"] * side - pad_x + 0.5 * h * math.sin(rot)
    cy = palm["cy"] * side - pad_y - 0.5 * h * math.cos(rot)
    return cx, cy, 2.6 * max(w, h), rot


def roi_matrix(roi, out=HAND_SIZE):
    """The 2 x 3 matrix that takes a pixel of the out x out crop to the frame."""
    cx, cy, size, rot = roi
    s = size / out
    c, n, half = math.cos(rot) * s, math.sin(rot) * s, out / 2.0
    return [[c, -n, cx - half * c + half * n], [n, c, cy - half * n - half * c]]


def gesture(lm, rot):
    """lm: the 21 points as (x, y) in the crop. rot: the crop's turn (palm_roi).
    -> "like" (thumbs up), "ok", or None.

    Points: 0 wrist; thumb 1-4; index 5-8; middle 9-12; ring 13-16; pinky 17-20
    (each finger from its knuckle to its tip)."""
    def d(a, b):
        return math.hypot(lm[a][0] - lm[b][0], lm[a][1] - lm[b][1])
    palm = d(0, 9)
    if palm < 1e-6:
        return None
    # A finger is out when its tip is well past its middle joint, seen from the
    # wrist, and folded when the tip is nearer the wrist than that joint.
    reach = [d(tip, 0) / max(d(pip, 0), 1e-6) for pip, tip in ((6, 8), (10, 12), (14, 16), (18, 20))]
    out = [r > 1.15 for r in reach]
    folded = [r < 1.0 for r in reach]

    # OK: thumb tip on the index tip, the other three fingers out.
    if d(4, 8) < 0.30 * palm and out[1] and out[2] and not folded[3]:
        return "ok"

    # Thumbs up: four fingers folded, the thumb straight, clear of the fist, and
    # pointing up in the picture (not sideways, not down).
    if sum(folded) >= 3 and not any(out):
        straight = d(2, 4) > 0.85 * (d(2, 3) + d(3, 4))
        clear = d(4, 17) > 1.0 * palm and d(4, 5) > 0.45 * palm
        tx, ty = lm[4][0] - lm[2][0], lm[4][1] - lm[2][1]
        up = -(math.sin(rot) * tx + math.cos(rot) * ty)      # how far the thumb rises in the frame
        if straight and clear and up > 0.5 * math.hypot(tx, ty):
            return "like"
    return None


class Trigger:
    """Frames of (signal, hand in view) -> the moment to sniff.

    A signal in NEED of the last WINDOW frames arms Gary. He sniffs when the
    hand has then been out of view for WINDOW - NEED + 1 frames: by then the
    hand cannot hide the thing in front of him, or be taken for a friend."""

    def __init__(self, window=WINDOW, need=NEED, say=None):
        self.window, self.need, self.say = window, need, say
        self.seen, self.armed, self.armed_at, self.gone, self.quiet_until = [], None, 0.0, 0, 0.0

    def update(self, signal, hand, now):
        """signal: "like", "ok" or None. hand: a hand is in view. -> True: sniff now."""
        if self.armed:
            self.gone = 0 if hand else self.gone + 1
            if self.gone >= self.window - self.need + 1:
                self.armed, self.seen, self.quiet_until = None, [], now + QUIET
                return True
            if now - self.armed_at > GIVE_UP:
                self.armed, self.seen = None, []
                if self.say:
                    self.say("HAND: still up after %d s. Forgotten: show it again, then lower it." % GIVE_UP)
            return False
        self.seen = (self.seen + [signal])[-self.window:]
        if now < self.quiet_until or signal is None or self.seen.count(signal) < self.need:
            return False
        self.armed, self.armed_at, self.gone = signal, now, 0
        if self.say:
            self.say("HAND: %s. Lower your hand and Gary sniffs." % ("thumbs up" if signal == "like" else "OK"))
        return False


class HandReader:
    """The two models, on one frame at a time."""

    def __init__(self, palm_model, hand_model, interpreter, threads=3, min_hand=MIN_HAND):
        import cv2
        import numpy as np
        self.cv2, self.np, self.min_hand = cv2, np, min_hand
        self.palm = interpreter(model_path=palm_model, num_threads=threads)
        self.hand = interpreter(model_path=hand_model, num_threads=threads)
        for it in (self.palm, self.hand):
            it.allocate_tensors()
        self.palm_in = self.palm.get_input_details()[0]["index"]
        self.hand_in = self.hand.get_input_details()[0]["index"]
        outs = self.palm.get_output_details()
        boxes = [o for o in outs if int(o["shape"][-1]) == 18]
        scores = [o for o in outs if int(o["shape"][-1]) == 1]
        if len(boxes) != 1 or len(scores) != 1 or int(boxes[0]["shape"][1]) != ANCHORS:
            raise SystemExit("%s is not the palm detector this code expects." % palm_model)
        self.palm_boxes, self.palm_scores = boxes[0]["index"], scores[0]["index"]
        outs = self.hand.get_output_details()
        if len(outs) < 2 or int(outs[0]["shape"][-1]) != 63 or int(outs[1]["shape"][-1]) != 1:
            raise SystemExit("%s is not the hand model this code expects." % hand_model)
        self.hand_points, self.hand_flag = outs[0]["index"], outs[1]["index"]
        self.last = None  # (roi, points in the frame) of the last hand read, for --show

    def _tensor(self, bgr):
        rgb = self.cv2.cvtColor(bgr, self.cv2.COLOR_BGR2RGB)
        return self.np.ascontiguousarray(rgb.astype(self.np.float32)[self.np.newaxis, ...] / 255.0)

    def read(self, frame, true_w=None, true_h=None):
        """One BGR frame -> (signal, hand): signal is "like", "ok" or None; hand
        says a hand close enough to be the wearer's is in view.

        true_w, true_h: the camera's own frame size, when `frame` is a shrunk
        (even squeezed) copy of it, as the QNX Gary's frames are. The hand is
        measured in the camera's pixels, so a squeezed frame reads the same."""
        cv2, np = self.cv2, self.np
        self.last = None
        fh, fw = frame.shape[:2]
        tw, th = float(true_w or fw), float(true_h or fh)
        side = max(tw, th)
        pad_x, pad_y = (side - tw) / 2.0, (side - th) / 2.0
        # The camera's picture, whole and unsqueezed, in the middle of a black square.
        pw = max(1, int(round(tw * PALM_SIZE / side)))
        ph = max(1, int(round(th * PALM_SIZE / side)))
        ox, oy = (PALM_SIZE - pw) // 2, (PALM_SIZE - ph) // 2
        canvas = np.zeros((PALM_SIZE, PALM_SIZE, 3), dtype=np.uint8)
        canvas[oy:oy + ph, ox:ox + pw] = cv2.resize(frame, (pw, ph))
        self.palm.set_tensor(self.palm_in, self._tensor(canvas))
        self.palm.invoke()
        scores = self.palm.get_tensor(self.palm_scores)[0, :, 0]
        i = int(np.argmax(scores))
        if sigmoid(float(scores[i])) < MIN_PALM_SCORE:
            return None, False
        palm = decode_palm([float(v) for v in self.palm.get_tensor(self.palm_boxes)[0, i]], i)
        if max(palm["w"], palm["h"]) * side < self.min_hand * tw:
            return None, False  # too small: not the wearer's hand
        roi = palm_roi(palm, side, pad_x, pad_y)
        m = roi_matrix(roi)  # crop -> the camera's pixels; then -> this frame's pixels
        fx, fy = fw / tw, fh / th
        matrix = np.array([[v * fx for v in m[0]], [v * fy for v in m[1]]], dtype=np.float32)
        crop = cv2.warpAffine(frame, matrix, (HAND_SIZE, HAND_SIZE),
                              flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_CONSTANT)
        self.hand.set_tensor(self.hand_in, self._tensor(crop))
        self.hand.invoke()
        if float(self.hand.get_tensor(self.hand_flag)[0][0]) < MIN_HAND_SCORE:
            return None, False
        raw = self.hand.get_tensor(self.hand_points)[0]
        lm = [(float(raw[3 * k]), float(raw[3 * k + 1])) for k in range(21)]
        self.last = (roi, [(matrix[0][0] * x + matrix[0][1] * y + matrix[0][2],
                            matrix[1][0] * x + matrix[1][1] * y + matrix[1][2]) for x, y in lm])
        return gesture(lm, roi[3]), True
