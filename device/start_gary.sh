#!/bin/sh
# start_gary.sh - run Gary as a field device: no keyboard, no screen.
#
# Starts three programs in the background. They keep running after you log
# out, and Gary is started again if he ever stops.
#
#   Gary        the camera, the model and the Sniff Test
#   sync.py     uploads the journal, fetches quests (only if GARY_API is set)
#   gary_io.py  the button and the buzzer
#
#   sh start_gary.sh            start whatever is not running yet
#   sh start_gary.sh --fresh    stop, set the old journal aside, start: a clean run
#   sh start_gary.sh status     what is running, and Gary's last lines
#   sh start_gary.sh stop       stop all three (the same as: sh stop_gary.sh)
#
# Settings: gary.env beside this script (copy gary.env.example and edit it).
# Logs: logs/gary.log, logs/sync.log, logs/io.log.
#
# Works with the QNX build (qnx/build/gary) and, when that is absent, with the
# Python version. Plain POSIX sh, so it runs under QNX's shell.
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1
[ -f gary.env ] && . ./gary.env
: "${GARY_FLAGS=--mute}"
# GARY_SOUND=on in gary.env: play the sound clips through a speaker (a USB
# speaker on the Pi). Off by default: the buzzer is always there.
if [ "${GARY_SOUND:-off}" = on ]; then
  GARY_FLAGS="$(printf '%s' "$GARY_FLAGS" | sed 's/--mute//g')"
fi
# GARY_LIVE=live/frame.jpg in gary.env: Gary writes what he sees, with boxes,
# for the live view (sh qnx/live.sh). Off unless set.
[ -n "${GARY_LIVE:-}" ] && export GARY_LIVE
: "${GARY_BUTTON_PIN:=17}"
: "${GARY_BUZZER_PIN:=27}"
: "${GARY_PYTHON:=python3}"
: "${GARY_START_WAIT:=3}"   # seconds to wait before reporting who came up
PYTHONUNBUFFERED=1
export PYTHONUNBUFFERED
mkdir -p logs

# Process ids are kept where a reboot wipes them (memory, not disk). After a
# power cut a pid file left on disk can name some other program; these cannot.
prefix=""
for base in /dev/shmem /dev/shm /tmp; do
  if [ -d "$base" ] && [ -w "$base" ]; then
    prefix="$base/gary-$(printf '%s' "$DIR" | cksum | cut -d' ' -f1)-"
    break
  fi
done
[ -n "$prefix" ] || prefix="$DIR/logs/"
LOOP_PID="${prefix}loop.pid"
SYNC_PID="${prefix}sync.pid"
IO_PID="${prefix}io.pid"

