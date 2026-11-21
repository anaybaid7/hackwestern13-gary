"""pair.py: the device flow and the token it keeps. Run: python3 -m pytest device/tests/test_pair.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pair  # noqa: E402

CONFIG = {"domain": "gary-test.ca.auth0.com", "audience": "https://gary.api", "client_id": "device-client"}


def auth0(answers):
    """A fake Auth0: answers each POST in turn and remembers what was asked."""
    asked = []

    def post(url, fields):
        asked.append((url, fields))
        return answers.pop(0)

    return post, asked


START = (200, {"device_code": "dc", "user_code": "GOAT-BAAA", "verification_uri": "https://t/activate",
               "verification_uri_complete": "https://t/activate?user_code=GOAT-BAAA", "interval": 1, "expires_in": 60})


def test_pairing_shows_the_code_waits_and_keeps_the_token(tmp_path):
    path = str(tmp_path / "gary.token")
    post, asked = auth0([START, (403, {"error": "authorization_pending"}), (429, {"error": "slow_down"}),
                         (200, {"access_token": "tok", "refresh_token": "ref", "expires_in": 3600})])
    said, naps = [], []
    assert pair.pair(CONFIG, say=said.append, post=post, sleep=naps.append, path=path) is True
    assert any("GOAT-BAAA" in line for line in said) and any("https://t/activate" in line for line in said)
    assert naps == [1, 1, 6]                      # slow_down means wait longer
    assert asked[0][1] == {"client_id": "device-client", "audience": "https://gary.api", "scope": "offline_access"}
    saved = json.load(open(path))
    assert saved["access_token"] == "tok" and saved["refresh_token"] == "ref" and saved["domain"] == CONFIG["domain"]
    assert oct(os.stat(path).st_mode & 0o777) == "0o600"   # only the owner can read it


def test_a_refused_or_expired_code_pairs_nothing(tmp_path):
    path = str(tmp_path / "gary.token")
    post, _ = auth0([START, (403, {"error": "access_denied", "error_description": "You said no."})])
    said = []
    assert pair.pair(CONFIG, say=said.append, post=post, sleep=lambda s: None, path=path) is False
    assert "You said no." in said[-1] and not os.path.exists(path)
    post, _ = auth0([(403, {"error": "unauthorized_client"})])
    assert pair.pair(CONFIG, say=said.append, post=post, sleep=lambda s: None, path=path) is False


def test_the_token_to_send_is_never_a_stale_one(tmp_path):
    path = str(tmp_path / "gary.token")
    assert pair.current_token(path) is None                                  # not paired
    pair.save({"access_token": "tok", "refresh_token": None, "expires_at": 1000, **CONFIG}, path)
    assert pair.current_token(path, now=lambda: 500) == "tok"
    assert pair.current_token(path, now=lambda: 950) is None                 # about to run out, no way to renew
    # with a refresh token it renews, and keeps the refresh token Auth0 did not send again
    pair.save({"access_token": "tok", "refresh_token": "ref", "expires_at": 1000, **CONFIG}, path)
    post, asked = auth0([(200, {"access_token": "tok2", "expires_in": 3600})])
    assert pair.current_token(path, post=post, now=lambda: 2000) == "tok2"
    assert asked[0][1]["grant_type"] == "refresh_token" and asked[0][0] == "https://gary-test.ca.auth0.com/oauth/token"
    assert json.load(open(path))["refresh_token"] == "ref"
    # Auth0 says no, or the network is down: no token, and no crash
    pair.save({"access_token": "tok", "refresh_token": "ref", "expires_at": 1000, **CONFIG}, path)
    post, _ = auth0([(403, {"error": "invalid_grant"})])
    assert pair.current_token(path, post=post, now=lambda: 2000) is None

    def down(url, fields):
        raise OSError("no network")

    assert pair.current_token(path, post=down, now=lambda: 2000) is None
    open(path, "w").write("not json")
    assert pair.current_token(path) is None


def test_an_upload_refused_for_its_token_is_sent_again_without_it(monkeypatch):
    import io
    import urllib.error
    import sync
    seen = []

    class Reply(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout=None):
        seen.append(req.get_header("Authorization"))
        if req.get_header("Authorization"):
            raise urllib.error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b"{}"))
        return Reply(b'{"accepted": 1}')

    monkeypatch.setattr(sync.urllib.request, "urlopen", fake)
    assert sync.call("http://gary", "/api/events", {"events": []}, "stale") == {"accepted": 1}
    assert seen == ["Bearer stale", None]
