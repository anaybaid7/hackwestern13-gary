# Auth0 in Gary: every key becomes an identity

Issue #23. Live at https://149-248-50-153.sslip.io (Settings, then Account).

Before this, Gary had three shared secrets: a passphrase for the private
check-ins, a key for the scout and a key for the reset. Anyone who knew one
could use it, and nobody could tell who had. With Auth0, each caller proves
who it is, in the way that fits what it is.

| Who | Auth0 flow | What it may do |
| --- | --- | --- |
| A person on the page | Universal Login (authorization code with PKCE) | Read and write **their own** check-ins |
| Gary himself, on the Pi | **Device Authorization Flow** | Send sniffs signed as the person he is paired with |
| The scout | Machine to machine (client credentials) | Write quests: its token carries `write:quests` |
| A person with the role "Goat keeper" | Universal Login, plus RBAC | Start Gary over: `reset:gary` |

## Pairing a goat

Gary has a button and a buzzer, no keyboard and no screen. So he signs in the
way a TV does:

```
$ python3 pair.py
  Gary wants to be your goat.
  On your phone, open:  https://<tenant>/activate
  and enter the code:   PRDQ-TJQR
  Paired. Gary's sniffs are now signed as yours.
```

From then on `sync.py` sends his token with every upload. The backend checks
it and marks those sniffs as yours; the page's Account panel then says a Gary
is paired with you. Nothing a device writes in the upload itself can claim an
owner: only a checked token can.

A paired Gary never loses a sniff over his token. He does not send one that
has run out, he renews it when he can, and if the backend refuses it he sends
the upload again without it.

## No names kept

The backend never stores a name, an e-mail address or the Auth0 id. It keeps
the first 16 hex digits of the SHA-256 of the id: a fingerprint. That is
enough to keep one person's check-ins apart from another's. On the page you
are a goat name made from the fingerprint ("Brave Cedar Goat"). The
fingerprint never appears in `/api/state`, which everyone can read.

## How a token is checked (`backend/auth.py`)

RS256 only; signed by one of the tenant's keys (fetched once, kept ten
minutes, fetched again for a key id it has not seen, at most every 30
seconds); issued by the tenant; meant for the API `https://gary.api`; not
run out. A token that is sent and fails any of these is refused with `401`,
on every route. It is never treated as "no token".

## It is optional

With no `AUTH0_DOMAIN` on the backend, none of this is active and the shared
keys work as before: the laptop demo, the Pi's own backend and the tests need
no tenant and no network. With Auth0 on, the shared keys still work beside
it, so the team is never locked out during the demo.

| Route | Opens with |
| --- | --- |
| `POST /api/mood`, `GET /api/wellness` | a person's token (their own check-ins), or `X-Private-Key` (the ones nobody signed) |
| `POST /api/quests` | a token with `write:quests`, or `X-Scout-Key` |
| `POST /api/dev/reset` | a token with `reset:gary`, or `X-Admin-Key` |
| `POST /api/events` | anyone, as before. A person's token signs the sniffs |
| `GET /api/me` | `{"signed_in", "fingerprint", "paired", "permissions"}` |
| `GET /api/auth/config` | what the page and the device need to start a login. Nothing secret |

## Set it up

```sh
brew install auth0/auth0-cli/auth0 && auth0 login
python3 backend/deploy/auth0_setup.py https://your-page-address
```

The script creates the API, the three applications, the scout's grant and the
role, and can be run again. It prints the four settings for the server's
`.env` (`AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AUTH0_CLIENT_ID`,
`AUTH0_DEVICE_CLIENT_ID`; none is secret) and writes the scout's id and secret
into `scout/.env`, which git ignores.

Signing in on the page needs `https`: `backend/deploy/https.sh` gives the
server an `https` address with no domain to buy.

## Tests

`backend/tests/test_auth.py` signs its own tokens with a key made in the test
and covers: wrong key, unknown key, wrong tenant, wrong API, run out, wrong
algorithm, a machine reading check-ins, a device claiming an owner, and key
rotation. `device/tests/test_pair.py` runs the device flow against a fake
Auth0. No test uses the network.
