"""Explorers nearby: who else is out with a Gary, close to you or on your quest.

Off unless a person switches it on in Settings. While it is on, their page
sends where they are every few seconds, and gets back the others who have it
on too. The rules here are the whole of the privacy story:

  - Nothing is stored. Positions live in this process's memory only, and one
    that has not been refreshed for STALE seconds is dropped.
  - Positions are rounded to about 100 m before they are kept or shown.
    (GARY_NEARBY_ROUND=5 on the server makes that about 1 m: a showcase
    setting, so people standing in one room can be told apart. The page
    says so on the map when it is on.)
  - Nobody is named. A device makes up a random id; others only ever see a
    tag made from it, which the page turns into a goat name. The id itself,
    which is what lets a device move or remove its own dot, is never sent out.
  - You only see others while you share: asking is the same call as telling.
  - Only people near you (RANGE_M) or on the same quest are returned.
"""
import hashlib
import math
import os
import threading
import time

STALE = 45.0        # seconds without a refresh before a dot disappears
RANGE_M = 2000.0    # how near "nearby" is
ROUND = 3           # decimal places kept: about 110 m north-south
MOST = 500          # dots kept at once; the oldest goes first

_lock = threading.Lock()
_spots = {}         # id -> {"lat", "lon", "quest", "at"}


def tag_of(device_id):
    return hashlib.sha256(("nearby:" + device_id).encode("utf-8")).hexdigest()[:8]


def metres(a_lat, a_lon, b_lat, b_lon):
    """Distance between two points, good to a few metres at city scale."""
    k = math.pi / 180
    x = (b_lon - a_lon) * k * math.cos((a_lat + b_lat) / 2 * k)
    y = (b_lat - a_lat) * k
    return math.hypot(x, y) * 6371000


def valid_id(device_id):
    return isinstance(device_id, str) and 16 <= len(device_id) <= 64 and device_id.isalnum()


def places():
    """Decimal places kept: ROUND, or GARY_NEARBY_ROUND (2 to 6) for a showcase."""
    try:
        return min(6, max(2, int(os.environ.get("GARY_NEARBY_ROUND") or ROUND)))
    except ValueError:
        return ROUND


def rounded_m():
    """How coarse a shown position is, in metres."""
    return round(111000 / 10 ** places(), 1)


def share(device_id, lat, lon, quest=None, now=None):
    """Put this device on the map and return the explorers near it."""
    now = time.time() if now is None else now
    lat, lon = round(float(lat), places()), round(float(lon), places())
    with _lock:
        for key in [k for k, spot in _spots.items() if now - spot["at"] > STALE]:
            del _spots[key]
        _spots[device_id] = {"lat": lat, "lon": lon, "quest": quest or None, "at": now}
        while len(_spots) > MOST:
            del _spots[min(_spots, key=lambda k: _spots[k]["at"])]
        others = []
        for key, spot in _spots.items():
            if key == device_id:
                continue
            far = metres(lat, lon, spot["lat"], spot["lon"])
            same = bool(quest) and spot["quest"] == quest
            if far <= RANGE_M or same:
                others.append({"tag": tag_of(key), "lat": spot["lat"], "lon": spot["lon"],
                               "same_quest": same, "metres": int(round(far, -1 if places() <= 3 else 0)),
                               "seconds_ago": int(now - spot["at"])})
    others.sort(key=lambda o: o["metres"])
    return others


def leave(device_id):
    with _lock:
        return _spots.pop(device_id, None) is not None


def forget_all():
    with _lock:
        _spots.clear()
