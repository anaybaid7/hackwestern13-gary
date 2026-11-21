#!/bin/sh
# setup.sh - runs on the server, as root. deploy.sh calls it. Safe to run again.
#
# Layout on the server:
#   /opt/gary/app     the code (backend/, contract/, web/dist)
#   /opt/gary/venv    Python packages
#   /opt/gary/.env    secrets: DATABASE_URL, SCOUT_KEY, GARY_ADMIN_KEY. Never in git
set -e
HOME_DIR="${GARY_HOME:-/opt/gary}"
PORT="${GARY_PORT:-80}"
if [ "$(id -u)" != 0 ]; then
  echo "Run this as root."
  exit 1
fi
if [ ! -d "$HOME_DIR/app.new/backend" ]; then
  echo "$HOME_DIR/app.new is missing. Run deploy.sh from your laptop; it copies the code first."
  exit 1
fi

if ! python3 -c "import venv, ensurepip" 2>/dev/null; then
  echo "Installing python3-venv"
  DEBIAN_FRONTEND=noninteractive apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv
fi
id gary > /dev/null 2>&1 || useradd --system --home "$HOME_DIR" --shell /usr/sbin/nologin gary

# Swap the new code in. The previous copy is kept as app.old.
rm -rf "$HOME_DIR/app.old"
[ -d "$HOME_DIR/app" ] && mv "$HOME_DIR/app" "$HOME_DIR/app.old"
mv "$HOME_DIR/app.new" "$HOME_DIR/app"

[ -d "$HOME_DIR/venv" ] || python3 -m venv "$HOME_DIR/venv"
"$HOME_DIR/venv/bin/pip" install -q --upgrade pip
"$HOME_DIR/venv/bin/pip" install -q -r "$HOME_DIR/app/backend/requirements.txt"

if [ ! -f "$HOME_DIR/.env" ]; then
  cat > "$HOME_DIR/.env" <<'ENV'
# Gary's secrets. One KEY=value per line, no quotes. After a change: systemctl restart gary
# DATABASE_URL=postgres://tsdbadmin:PASSWORD@HOST.tsdb.cloud.timescale.com:PORT/tsdb?sslmode=require
# SCOUT_KEY=choose-a-long-random-string
# GARY_ADMIN_KEY=choose-another
# GARY_NAP_SECONDS=60        (shows a nap after a minute. Leave it out for the three-minute demo)
ENV
  chmod 600 "$HOME_DIR/.env"
fi
chown -R gary:gary "$HOME_DIR"

START="$HOME_DIR/venv/bin/uvicorn app:app --host 0.0.0.0 --port $PORT"
if command -v systemctl > /dev/null 2>&1 && [ -d /run/systemd/system ]; then
  cat > /etc/systemd/system/gary.service <<UNIT
[Unit]
Description=Gary the Goat: API and web page
After=network-online.target
Wants=network-online.target

[Service]
User=gary
WorkingDirectory=$HOME_DIR/app/backend
EnvironmentFile=-$HOME_DIR/.env
ExecStart=$START
AmbientCapabilities=CAP_NET_BIND_SERVICE
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable -q gary
  systemctl restart gary
else
  echo "No systemd on this machine, so nothing was started. Start Gary by hand:"
  echo "  cd $HOME_DIR/app/backend && $START"
  exit 0
fi

# Vultr's Ubuntu images come with the ufw firewall on and only SSH open.
if command -v ufw > /dev/null 2>&1; then
  ufw allow "$PORT/tcp" > /dev/null 2>&1 || true
fi

n=0
while [ "$n" -lt 15 ]; do
  if curl -fsS --max-time 3 "http://127.0.0.1:$PORT/api/health" > /dev/null 2>&1; then
    echo "Gary is up on port $PORT."
    exit 0
  fi
  sleep 1
  n=$((n + 1))
done
echo "Gary did not come up. Look at: journalctl -u gary -n 50"
exit 1
