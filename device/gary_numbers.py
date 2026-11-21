#!/usr/bin/env python3
"""gary_numbers.py - turn one run of Gary into a table for the judges (issue #14).
Standard library only, so it runs on QNX's Python.

(Not called numbers.py: that name would hide Python's own numbers module from
every script in this folder, numpy included.)

Gary writes latency.csv when he stops, and every sniff in journal.jsonl carries
its button-to-answer time. This script reads both and prints one table row.

    # 1. a normal run: start Gary, press the button ten times, stop him (q + Enter)
    python3 gary_numbers.py --label "QNX, normal" --append ../docs/qnx-numbers.md

    # 2. the same with a busy CPU and a real-time priority
    python3 cpu_load.py --seconds 120 &
    ./qnx/build/gary --mute --priority 20      # ten presses, then q + Enter
    python3 gary_numbers.py --label "QNX, --priority 20, CPU loaded" --append ../docs/qnx-numbers.md

Other checks

    python3 gary_numbers.py --check-journal     after pulling the power: is the journal intact?
    python3 gary_numbers.py --threads           while Gary runs on QNX: his threads and priorities
    python3 gary_numbers.py --temp              the Pi's temperature

"Frame" means the frame reaching Gary. Time inside the camera and the USB link
is not included.
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HEADER = ("| Run | Frames | Frames per second | Model, mean | Frame to decision, p50 | p95 | max "
          "| Sniffs | Button to answer, p50 | p95 | max |")
RULE = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"


def percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct / 100.0 * (len(ordered) - 1))))]


def read_latency(path):
    """latency.csv -> {"frames", "fps", "model_ms", "p50", "p95", "max", "seconds"}."""
    decide, model, times = [], [], []
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 3:
                continue
            try:
                decide.append(float(parts[1]))
                model.append(float(parts[2]))
                if len(parts) > 3:
                    times.append(float(parts[3]))
            except ValueError:
                continue
    if not decide:
        raise ValueError("%s has no frames in it" % path)
    seconds = (times[-1] - times[0]) / 1000.0 if len(times) > 1 else 0.0
    return {
        "frames": len(decide),
        "fps": (len(times) - 1) / seconds if seconds > 0 else None,  # None: an old file with no t_ms column
        "model_ms": sum(model) / len(model),
        "p50": percentile(decide, 50), "p95": percentile(decide, 95), "max": max(decide),
        "seconds": seconds,
        "columns": header,
    }


def read_events(path):
    """journal.jsonl -> (events, damaged line count). A line cut short by a power
    cut is damaged; it is skipped, and nothing else is lost."""
    events, damaged = [], 0
    if not os.path.exists(path):
        return events, damaged
    with open(path, "rb") as f:
        for raw in f.read().split(b"\n"):
            if not raw.strip():
                continue
            try:
                event = json.loads(raw.decode("utf-8"))
            except ValueError:
                damaged += 1
                continue
            if isinstance(event, dict) and event.get("id") and event.get("type"):
                events.append(event)
            else:
                damaged += 1
    return events, damaged


def parse_ts(text):
    try:
        return datetime.datetime.fromisoformat(str(text).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def sniff_times(events, run_end, run_seconds, last=None):
    """Button-to-answer times of the sniffs that belong to one run.

    The run ended when latency.csv was written and lasted run_seconds, so its
    sniffs are the ones stamped inside that window. `last` overrides this with
    the newest N sniffs.
    """
    sniffs = [e for e in events if e.get("type") in ("discovery", "miss") and e.get("latency_ms") is not None]
    if last:
        return [float(e["latency_ms"]) for e in sniffs[-last:]]
    start = run_end - run_seconds - 3.0
    picked = []
    for e in sniffs:
        when = parse_ts(e.get("ts"))
        if when is not None and start <= when <= run_end + 3.0:
            picked.append(float(e["latency_ms"]))
    return picked


def table_row(label, lat, sniffs):
    def ms(value):
        return "%.0f ms" % value

    fps = "%.1f" % lat["fps"] if lat["fps"] is not None else "n/a"
    cells = [label, str(lat["frames"]), fps, ms(lat["model_ms"]), ms(lat["p50"]), ms(lat["p95"]), ms(lat["max"])]
    if sniffs:
        cells += [str(len(sniffs)), ms(percentile(sniffs, 50)), ms(percentile(sniffs, 95)), ms(max(sniffs))]
    else:
        cells += ["0", "n/a", "n/a", "n/a"]
    return "| " + " | ".join(cells) + " |"


def append_row(path, row):
    """Add the row to the table in docs/qnx-numbers.md, creating the table if needed."""
    text = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    if HEADER not in text:
        text = (text.rstrip("\n") + "\n\n" if text.strip() else "") + HEADER + "\n" + RULE + "\n"
    lines = text.rstrip("\n").split("\n")
    at = lines.index(HEADER) + 1          # the rule line under the header
    while at + 1 < len(lines) and lines[at + 1].startswith("|"):
        at += 1                           # the last row of this table
    lines.insert(at + 1, row)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def temperature():
    """The board temperature as text, or None."""
    for path in ("/dev/thermal",):  # QNX
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read(200).strip()
            if text:
                return "%s: %s" % (path, text)
        except OSError:
            pass
    try:  # Linux
        with open("/sys/class/thermal/thermal_zone0/temp", "r", encoding="utf-8") as f:
            return "%.1f C" % (int(f.read().strip()) / 1000.0)
    except (OSError, ValueError):
        return None


def threads():
    """QNX: the lines of `pidin` that mention gary, with the header line."""
    if not shutil.which("pidin"):
        return None
    out = subprocess.run(["pidin"], capture_output=True, text=True, timeout=20).stdout.splitlines()
    return "\n".join(out[:1] + [line for line in out[1:] if "gary" in line])


def main(argv=None):
    ap = argparse.ArgumentParser(description="One run of Gary as a table row for the judges")
    ap.add_argument("--dir", default=HERE, help="the device folder (latency.csv, journal.jsonl)")
    ap.add_argument("--label", default="run", help='what this run was, for example "QNX, normal"')
    ap.add_argument("--last", type=int, help="use the newest N sniffs instead of the ones inside the run")
    ap.add_argument("--append", metavar="FILE", help="also add the row to this markdown file")
    ap.add_argument("--check-journal", action="store_true", help="count intact and damaged journal lines")
    ap.add_argument("--threads", action="store_true", help="QNX: show Gary's threads and priorities")
    ap.add_argument("--temp", action="store_true", help="show the board temperature")
    args = ap.parse_args(argv)
    journal = os.path.join(args.dir, "journal.jsonl")

    if args.check_journal:
        events, damaged = read_events(journal)
        kinds = {}
        for e in events:
            kinds[e["type"]] = kinds.get(e["type"], 0) + 1
        detail = ", ".join("%d %s" % (n, k) for k, n in sorted(kinds.items())) or "no events"
        if damaged == 0:
            print("Journal intact: %d events (%s), 0 damaged lines." % (len(events), detail))
        else:
            print("Journal: %d events (%s) are intact. %d damaged line%s: the write that was in "
                  "progress when the power went. Nothing else is lost."
                  % (len(events), detail, damaged, "" if damaged == 1 else "s"))
        return 0
    if args.threads:
        out = threads()
        print(out if out else "pidin is not on this machine. On QNX, run: pidin | grep gary")
        return 0
    if args.temp:
        print(temperature() or "No temperature sensor found here. On QNX: cat /dev/thermal")
        return 0

    latency = os.path.join(args.dir, "latency.csv")
    if not os.path.exists(latency):
        sys.exit("No latency.csv in %s. Gary writes it when he stops: run him, press the button a few "
                 "times, then quit with q + Enter." % args.dir)
    try:
        lat = read_latency(latency)
    except ValueError as exc:
        sys.exit(str(exc))
    events, _ = read_events(journal)
    sniffs = sniff_times(events, os.path.getmtime(latency), lat["seconds"], args.last)
    row = table_row(args.label, lat, sniffs)
    print(HEADER)
    print(RULE)
    print(row)
    if lat["fps"] is None:
        print("\nNote: this latency.csv has no t_ms column, so frames per second is not known. "
              "Rebuild Gary and run again.")
    if not sniffs:
        print("\nNote: no sniffs were found inside this run. Press the button during the run, "
              "or pass --last 10 to use the newest ten.")
    if args.append:
        try:
            append_row(args.append, row)
            print("\nAdded to %s" % args.append)
        except OSError as exc:
            print("\nCould not write %s (%s). Copy the row above into docs/qnx-numbers.md by hand."
                  % (args.append, exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
