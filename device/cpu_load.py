#!/usr/bin/env python3
"""cpu_load.py - keep every CPU core busy for a while. Standard library only.

For the QNX numbers (issue #14): run this, then run Gary with --priority 20
and show that his button-to-answer time holds while the CPU is busy.

    python3 cpu_load.py --seconds 120 &        # four busy processes for two minutes
    ./qnx/build/gary --mute --priority 20

The busy processes run at the ordinary priority. On QNX the highest-priority
ready thread always runs first, so Gary at priority 20 is not kept waiting.
"""
import argparse
import os
import subprocess
import sys
import time


def main():
    ap = argparse.ArgumentParser(description="Load every CPU core for a while")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--procs", type=int, default=os.cpu_count() or 4, help="busy processes (default: one per core)")
    args = ap.parse_args()
    busy = [subprocess.Popen([sys.executable, "-c", "while True: pass"]) for _ in range(max(1, args.procs))]
    print("%d busy processes for %.0f seconds. Ctrl-C stops them early." % (len(busy), args.seconds), flush=True)
    try:
        time.sleep(args.seconds)
    except KeyboardInterrupt:
        pass
    finally:
        for proc in busy:
            proc.terminate()
        for proc in busy:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    print("load stopped", flush=True)


if __name__ == "__main__":
    main()
