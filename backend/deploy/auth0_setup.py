#!/usr/bin/env python3
"""Create Gary's Auth0 pieces in your tenant. Safe to run again.

    brew install auth0/auth0-cli/auth0 && auth0 login      once
    python3 backend/deploy/auth0_setup.py https://your-page-address

It makes: the API "https://gary.api" with the permissions write:quests and
reset:gary; three applications (the page, Gary himself with the device flow,
the scout as a machine); the scout's grant; and the role "Goat keeper".
It prints ids only, and the settings the server needs. The scout's client
secret goes from Auth0 straight into scout/.env and is never shown.
"""
import json
import os
import re
import shutil
import subprocess
import sys

A0 = shutil.which("auth0") or "/opt/homebrew/bin/auth0"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUD = "https://gary.api"
# where the page is served: sign-in may return only to these addresses
ORIGINS = ["http://localhost:8000", "http://localhost:5173"] + [a.rstrip("/") for a in sys.argv[1:]]

def api(method, path, body=None):
    cmd = [A0, "api", method, path]
    if body is not None:
        cmd += ["--data", json.dumps(body)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    text = out.stdout.strip()
    try:
        data = json.loads(text) if text else None
    except ValueError:
        data = {"raw": text[:300]}
    if out.returncode != 0 or (isinstance(data, dict) and data.get("statusCode", 200) >= 400):
        print("FAILED", method, path, (data or {}).get("message") if isinstance(data, dict) else "", out.stderr.strip()[:300])
        sys.exit(1)
    return data

apis = api("get", "resource-servers")
rs = next((a for a in apis if a.get("identifier") == AUD), None)
rs_body = {"name": "Gary API", "signing_alg": "RS256", "enforce_policies": True,
           "token_dialect": "access_token_authz", "allow_offline_access": True, "token_lifetime": 86400,
           "token_lifetime_for_web": 7200, "skip_consent_for_verifiable_first_party_clients": True,
           "scopes": [{"value": "write:quests", "description": "The scout may write today's quests"},
                      {"value": "reset:gary", "description": "Start Gary over, for testing"}]}
if rs:
    api("patch", "resource-servers/" + rs["id"], rs_body)
else:
    rs = api("post", "resource-servers", dict(rs_body, identifier=AUD))
print("api", rs["identifier"])

clients = api("get", "clients?fields=client_id,name&include_fields=true&per_page=100")
def client(name, body):
    found = next((c for c in clients if c.get("name") == name), None)
    if found:
        api("patch", "clients/" + found["client_id"], body)
        return found["client_id"]
    return api("post", "clients", dict(body, name=name))["client_id"]

rotate = {"rotation_type": "rotating", "expiration_type": "expiring", "token_lifetime": 2592000, "leeway": 30,
          "infinite_token_lifetime": False, "idle_token_lifetime": 1296000, "infinite_idle_token_lifetime": False}
page = client("Gary page", {"app_type": "spa", "is_first_party": True, "oidc_conformant": True,
    "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"],
    "callbacks": ORIGINS, "allowed_logout_urls": ORIGINS, "web_origins": ORIGINS, "allowed_origins": ORIGINS,
    "jwt_configuration": {"alg": "RS256"}, "refresh_token": rotate,
    "description": "The web page: people sign in here"})
device = client("Gary device", {"app_type": "native", "is_first_party": True, "oidc_conformant": True,
    "token_endpoint_auth_method": "none",
    "grant_types": ["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"],
    "jwt_configuration": {"alg": "RS256"}, "refresh_token": rotate,
    "description": "Gary himself, on the Pi: paired with the device flow"})
scout = client("Gary scout", {"app_type": "non_interactive", "is_first_party": True, "oidc_conformant": True,
    "grant_types": ["client_credentials"], "jwt_configuration": {"alg": "RS256"},
    "description": "The TinyFish scout: a machine that may write quests"})

grants = api("get", "client-grants?client_id=%s" % scout)
grant = next((g for g in grants if g.get("audience") == AUD), None)
if grant:
    api("patch", "client-grants/" + grant["id"], {"scope": ["write:quests"]})
else:
    api("post", "client-grants", {"client_id": scout, "audience": AUD, "scope": ["write:quests"]})

# People sign in through the tenant's connections: switch them on for the page and for Gary
for conn in api("get", "connections?per_page=50"):
    api("patch", "connections/%s/clients" % conn["id"],
        [{"client_id": page, "status": True}, {"client_id": device, "status": True}])
    print("connection", conn["name"], conn["strategy"])

roles = api("get", "roles")
role = next((r for r in roles if r.get("name") == "Goat keeper"), None) or \
    api("post", "roles", {"name": "Goat keeper", "description": "May start Gary over (reset:gary)"})
api("post", "roles/%s/permissions" % role["id"],
    {"permissions": [{"resource_server_identifier": AUD, "permission_name": "reset:gary"}]})

tenant = json.loads(subprocess.run([A0, "tenants", "list", "--json"], capture_output=True, text=True).stdout)
domain = next(t["name"] for t in tenant if t.get("active"))

# the scout's secret: from Auth0 into scout/.env, never onto the screen
shown = subprocess.run([A0, "apps", "show", scout, "--reveal-secrets", "--json"], capture_output=True, text=True)
secret = json.loads(shown.stdout)["client_secret"]
env = os.path.join(ROOT, "scout", ".env")
lines = open(env).read().splitlines() if os.path.exists(env) else []
lines = [l for l in lines if not re.match(r"AUTH0_(DOMAIN|AUDIENCE|SCOUT_CLIENT_ID|SCOUT_CLIENT_SECRET)=", l)]
lines += ["AUTH0_DOMAIN=" + domain, "AUTH0_AUDIENCE=" + AUD, "AUTH0_SCOUT_CLIENT_ID=" + scout,
          "AUTH0_SCOUT_CLIENT_SECRET=" + secret]
fd = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    f.write("\n".join(lines) + "\n")
print("scout: its id and secret are now in scout/.env")
print("role Goat keeper:", role["id"])
print("")
print("# for the server's .env (none of these is secret):")
print("AUTH0_DOMAIN=%s\nAUTH0_AUDIENCE=%s\nAUTH0_CLIENT_ID=%s\nAUTH0_DEVICE_CLIENT_ID=%s" % (domain, AUD, page, device))
