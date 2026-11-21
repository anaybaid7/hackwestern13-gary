"""Tests for scripts/demo.py: the demo-day check, the reset and the replay.

Each test starts a throwaway backend of its own, in memory, on a free port.
It never reads backend/.env, so it can never touch the team's real backend.

    python3 scripts/tests/test_demo.py      # plain Python
    pytest scripts                          # or with pytest

Needs the backend requirements (pip install -r backend/requirements.txt).
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PY = sys.executable
DEMO = os.path.join(ROOT, "scripts", "demo.py")


class Backend:
    """A fresh backend that keeps its data in memory. `settings` are its
    environment, for example {"GARY_ADMIN_KEY": "k"}."""

    def __init__(self, **settings):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        self.api = "http://127.0.0.1:%d" % port
        env = {k: v for k, v in os.environ.items()
               if k not in ("SCOUT_KEY", "GARY_ADMIN_KEY", "GARY_PRIVATE_KEY", "GARY_SEED", "GARY_NAP_SECONDS",
                            "GARY_TZ", "GARY_API")}
        env.update({"GARY_NO_ENV_FILE": "1", "DATABASE_URL": ""}, **settings)
        self.proc = subprocess.Popen([PY, "-m", "uvicorn", "app:app", "--port", str(port), "--log-level", "warning"],
                                     cwd=os.path.join(ROOT, "backend"), env=env)
        for _ in range(80):
            try:
                health = self.get("/api/health")
                break
            except OSError:
                time.sleep(0.25)
        else:
            self.close()
            raise RuntimeError("the test backend did not start")
        assert health["store"] == "memory" and health["events"] == 0, health

    def get(self, path):
        with urllib.request.urlopen(self.api + path, timeout=5) as reply:
            return json.loads(reply.read().decode("utf-8"))

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def demo(*args, env=None, stdin=subprocess.DEVNULL):
    clean = {k: v for k, v in os.environ.items()
             if k not in ("SCOUT_KEY", "GARY_ADMIN_KEY", "GARY_PRIVATE_KEY", "GARY_API", "TINYFISH_API_KEY")}
    clean.update(env or {})
    return subprocess.run([PY, DEMO] + list(args), capture_output=True, text=True, env=clean, stdin=stdin, timeout=120)


def scratch():
    """A folder with no run log and no cached quests, so the tests do not
    depend on what the scout has left in this repo."""
    folder = tempfile.mkdtemp(prefix="gary-demo-")
    return folder, ["--cache", os.path.join(folder, "cached_quests.json"), "--runs", os.path.join(folder, "runs.jsonl")]


def cached_quests(path):
    """A cache file as a live scout run leaves it."""
    sys.path.insert(0, os.path.join(ROOT, "scout"))
    import scout
    places = [{"name": "Springbank Park", "about": "Large riverside park with gardens."},
              {"name": "Kains Woods", "about": "Wooded hiking trail."}]
    source = {"kind": "parks", "time": "short", "url": "https://london.ca/parks-london"}
    quests, _ = scout.build_quests(places, source, scout.today(), scout.load_labels())
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"saved_at": "2026-11-22T12:00:00Z", "day": scout.today(), "quests": quests}, f)
    return quests


def test_check_on_a_fresh_backend_is_ready_and_says_what_to_know():
    backend = Backend()
    folder, files = scratch()
    try:
        out = demo("check", "--api", backend.api, *files)
        assert out.returncode == 0, out.stdout + out.stderr
        text = out.stdout
        assert "READY, with" in text and "NOT READY" not in text
        assert "ok    a clean start: asleep, 0 XP, no finds" in text
        assert "ok    both table quests are open" in text
        assert "WARN  keeps everything in memory" in text
        assert ("WARN  anyone who has this address can reset Gary and post quests and read the private check-ins "
                "(GARY_ADMIN_KEY, SCOUT_KEY, GARY_PRIVATE_KEY not set)") in text
        assert "Do not call it private in beat 7" in text
        assert "WARN  no quest from a live scout run is loaded" in text
        assert "WARN  that quest is already on the sign" in text
        assert 'WARN  no "before" check-in yet today' in text
        assert "WARN  no live scout run is recorded here" in text and "WARN  no cached scout quests here" in text
        # it changed nothing
        assert backend.get("/api/health")["events"] == 0 and backend.get("/api/wellness")["checkins"] == []
    finally:
        backend.close()
        shutil.rmtree(folder)


def test_check_says_not_ready_when_the_backend_is_not_there():
    folder, files = scratch()
    try:
        out = demo("check", "--api", "http://127.0.0.1:9", *files)
        assert out.returncode == 1
        assert "FAIL  cannot reach the backend" in out.stdout and "?mock" in out.stdout
        assert "NOT READY: 1 thing to fix" in out.stdout
    finally:
        shutil.rmtree(folder)


def test_the_replay_proves_the_numbers_in_the_demo_script():
    backend = Backend()
    folder, files = scratch()
    try:
        out = demo("replay", "--auto", "--yes", "--samples", "--api", backend.api, *files)
        assert out.returncode == 0, out.stdout + out.stderr
        text = out.stdout
        for line in ("ok    Gary is napping with 0 XP", "ok    the bottle finishes its quest for 20 XP",
                     "ok    the backpack with a friend finishes its quest for 40 XP",
                     "ok    Gary grows into a Scrambler at 60 XP", "ok    the herd moves up the Herd Cup (was 5, now 3)",
                     "ok    two places are uncovered",
                     'ok    the sentence: "You reported feeling better after your outing."',
                     "ok    Gary is still awake at the end", "The demo's numbers hold."):
            assert line in text, (line, text)
        assert "A sample quest, written by hand" in text, "sample places are never called the scout's finds"
        # the script docs/DEMO.md is written from says the same
        with open(os.path.join(ROOT, "docs", "DEMO.md"), encoding="utf-8") as f:
            script = f.read()
        for words in ("**+20 XP**", "**+40 XP**", "Scrambler", "from 5th to 3rd", "You reported feeling better after your outing."):
            assert words in script, words
        # after a replay the backend is not ready for the real demo, and check says how to fix it
        after = demo("check", "--api", backend.api, *files)
        assert after.returncode == 1
        assert "FAIL  Gary already has 60 XP and 2 finds" in after.stdout
        assert "FAIL  the table quest is already finished: q-demo-bottle, q-demo-backpack" in after.stdout
        assert "demo.py reset" in after.stdout
        assert "WARN  today already has a before and an after" in after.stdout
    finally:
        backend.close()
        shutil.rmtree(folder)


def test_a_short_nap_setting_is_caught_before_it_spoils_the_demo():
    backend = Backend(GARY_NAP_SECONDS="60")
    folder, files = scratch()
    try:
        out = demo("check", "--api", backend.api, *files)
        assert "WARN  Gary naps after 60 seconds of quiet" in out.stdout
    finally:
        backend.close()
        shutil.rmtree(folder)


def test_reset_asks_first_and_then_puts_the_scouts_quests_back():
    backend = Backend()
    folder, files = scratch()
    try:
        demo("replay", "--auto", "--yes", "--no-quests", "--api", backend.api, *files)
        assert backend.get("/api/state")["gary"]["xp"] == 60
        # with nobody to ask, it changes nothing
        refused = demo("reset", "--api", backend.api, *files)
        assert refused.returncode != 0 and "Nothing was changed" in refused.stderr
        assert backend.get("/api/state")["gary"]["xp"] == 60
        # with --yes and no cached quests: only the built-in quests, and it says how to get samples
        plain = demo("reset", "--yes", "--api", backend.api, *files)
        assert plain.returncode == 0, plain.stdout + plain.stderr
        assert "only the built-in quests are loaded" in plain.stdout and "--samples" in plain.stdout
        assert backend.get("/api/state")["gary"]["xp"] == 0 and backend.get("/api/health")["quests"] == 3
        assert "sh start_gary.sh --fresh" in plain.stdout and "Before you head out" in plain.stdout
        # with cached quests from a live run: they come back, as the scout's
        quests = cached_quests(files[1])
        again = demo("reset", "--yes", "--api", backend.api, *files)
        assert again.returncode == 0 and "Backend accepted %d quests" % len(quests) in again.stdout
        listed = backend.get("/api/quests")["quests"]
        assert sorted(q["id"] for q in listed if q["source"] == "tinyfish") == sorted(q["id"] for q in quests)
        ready = demo("check", "--api", backend.api, *files)
        assert ready.returncode == 0
        assert "ok    2 quests from live scout runs, 2 dated today" in ready.stdout
        assert "ok    2 cached quests saved from the live run of 2026-11-22T12:00:00Z" in ready.stdout
        assert 'A tap on Short will show: "Find a bench at Springbank Park" (found by the scout).' in ready.stdout
        assert "already on the sign" not in ready.stdout
    finally:
        backend.close()
        shutil.rmtree(folder)


def test_a_locked_private_page_needs_its_passphrase():
    backend = Backend(GARY_PRIVATE_KEY="goats climb for-test")
    folder, files = scratch()
    key = {"GARY_PRIVATE_KEY": "goats climb for-test"}
    try:
        # without the passphrase the check says what it could not look at, and still runs
        blind = demo("check", "--api", backend.api, *files)
        assert blind.returncode == 0, blind.stdout + blind.stderr
        assert "WARN  the private page is locked, so the check-in could not be looked at" in blind.stdout
        assert "read the private check-ins" not in blind.stdout, "that door is closed on this backend"
        wrong = demo("check", "--api", backend.api, *files, env={"GARY_PRIVATE_KEY": "not it"})
        assert "WARN  the passphrase in GARY_PRIVATE_KEY did not open the private page" in wrong.stdout
        # the replay cannot make its check-ins without it, and it finds that out before it forgets anything
        req = urllib.request.Request(backend.api + "/api/events", headers={"Content-Type": "application/json"}, data=json.dumps(
            {"events": [{"id": "keep-me", "ts": "2026-11-21T15:00:00Z", "type": "discovery", "label": "kite"}]}).encode())
        urllib.request.urlopen(req, timeout=5).read()
        stuck = demo("replay", "--auto", "--yes", "--api", backend.api, *files)
        assert stuck.returncode != 0 and "GARY_PRIVATE_KEY" in stuck.stderr and "Nothing was changed" in stuck.stderr
        assert backend.get("/api/health")["events"] == 1, "the sniff from before is still there"
        # with it, everything works, and the passphrase is never printed
        played = demo("replay", "--auto", "--yes", "--api", backend.api, *files, env=key)
        assert played.returncode == 0 and "The demo's numbers hold." in played.stdout, played.stdout + played.stderr
        seen = demo("check", "--api", backend.api, *files, env=key)
        assert "WARN  today already has a before and an after" in seen.stdout
        for out in (blind, wrong, stuck, played, seen):
            assert "goats climb" not in out.stdout + out.stderr
    finally:
        backend.close()
        shutil.rmtree(folder)


def test_a_locked_backend_needs_its_keys_and_check_says_it_is_locked():
    backend = Backend(GARY_ADMIN_KEY="admin-key-for-test", SCOUT_KEY="scout-key-for-test", GARY_PRIVATE_KEY="private-for-test")
    folder, files = scratch()
    try:
        cached_quests(files[1])
        out = demo("check", "--api", backend.api, *files)
        assert "ok    the reset, quest posting and the private page are locked with keys" in out.stdout
        assert "admin-key-for-test" not in out.stdout and "scout-key-for-test" not in out.stdout
        no_key = demo("reset", "--yes", "--api", backend.api, *files)
        assert no_key.returncode != 0 and "GARY_ADMIN_KEY" in no_key.stderr and "Nothing was changed" in no_key.stderr
        wrong = demo("reset", "--yes", "--api", backend.api, *files, env={"GARY_ADMIN_KEY": "not-it"})
        assert wrong.returncode != 0 and "Nothing was changed" in wrong.stderr
        # the admin key alone resets, but the quests need the scout's key too, and it says so
        half = demo("reset", "--yes", "--api", backend.api, *files, env={"GARY_ADMIN_KEY": "admin-key-for-test"})
        assert half.returncode == 0 and "export the same value here" in half.stdout
        assert backend.get("/api/health")["quests"] == 3
        both = demo("reset", "--yes", "--api", backend.api, *files,
                    env={"GARY_ADMIN_KEY": "admin-key-for-test", "SCOUT_KEY": "scout-key-for-test"})
        assert both.returncode == 0 and backend.get("/api/health")["quests"] == 5
    finally:
        backend.close()
        shutil.rmtree(folder)


def test_check_knows_a_before_check_in_from_one_that_is_already_paired():
    backend = Backend()
    folder, files = scratch()
    try:
        def mood(phase, value):
            req = urllib.request.Request(backend.api + "/api/mood", data=json.dumps({"phase": phase, "value": value}).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5).read()

        mood("before", 5)
        assert 'WARN  the "before" check-in is already at the top of the scale' in demo("check", "--api", backend.api, *files).stdout
        mood("after", 5)
        mood("before", 2)
        out = demo("check", "--api", backend.api, *files).stdout
        assert 'ok    a "before" check-in is waiting for its "after"' in out
        assert " 2 " not in out.split("The private check-in")[1].split("This machine")[0], "the number itself is private"
    finally:
        backend.close()
        shutil.rmtree(folder)


def test_check_device_reads_what_the_real_start_script_says():
    """Runs the real start_gary.sh in a scratch folder, with the device tests'
    stand-in for Gary, and reads its status the way `check --device` does."""
    if os.name != "posix" or not shutil.which("sh"):
        return  # needs a POSIX shell
    device, tests = os.path.join(ROOT, "device"), os.path.join(ROOT, "device", "tests")
    folder = tempfile.mkdtemp(prefix="gary-demo-device-")
    scratch_folder, files = scratch()
    start = os.path.join(folder, "start_gary.sh")
    try:
        for name in ("start_gary.sh", "stop_gary.sh", "gary_io.py", "sync.py"):
            shutil.copy(os.path.join(device, name), folder)
        shutil.copy(os.path.join(tests, "fake_gary.py"), folder)
        with open(os.path.join(folder, "gary.env"), "w") as f:
            f.write('GARY_CMD="%s fake_gary.py"\nGARY_FLAGS=""\nGARY_PYTHON="%s"\nGARY_API=http://127.0.0.1:9\n'
                    'GARY_BUTTON_PIN=none\nGARY_BUZZER_PIN=none\nGARY_START_WAIT=1\n' % (PY, PY))
        with open(os.path.join(folder, "journal.jsonl"), "w") as f:
            f.write('{"id": "old-1", "ts": "2026-11-21T15:00:00Z", "type": "miss"}\n')

        # nothing started yet
        down = demo("check", "--api", "http://127.0.0.1:9", "--device", "--device-dir", folder, *files).stdout
        section = down.split("Gary, on this machine")[1]
        assert "FAIL  Gary is not running" in section and "FAIL  sync is not running" in section

        up = subprocess.run(["sh", start], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        assert "Gary: up" in up.stdout, up.stdout + up.stderr
        seen = demo("check", "--api", "http://127.0.0.1:9", "--device", "--device-dir", folder, *files).stdout
        section = seen.split("Gary, on this machine")[1]
        assert "ok    Gary is running" in section and "ok    sync is running" in section, section
        # no pins in this scratch folder, so the button script is not started: the check must say so
        assert "FAIL  the button and buzzer script is not running" in section, section
        assert "WARN  the device's journal has 1 line from earlier" in section
        assert "WARN  this is the Python version of Gary, not the QNX build" in section
        assert "This machine" not in seen, "on the Pi the repo's files are not looked at"
        # copied next to start_gary.sh, as on a Pi that has only Gary's folder, it finds Gary by itself
        shutil.copy(DEMO, folder)
        clean = {k: v for k, v in os.environ.items() if k not in ("GARY_API", "GARY_PRIVATE_KEY")}
        alone = subprocess.run([PY, os.path.join(folder, "demo.py"), "check", "--api", "http://127.0.0.1:9", "--device"],
                               capture_output=True, text=True, env=clean, timeout=60).stdout
        assert "Gary, on this machine  %s" % os.path.realpath(folder) in alone.replace(folder, os.path.realpath(folder)), alone
        assert "ok    Gary is running" in alone
    finally:
        subprocess.run(["sh", os.path.join(folder, "stop_gary.sh")], capture_output=True, text=True, timeout=60)
        shutil.rmtree(folder, ignore_errors=True)
        shutil.rmtree(scratch_folder)


if __name__ == "__main__":
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        print("skipped: the demo tool tests need the backend requirements (pip install -r backend/requirements.txt)")
        sys.exit(0)
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok   " + name)
            except Exception:
                failed += 1
                import traceback
                print("FAIL " + name)
                traceback.print_exc()
    print("%d demo tool tests, %d failed" % (sum(1 for n in globals() if n.startswith("test_")), failed))
    sys.exit(1 if failed else 0)
