"""How well does Gary's model name things? A photo benchmark.

    python3 bench_model.py --fetch            download about 10 photos per thing from Wikimedia Commons
    python3 bench_model.py                    score models/gary_world.tflite on them
    python3 bench_model.py --compare-ssd      the old SSD model on the same photos, side by side

Photos live in bench_photos/<thing>/*.jpg (not committed: they are other
people's photos, fetched again with --fetch). The folder name is the right
answer. Delete any photo that does not show its thing before you trust a score.

For each photo the model's boxes are read as a Sniff Test would read them:
the strongest thing that is not a person. A photo is a hit when that is the
right thing at or above the threshold. Writes bench_results.md.
"""
import argparse
import collections
import importlib.util
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTOS = os.path.join(HERE, "bench_photos")
THRESHOLDS = (0.3, 0.4, 0.5)
# the 25 trail things, and some old ones as a control
THINGS = ["tree", "flower", "leaf", "mushroom", "rock", "pine cone", "squirrel", "chipmunk", "duck", "goose",
          "rabbit", "deer", "butterfly", "bridge", "trail sign", "picnic table", "trash can", "statue", "fountain",
          "playground", "street lamp", "mailbox", "canoe", "kayak", "waterfall",
          "bench", "bicycle", "dog", "bird", "bottle", "cup", "backpack"]
# Commons search words, where the plain name finds the wrong photos
SEARCH = {"leaf": "autumn leaf close-up", "rock": "boulder rock outdoors", "trail sign": "hiking trail sign",
          "trash can": "public trash can park", "street lamp": "street lamp", "mailbox": "mailbox post box",
          "playground": "children playground equipment", "bottle": "water bottle", "cup": "coffee cup"}
AGENT = "gary-model-bench/0.1 (hackathon test script)"


def get(url):
    """GET with Commons' manners: a named client, and a wait when asked to slow down."""
    for attempt in range(5):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENT}), timeout=30).read()
        except urllib.error.HTTPError as err:
            if err.code != 429 or attempt == 4:
                raise
            time.sleep(int(err.headers.get("Retry-After") or 0) or 10 * (attempt + 1))


def fetch(things, per_thing):
    api = "https://commons.wikimedia.org/w/api.php?"
    for thing in things:
        folder = os.path.join(PHOTOS, thing)
        os.makedirs(folder, exist_ok=True)
        have = len([f for f in os.listdir(folder) if f.endswith(".jpg")])
        if have >= per_thing:
            continue
        query = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                 "gsrsearch": "filetype:bitmap " + SEARCH.get(thing, thing), "gsrlimit": per_thing * 3,
                 "prop": "imageinfo", "iiprop": "url|mime", "iiurlwidth": 640}
        pages = json.loads(get(api + urllib.parse.urlencode(query))).get("query", {}).get("pages", {})
        got = have
        for page in sorted(pages.values(), key=lambda p: p.get("index", 0)):
            info = (page.get("imageinfo") or [{}])[0]
            if info.get("mime") != "image/jpeg" or not info.get("thumburl") or got >= per_thing:
                continue
            try:
                data = get(info["thumburl"])
            except OSError:
                continue
            with open(os.path.join(folder, "%02d.jpg" % got), "wb") as f:
                f.write(data)
            got += 1
            time.sleep(1)  # be polite to Commons
        print("%-14s %d photos" % (thing, got))


def load_detector(model, labels):
    spec = importlib.util.spec_from_file_location("gary_device", os.path.join(HERE, "gary_device.py"))
    gd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gd)
    return gd.cv2, gd.Detector(model, labels), gd


def score(model, labels):
    """{thing: [(answer, score, right_score) per photo]}, and ms per photo."""
    cv2, det, _ = load_detector(model, labels)
    out, times = collections.defaultdict(list), []
    for thing in sorted(os.listdir(PHOTOS)):
        folder = os.path.join(PHOTOS, thing)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            img = cv2.imread(os.path.join(folder, name))
            if img is None:
                continue
            t = time.perf_counter()
            found = [f for f in det.detect(img, min_score=0.1) if f[0] != "person"]
            times.append((time.perf_counter() - t) * 1000)
            best = max(found, key=lambda f: f[1], default=(None, 0.0))
            right = max((f[1] for f in found if f[0] == thing), default=0.0)
            out[thing].append((best[0], best[1], right))
    return out, statistics.median(times) if times else 0.0, set(det.labels)


def rate(rows, thing, threshold):
    return sum(1 for answer, s, _ in rows if answer == thing and s >= threshold) / len(rows) if rows else 0.0


def report(results, ms, known, title, base=None):
    lines = ["## " + title, "", "Median %.0f ms a photo on this machine." % ms, "",
             "| Thing | Photos | Hit at 0.3 | 0.4 | 0.5 | Median score when right | Most common wrong answer |" + (" SSD at 0.5 |" if base else ""),
             "| --- | --- | --- | --- | --- | --- | --- |" + (" --- |" if base else "")]
    for thing in sorted(results, key=lambda t: -rate(results[t], t, 0.5)):
        rows = results[thing]
        if thing not in known:
            continue
        rights = [r for _, _, r in rows if r > 0]
        wrong = collections.Counter(("too faint" if a == thing else a or "nothing")
                                    for a, s, _ in rows if a != thing or s < 0.5).most_common(1)
        cells = [thing, str(len(rows))] + ["%d%%" % round(100 * rate(rows, thing, t)) for t in THRESHOLDS] + [
            "%.2f" % statistics.median(rights) if rights else "-", "%s (%d)" % wrong[0] if wrong else "-"]
        if base:
            cells.append("%d%%" % round(100 * rate(base[0][thing], thing, 0.5)) if thing in base[2] else "can't name it")
        lines.append("| " + " | ".join(cells) + " |")
    total = [r for t in results for r in results[t] if t in known]
    hits = sum(1 for t in results if t in known for a, s, _ in results[t] if a == t and s >= 0.5)
    lines += ["", "Overall at 0.5: %d of %d photos (%d%%)." % (hits, len(total), round(100 * hits / max(1, len(total))))]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Score Gary's model on labelled photos")
    ap.add_argument("--fetch", action="store_true", help="download photos from Wikimedia Commons first")
    ap.add_argument("--per-thing", type=int, default=10)
    ap.add_argument("--model", default=os.path.join(HERE, "models", "gary_world.tflite"))
    ap.add_argument("--labels", default=os.path.join(HERE, "models", "gary_labels.txt"))
    ap.add_argument("--compare-ssd", action="store_true", help="also score the old SSD model")
    args = ap.parse_args()
    if args.fetch:
        fetch(THINGS, args.per_thing)
    if not os.path.isdir(PHOTOS):
        sys.exit("No photos yet. Run: python3 bench_model.py --fetch")
    results, ms, known = score(args.model, args.labels)
    base = None
    if args.compare_ssd:
        base = score(os.path.join(HERE, "models", "ssd_mobilenet_v2_coco_quant_postprocess.tflite"),
                     os.path.join(HERE, "models", "coco_labels.txt"))
    text = report(results, ms, known, "Model benchmark: %s" % os.path.basename(args.model), base)
    if base:
        text += "\n\nSSD MobileNet v2: median %.0f ms a photo." % base[1]
    with open(os.path.join(HERE, "bench_results.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
