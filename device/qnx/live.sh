#!/bin/sh
# live.sh - watch what Gary sees, with his boxes, in a browser.
#
#   1. start Gary with GARY_LIVE set (start_gary.sh does it when GARY_LIVE is in gary.env):
#        GARY_LIVE=live/frame.jpg ./qnx/build/gary
#   2. sh qnx/live.sh            then open http://<pi address>:8090 on the laptop
#
# With the backend on the Pi (GARY_BACKEND in gary.env) this is not needed:
# start_gary.sh has the backend serve the same page at http://<pi>:8800/live/
#
# Only frames are served, never stored: each one replaces the last.
cd "$(dirname "$0")/.." || exit 1
mkdir -p live
cp qnx/live.html live/index.html
echo "Live view on port 8090. Ctrl-C to stop."
cd live && exec python3 -m http.server 8090
