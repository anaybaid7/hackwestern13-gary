#!/bin/sh
# live.sh - watch what Gary sees, with his boxes, in a browser.
#
#   1. start Gary with GARY_LIVE set (start_gary.sh does it when GARY_LIVE is in gary.env):
#        GARY_LIVE=live/frame.jpg ./qnx/build/gary
#   2. sh qnx/live.sh            then open http://<pi address>:8090 on the laptop
#
# Only frames are served, never stored: each one replaces the last.
cd "$(dirname "$0")/.." || exit 1
mkdir -p live
cat > live/index.html <<'EOF'
<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Gary sees</title>
<style>body{margin:0;background:#14202b;color:#fff4da;font:16px monospace;text-align:center}
img{max-width:100%;max-height:92vh}</style>
<p>What Gary sees</p><img id="f" alt="Gary's camera, with what he recognises boxed">
<script>
const img = document.getElementById('f')
function next() { const n = new Image(); n.onload = () => { img.src = n.src; setTimeout(next, 150) }
  n.onerror = () => setTimeout(next, 500); n.src = 'frame.jpg?' + Date.now() }
next()
</script>
EOF
echo "Live view on port 8090. Ctrl-C to stop."
cd live && exec python3 -m http.server 8090
