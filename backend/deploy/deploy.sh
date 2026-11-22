#!/bin/sh
# deploy.sh - put Gary's backend and web page on a Vultr machine (issue #22).
#
#   sh backend/deploy/deploy.sh root@203.0.113.10
#
# Run it on your laptop, from anywhere in the repo. Run it again to update.
# With a key that is not your default one:
#
#   GARY_SSH="ssh -i $HOME/.ssh/gary_key" sh backend/deploy/deploy.sh root@203.0.113.10
#
#   1. builds the web page here, so the server needs no Node
#   2. copies backend/, contract/ and web/dist to the server
#   3. on the server: a Python venv, the requirements, a service on port 80,
#      and port 80 opened in the firewall (setup.sh)
#   4. checks http://<address>/api/health
#
# Secrets never travel with the code. They live in /opt/gary/.env on the
# server. Edit that file there, then: systemctl restart gary
set -e
TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  echo "usage: sh backend/deploy/deploy.sh root@<server address>"
  exit 2
fi
SSH="${GARY_SSH:-ssh}"   # may carry options, so it is used unquoted below
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "1. Building the web page"
if [ "${SKIP_WEB_BUILD:-}" != 1 ]; then
  (
    cd web
    # install when there is nothing yet, or when package-lock.json has changed
    # since the last install (a new library, such as the 3D map's)
    if [ ! -f node_modules/.package-lock.json ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
      npm install
    fi
    npm run build
  )
fi
if [ ! -f web/dist/index.html ]; then
  echo "web/dist is missing. Run: cd web && npm install && npm run build"
  exit 1
fi

echo "2. Copying the code to $TARGET"
# Only what the server needs: no .env, no tests, no journal, no node_modules.
# The three scout files are for picks (backend/picks.py runs the TinyFish code).
# COPYFILE_DISABLE stops macOS from adding ._ files to the archive, and
# --no-xattrs its own file attributes, which the server's tar warns about.
COPYFILE_DISABLE=1 tar --no-xattrs -czf - \
    --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.env' --exclude='backend/tests' \
    backend contract web/dist scout/scout.py scout/personal.py scout/sources.json \
  | $SSH "$TARGET" 'rm -rf /opt/gary/app.new && mkdir -p /opt/gary/app.new && tar -xzf - -C /opt/gary/app.new'

echo "3. Setting up the server"
$SSH "$TARGET" 'sh /opt/gary/app.new/backend/deploy/setup.sh'

echo "4. Checking from here"
HOST="${TARGET#*@}"
if curl -fsS --max-time 10 "http://$HOST/api/health"; then
  echo
  echo "Gary is at http://$HOST/"
  echo "Next: put the keys and DATABASE_URL in /opt/gary/.env on the server, then: ssh $TARGET systemctl restart gary"
else
  echo
  echo "The server says Gary is up, but http://$HOST/api/health did not answer from here."
  echo "Check the Vultr firewall group for this instance: port 80 must be open."
  exit 1
fi
