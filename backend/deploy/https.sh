#!/bin/sh
# Give Gary's server an https address. Run ON the server, as root:
#
#   sh /opt/gary/app/backend/deploy/https.sh 149-248-50-153.sslip.io
#
# Signing in with Auth0 only works on https (the browser's crypto needs it).
# sslip.io turns an IP address into a name with no sign-up: the name
# 149-248-50-153.sslip.io points at 149.248.50.153, so Let's Encrypt can
# give it a certificate.
#
# Caddy listens on 443 only and hands requests to Gary on port 80. Plain
# http on port 80 keeps working exactly as before: the Pi and the scout
# post there. Safe to run again.
set -e
HOST="${1:-}"
if [ -z "$HOST" ]; then
  echo "usage: sh https.sh <host name that points at this server>"
  exit 2
fi
export DEBIAN_FRONTEND=noninteractive
if ! command -v caddy > /dev/null 2>&1; then
  apt-get -o DPkg::Lock::Timeout=180 update -q > /dev/null
  apt-get -o DPkg::Lock::Timeout=180 install -y -q caddy > /dev/null
fi
cat > /etc/caddy/Caddyfile <<CADDY
{
	# port 80 belongs to Gary: no redirect listener, and prove the name on 443
	auto_https disable_redirects
}
$HOST {
	tls {
		issuer acme {
			disable_http_challenge
		}
	}
	reverse_proxy 127.0.0.1:80
}
CADDY
if command -v ufw > /dev/null 2>&1; then
  ufw allow 443/tcp > /dev/null 2>&1 || true
fi
systemctl enable caddy > /dev/null 2>&1 || true
systemctl restart caddy
echo "Waiting for the certificate"
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if curl -fsS --max-time 5 "https://$HOST/api/health" > /dev/null 2>&1; then
    echo "Gary is at https://$HOST/"
    exit 0
  fi
  sleep 3
done
echo "https://$HOST/ did not answer yet. Look at: journalctl -u caddy -n 30"
exit 1
