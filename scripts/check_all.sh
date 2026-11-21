#!/bin/sh
# Run every test suite in the repo. Suites this machine cannot run are skipped,
# with the reason. Run it from anywhere, before every push:
#
#   sh scripts/check_all.sh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
PY="${PYTHON:-python3}"
failed=""
skipped=""

step() { printf '\n=== %s ===\n' "$1"; }
fail() { failed="$failed\n  - $1"; }
skip() { skipped="$skipped\n  - $1"; echo "skipped: $1"; }

step "Backend against the contract"
if "$PY" -c "import fastapi, httpx, pytest" 2>/dev/null; then
  (cd backend && "$PY" -m pytest -q) || fail "backend tests"
  if [ -z "${TEST_DATABASE_URL:-}" ]; then
    echo "(in memory only. Set TEST_DATABASE_URL to a throwaway database to run them on Postgres too)"
  fi
else
  skip "backend tests (pip install -r backend/requirements.txt)"
fi

step "Scout"
"$PY" scout/tests/test_scout.py || fail "scout tests"

step "Web"
if [ -d web/node_modules ]; then
  (cd web && npm test --silent) || fail "web tests"
  (cd web && npm run build --silent) || fail "web build"
else
  skip "web tests (cd web && npm install)"
fi

step "Device scripts: button, buzzer, sync, start and stop"
"$PY" device/tests/test_device.py || fail "device script tests"

step "QNX program on this machine, with stand-ins"
if command -v g++ >/dev/null 2>&1 && [ "$(uname -s)" = "Linux" ] \
   && [ -f /usr/include/opencv4/opencv2/imgcodecs.hpp ]; then
  sh device/qnx/host_test/run.sh || fail "device/qnx host test"
else
  skip "device/qnx host test (Linux with g++ and libopencv-dev)"
fi

step "Whole chain: scout, backend, sync, device"
if "$PY" -c "import fastapi, cv2, numpy" 2>/dev/null \
   && "$PY" -c "import ai_edge_litert" 2>/dev/null; then
  "$PY" scripts/e2e.py || fail "end-to-end check"
else
  skip "end-to-end check (pip install -r backend/requirements.txt -r device/requirements.txt)"
fi

echo
if [ -n "$skipped" ]; then printf 'Skipped:%b\n' "$skipped"; fi
if [ -n "$failed" ]; then
  printf 'FAILED:%b\n' "$failed"
  exit 1
fi
echo "All checks that could run here PASSED."