alive() { [ -s "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

stop_one() {  # $1 = pid file, $2 = what to call it
  if alive "$1"; then
    kill "$(cat "$1")" 2>/dev/null
    echo "$2: stopped"
  fi
  rm -f "$1"
}

stop_all() {
  was_looping=no
  alive "$LOOP_PID" && was_looping=yes
  # The loop stops Gary itself when it is told to stop.
  stop_one "$LOOP_PID" "Gary"
  stop_one "$IO_PID" "button and buzzer"
  stop_one "$SYNC_PID" "sync"
  if [ "$was_looping" = yes ]; then
    # Give Gary a moment to finish: he writes latency.csv and removes gary.pid.
    n=0
    while [ -f gary.pid ] && [ "$n" -lt 8 ]; do
      sleep 1
      n=$((n + 1))
    done
  elif [ -f gary.pid ]; then
    echo "A gary.pid is here, but Gary was not started by this script. If he is running in a terminal, stop him there with q + Enter."
  fi
}

status() {
  if alive "$LOOP_PID" && alive gary.pid; then
    echo "Gary: up (pid $(cat gary.pid))"
  elif alive "$LOOP_PID"; then
    echo "Gary: NOT up. He is being restarted every few seconds. Last lines of logs/gary.log:"
    tail -n 6 logs/gary.log 2>/dev/null | sed 's/^/    /'
  else
    echo "Gary: not running"
  fi
  if alive "$IO_PID"; then
    echo "button and buzzer: up"
  elif [ -s logs/io.log ]; then
    echo "button and buzzer: not running. Last line of logs/io.log:"
    tail -n 1 logs/io.log | sed 's/^/    /'
  else
    echo "button and buzzer: not running"
  fi
  if alive "$SYNC_PID"; then
    echo "sync: up, $(tail -n 1 logs/sync.log 2>/dev/null)"
  elif [ -z "$GARY_API" ]; then
    echo "sync: off (GARY_API is not set in gary.env). Sniffs are kept in journal.jsonl"
  else
    echo "sync: not running"
  fi
  if [ -f journal.jsonl ]; then
    echo "journal: $(wc -l < journal.jsonl | tr -d ' ') lines"
  fi
}

case "${1:-}" in
  stop)
    stop_all
    exit 0
    ;;
  status)
    status
    exit 0
    ;;
  --fresh)
    stop_all > /dev/null
    stamp="$(date +%Y%m%d-%H%M%S)"
    if [ -f journal.jsonl ]; then
      mv journal.jsonl "journal.$stamp.bak"
      echo "Fresh run: the old journal is now journal.$stamp.bak"
    fi
    rm -f sync.state
    ;;
  "") ;;
  *)
    echo "usage: sh start_gary.sh [--fresh | status | stop]"
    exit 2
    ;;
esac

# Which Gary: the QNX build if it is here, else the Python version.
if [ -n "${GARY_CMD:-}" ]; then
  gary="$GARY_CMD"
elif [ -x qnx/build/gary ]; then
  gary="./qnx/build/gary"
elif [ -x venv/bin/python3 ]; then
  gary="venv/bin/python3 gary_device.py"
else
  gary="$GARY_PYTHON gary_device.py"
fi

if alive "$LOOP_PID"; then
  echo "Gary: already running"
else
  rm -f gary.pid  # a leftover from before a power cut must not be trusted
  (
    trap '' HUP   # logging out must not stop the loop (Gary reads HUP as "reload the quests")
    child=""
    trap '[ -n "$child" ] && kill "$child" 2>/dev/null; exit 0' TERM INT
    while :; do
      # shellcheck disable=SC2086
      $gary $GARY_FLAGS < /dev/null >> logs/gary.log 2>&1 &
      child=$!
      wait "$child"
      child=""
      rm -f gary.pid
      echo "$(date '+%H:%M:%S') Gary stopped. Starting him again in 3 seconds." >> logs/gary.log
      sleep 3 &
      wait $!
    done
  ) > /dev/null 2>&1 &
  echo $! > "$LOOP_PID"
  echo "Gary: starting ($gary $GARY_FLAGS)"
fi

if alive "$IO_PID"; then
  echo "button and buzzer: already running"
else
  (
    trap '' HUP
    # shellcheck disable=SC2086
    exec $GARY_PYTHON gary_io.py --button-pin "$GARY_BUTTON_PIN" --buzzer-pin "$GARY_BUZZER_PIN" \
      ${GARY_IO_FLAGS:-} < /dev/null >> logs/io.log 2>&1
  ) &
  echo $! > "$IO_PID"
  echo "button and buzzer: starting (button GPIO$GARY_BUTTON_PIN, buzzer GPIO$GARY_BUZZER_PIN)"
fi

if [ -z "${GARY_API:-}" ]; then
  echo "sync: off. Set GARY_API in gary.env to upload. Until then sniffs are kept in journal.jsonl"
elif alive "$SYNC_PID"; then
  echo "sync: already running"
else
  (
    trap '' HUP
    exec $GARY_PYTHON sync.py --api "$GARY_API" < /dev/null >> logs/sync.log 2>&1
  ) &
  echo $! > "$SYNC_PID"
  echo "sync: starting, with $GARY_API"
fi

sleep "$GARY_START_WAIT"
echo
status
