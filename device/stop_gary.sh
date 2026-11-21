#!/bin/sh
# stop_gary.sh - stop Gary, sync.py and gary_io.py, if start_gary.sh started them.
# Gary finishes cleanly: his journal is already on disk, and he writes
# latency.csv on the way out.
exec sh "$(dirname "$0")/start_gary.sh" stop
