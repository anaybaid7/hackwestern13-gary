#!/usr/bin/env python3
"""Tests for the device's scripts. No Pi, no camera, no backend needed.

    python3 device/tests/test_device.py          (or: pytest device/tests)

What is covered: the button's debounce, the five buzzer patterns, following
the journal, the mood line, a stale gary.pid, sync.py with no network and its
catch-up, gary_numbers.py, the quest choice, the torn-line repair, and
start_gary.sh with a stand-in Gary.

What is not: real GPIO pins, a real buzzer, QNX. Those need the Pi.
"""
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

TESTS = os.path.dirname(os.path.abspath(__file__))
DEVICE = os.path.dirname(TESTS)
sys.path.insert(0, DEVICE)

import gary_io  # noqa: E402

PY = sys.executable


class Skip(Exception):
    pass


def load(name):
    """Import one of the device scripts by file name."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gary_" + name, os.path.join(DEVICE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wait_for(check, seconds=5.0, every=0.02):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(every)
    return check()


def read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_no_script_here_hides_a_python_module():
    """A file called io.py or numbers.py in this folder would replace Python's
    own module of that name for every script run from here (numpy imports
    numbers, and then Gary himself would not start). Keep the names clear."""
    for name in sorted(os.listdir(DEVICE)):
        if not name.endswith(".py"):
            continue
        stem = name[:-3]
        clash = stem in sys.builtin_module_names or stem in getattr(sys, "stdlib_module_names", ())
        assert not clash, "%s has the same name as Python's own '%s' module. Rename it." % (name, stem)


# --------------------------------------------------------------------------
# Button
# --------------------------------------------------------------------------
def feed(button, samples):
    """samples: [(time, level)]. Returns the times at which a press was reported."""
    return [t for t, level in samples if button.update(level, t)]


def test_one_noisy_push_is_one_press():
    button = gary_io.Button(debounce=0.03, gap=0.4)
    samples = [(0.000, False)]
    # contact bounce for 12 ms, then held for 200 ms, bounce on release
    samples += [(0.100 + i * 0.002, i % 2 == 0) for i in range(6)]
    samples += [(0.112 + i * 0.005, True) for i in range(40)]
    samples += [(0.312 + i * 0.002, i % 2 == 1) for i in range(6)]
    samples += [(0.324 + i * 0.005, False) for i in range(40)]
    presses = feed(button, samples)
    assert len(presses) == 1, presses
    assert 0.13 <= presses[0] <= 0.16, "reported about 30 ms after the level settled, got %r" % presses


def test_a_held_button_and_a_double_tap_are_one_press():
    button = gary_io.Button(debounce=0.03, gap=0.4)
    held = [(0.0, False)] + [(0.1 + i * 0.005, True) for i in range(1000)]  # held for 5 seconds
    assert len(feed(button, held)) == 1

    button = gary_io.Button(debounce=0.03, gap=0.4)
    def push(at):
        return [(at + i * 0.005, True) for i in range(12)] + [(at + 0.06 + i * 0.005, False) for i in range(12)]
    assert len(feed(button, [(0.0, False)] + push(0.1) + push(0.25))) == 1, "two taps 150 ms apart are one"
    button = gary_io.Button(debounce=0.03, gap=0.4)
    assert len(feed(button, [(0.0, False)] + push(0.1) + push(0.7))) == 2, "two pushes 600 ms apart are two"


def test_a_button_stuck_at_start_is_not_a_press():
    button = gary_io.Button()
    assert feed(button, [(i * 0.005, True) for i in range(200)]) == []
    # ...and it works normally once it is released and pushed again
    after = [(1.0 + i * 0.005, False) for i in range(20)] + [(1.2 + i * 0.005, True) for i in range(20)]
    assert len(feed(button, after)) == 1


def test_a_glitch_shorter_than_the_debounce_is_ignored():
    button = gary_io.Button(debounce=0.03)
    samples = [(0.0, False), (0.100, True), (0.105, True), (0.110, False)] + [(0.2 + i * 0.005, False) for i in range(10)]
    assert feed(button, samples) == []


# --------------------------------------------------------------------------
# Buzzer
# --------------------------------------------------------------------------
def on_off(steps):
    """A pattern as the on/off buzzer plays it: lengths of each beep, in ms."""
    return [round(seconds * 1000) for seconds, tone in steps if tone]


def test_good_is_one_quick_beep_and_bad_is_three():
    beeps = lambda event, open_labels=(): len(on_off(gary_io.pattern_for(event, open_labels)))  # noqa: E731
    bottle_quest = {"bottle"}
    assert beeps({"type": "discovery", "label": "bottle", "quest_id": "q-1"}, bottle_quest) == 1, "the quest's thing"
    assert beeps({"type": "discovery", "label": "bottle", "friend": True}, bottle_quest) == 1, "the thing, a herd quest"
    assert beeps({"type": "discovery", "label": "dog", "new": True}, bottle_quest) == 3, "not what we're looking for"
    assert beeps({"type": "discovery", "label": "dog", "new": True}) == 1, "no quest open: a find is good"
    assert beeps({"type": "discovery", "label": "dog", "new": False}) == 1
    unsure = on_off(gary_io.pattern_for({"type": "miss"}, bottle_quest))
    assert len(unsure) == 2 and unsure[1] > unsure[0], "nothing he can name: puzzled, not bad"
    assert on_off(gary_io.pattern_for({"type": "miss", "friend": True})) == unsure
    assert max(on_off(gary_io.PATTERNS["bad"])) <= 60, "quick, so the voice follows at once"
    # lines that are not sniffs make no noise, and nothing here reveals a mood
    assert gary_io.pattern_for({"type": "choice"}) == []
    assert gary_io.pattern_for({"type": "mood", "value": 1}) == gary_io.pattern_for({"type": "mood", "value": 5})


def test_the_beeper_keeps_time_and_ends_silent():
    played = []
    beeper = gary_io.Beeper(lambda tone: played.append((round(now[0], 3), tone)))
    now = [0.0]
    beeper.play(gary_io.PATTERNS["bad"])        # 60 on, 60 off, 60 on, 60 off, 60 on
    while beeper.busy():
        beeper.tick(now[0])
        now[0] += 0.005
    assert [tone for _, tone in played] == [880, 0, 880, 0, 880, 0], played
    starts = [t for t, _ in played]
    assert all(abs(s - want) < 0.011 + 0.005 * i for i, (s, want) in enumerate(zip(starts, [0, 0.06, 0.12, 0.18, 0.24, 0.30])))

    # two patterns in a row are separated by a silence; a flood is dropped, not queued for a minute
    played.clear()
    beeper.play(gary_io.PATTERNS["good"])
    beeper.play(gary_io.PATTERNS["good"])
    for _ in range(100):
        beeper.play(gary_io.PATTERNS["not_ready"])
    assert beeper.queued < gary_io.Beeper.MAX_QUEUED + 1.0
    while beeper.busy():
        beeper.tick(now[0])
        now[0] += 0.005
    assert played[-1][1] == 0, "the buzzer must end switched off"


def test_the_buzzer_knows_which_quests_are_open():
    folder = tempfile.mkdtemp(prefix="gary-io-")
    try:
        with open(os.path.join(folder, "quests.seed.tsv"), "w", encoding="utf-8") as f:
            f.write("# seed\ns-1\tbench\t10\tA bench\nh-1\tperson\t10\tA friend\n")
        journal = os.path.join(folder, "journal.jsonl")
        with open(journal, "w", encoding="utf-8") as f:
            f.write("{not json\n")  # a torn line is skipped
        book = gary_io.QuestBook(folder, journal)
        assert book.open_labels() == {"bench"}, "a quest for a friend is not a thing to find"
        with open(os.path.join(folder, "quests.tsv"), "w", encoding="utf-8") as f:
            f.write("q-1\tbottle\t10\tWater bottle\n")
        assert book.open_labels() == {"bottle"}, "sync.py's quests.tsv wins over the seed"
        book.note({"type": "discovery", "label": "bottle", "quest_id": "q-1"})
        assert book.open_labels() == set(), "a finished quest is no longer open"
        assert gary_io.QuestBook(folder, os.path.join(folder, "none.jsonl")).open_labels() == {"bottle"}
        with open(journal, "a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "discovery", "label": "bottle", "quest_id": "q-1"}) + "\n")
        assert gary_io.QuestBook(folder, journal).open_labels() == set(), "done quests are read from the journal"
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_a_broken_buzzer_never_stops_the_loop():
    class Broken:
        has_button = has_buzzer = True

        def read_button(self):
            raise OSError("the GPIO manager went away")

        def sound(self, tone):
            raise OSError("no such pin")

        def close(self):
            pass

    said = []
    folder = tempfile.mkdtemp(prefix="gary-io-")
    try:
        io = gary_io.Io(Broken(), folder, said.append)
        io.beeper.play(gary_io.PATTERNS["good"])
        for i in range(50):
            io.step(i * 0.005)        # must not raise
        assert io.button_ok is False and io.buzzer_ok is False
        assert len(said) == 2, "each failure is reported once, not on every tick: %r" % said
    finally:
        shutil.rmtree(folder)


# --------------------------------------------------------------------------
# Following the journal
# --------------------------------------------------------------------------
def test_the_tail_only_reports_new_complete_lines():
    folder = tempfile.mkdtemp(prefix="gary-io-")
    path = os.path.join(folder, "journal.jsonl")
    try:
        with open(path, "w") as f:
            f.write('{"id": "old", "type": "discovery"}\n')
        tail = gary_io.JournalTail(path)
        assert tail.poll() == [], "lines from before the start make no sound"
        with open(path, "a") as f:
            f.write('{"id": "a", "type": "discovery"}\n{"id": "b", "ty')
        assert [e["id"] for e in tail.poll()] == ["a"], "a half-written line waits"
        with open(path, "a") as f:
            f.write('pe": "miss"}\n')
        assert [e["id"] for e in tail.poll()] == ["b"]
        with open(path, "a") as f:
            f.write('{"id": "torn", "ts": "20\n{"id": "c", "type": "miss"}\n')
        assert [e["id"] for e in tail.poll()] == ["c"], "a torn line is skipped"
        # the journal is set aside (start_gary.sh --fresh) and a new one begins
        os.rename(path, path + ".bak")
        assert tail.poll() == []
        with open(path, "w") as f:
            f.write('{"id": "fresh", "type": "discovery"}\n')
        assert [e["id"] for e in tail.poll()] == ["fresh"]
        # a burst (a copied-in journal) beeps once, not fifty times
        with open(path, "a") as f:
            f.write("".join('{"id": "n%d", "type": "discovery"}\n' % i for i in range(50)))
        assert [e["id"] for e in tail.poll()] == ["n49"]
    finally:
        shutil.rmtree(folder)


def test_a_mood_line_is_a_valid_event_on_its_own_line():
    folder = tempfile.mkdtemp(prefix="gary-io-")
    path = os.path.join(folder, "journal.jsonl")
    try:
        with open(path, "w") as f:
            f.write('{"id": "a", "type": "discovery"}\n{"id": "cut", "ts": "20')   # ends mid-line
        event = gary_io.write_mood(path, "gary-01", "before", 3)
        assert event["type"] == "mood" and event["phase"] == "before" and event["value"] == 3
        with open(path) as f:
            lines = f.read().split("\n")
        assert lines[-1] == "" and json.loads(lines[-2]) == event, "the mood line stands alone"
        assert set(event) == {"id", "ts", "type", "device", "phase", "value"}
        for bad in (("during", 3), ("before", 0), ("after", 6)):
            try:
                gary_io.write_mood(path, "gary-01", *bad)
            except ValueError:
                continue
            raise AssertionError("accepted %r" % (bad,))
        out = subprocess.run([PY, os.path.join(DEVICE, "gary_io.py"), "--dir", folder, "--mood", "after", "4"],
                             capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        last = read_lines_tolerant(path)[-1]
        assert (last["phase"], last["value"]) == ("after", 4)
    finally:
        shutil.rmtree(folder)


def read_lines_tolerant(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


# --------------------------------------------------------------------------
# Button -> Gary -> journal -> buzzer, with a stand-in Gary
# --------------------------------------------------------------------------
class ScriptPins:
    has_button = has_buzzer = True

    def __init__(self):
        self.level = False
        self.sounds = []

    def read_button(self):
        return self.level

    def sound(self, tone):
        self.sounds.append(tone)

    def close(self):
        pass


def start_fake_gary(folder):
    proc = subprocess.Popen([PY, os.path.join(TESTS, "fake_gary.py"), folder],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert wait_for(lambda: os.path.exists(os.path.join(folder, "gary.pid"))), "the stand-in Gary did not start"
    return proc


def run_io(io, pins, seconds, pushes=()):
    """Drive the loop in real time. pushes: [(start, end)] seconds when the button is down,
    with 10 ms of contact bounce at each edge."""
    begin = time.monotonic()
    while True:
        t = time.monotonic() - begin
        if t >= seconds:
            return
        level = False
        for start, end in pushes:
            if start <= t < start + 0.010 or end <= t < end + 0.010:
                level = int(t * 1000) % 2 == 0     # bouncing
            elif start + 0.010 <= t < end:
                level = True
        pins.level = level
        io.step(time.monotonic())
        time.sleep(0.002)


def test_one_push_is_one_journal_line_and_one_pattern():
    folder = tempfile.mkdtemp(prefix="gary-io-")
    gary = start_fake_gary(folder)
    try:
        pins, said = ScriptPins(), []
        io = gary_io.Io(pins, folder, said.append)
        run_io(io, pins, 2.2, pushes=[(0.2, 0.45), (1.2, 1.5)])
        lines = read_lines(os.path.join(folder, "journal.jsonl"))
        assert len(lines) == 2, "two pushes, two sniffs, got %d: %r" % (len(lines), said)
        assert io.presses == 2
        assert sum(1 for s in said if s == "button: Sniff Test") == 2
        # no quest is open here, so both finds are good: one quick beep each
        assert sum(1 for tone in pins.sounds if tone) == 2, pins.sounds
        assert pins.sounds[-1] == 0, "ends silent"
        assert any("new discovery: bottle" in s for s in said) and any("seen before: bottle" in s for s in said)
    finally:
        gary.terminate()
        gary.wait(timeout=5)
        shutil.rmtree(folder)


def test_a_push_with_no_gary_says_so_and_harms_nothing():
    folder = tempfile.mkdtemp(prefix="gary-io-")
    try:
        pins, said = ScriptPins(), []
        io = gary_io.Io(pins, folder, said.append)
        run_io(io, pins, 1.4, pushes=[(0.1, 0.3)])
        assert any("Gary is not running" in s for s in said), said
        assert sum(1 for tone in pins.sounds if tone) == 3, "three slow buzzes: %r" % pins.sounds
        assert not os.path.exists(os.path.join(folder, "journal.jsonl"))
    finally:
        shutil.rmtree(folder)


def test_a_stale_pid_file_never_signals_a_stranger():
    if not os.path.exists("/proc/self/cmdline"):
        raise Skip("this system does not show command lines in /proc")
    folder = tempfile.mkdtemp(prefix="gary-io-")
    stranger = subprocess.Popen(["sleep", "30"])
    try:
        with open(os.path.join(folder, "gary.pid"), "w") as f:
            f.write("%d\n" % stranger.pid)      # as after a power cut: the number now belongs to someone else
        assert gary_io.gary_pid(os.path.join(folder, "gary.pid")) is None
        assert gary_io.press_gary(os.path.join(folder, "gary.pid")) is False
        time.sleep(0.1)
        assert stranger.poll() is None, "the other program must still be running"
        for text in ("", "not a number", "1", str(os.getpid()), "999999999"):
            with open(os.path.join(folder, "gary.pid"), "w") as f:
                f.write(text)
            assert gary_io.gary_pid(os.path.join(folder, "gary.pid")) is None, text
        assert gary_io.gary_pid(os.path.join(folder, "missing.pid")) is None
        assert gary_io.looks_like_gary("gary") and gary_io.looks_like_gary("gary_device.py")
        assert not gary_io.looks_like_gary("gary_io.py") and not gary_io.looks_like_gary("sync.py")
    finally:
        stranger.kill()
        stranger.wait()
        shutil.rmtree(folder)


def test_no_gpio_fails_quietly():
    """On a machine with no GPIO library the script says so and exits 0."""
    for name in ("rpi_gpio", "RPi", "gpiozero"):
        try:
            __import__(name)
        except Exception:
            continue
        raise Skip("this machine has a GPIO library (%s)" % name)
    folder = tempfile.mkdtemp(prefix="gary-io-")
    try:
        out = subprocess.run([PY, os.path.join(DEVICE, "gary_io.py"), "--dir", folder],
                             capture_output=True, text=True, timeout=20)
        assert out.returncode == 0, out.stderr
        assert "Gary is not affected" in out.stdout
        demo = subprocess.run([PY, os.path.join(DEVICE, "gary_io.py"), "--dir", folder, "--fake", "--demo"],
                              capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        assert demo.returncode == 0 and demo.stdout.count("\n") >= 3, demo.stdout + demo.stderr
    finally:
        shutil.rmtree(folder)


# --------------------------------------------------------------------------
# sync.py: no network, then catching up
# --------------------------------------------------------------------------
class Stub:
    """A tiny stand-in for the backend: remembers what was posted."""

    def __init__(self, quests=None):
        self.bodies, self.quests = [], quests or []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, payload):
                data = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._send({"quests": stub.quests})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
                stub.bodies.append(body)
                self._send({"accepted": len(body.get("events", [])), "duplicates": 0, "results": []})

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.api = "http://127.0.0.1:%d" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def events(self):
        return [e for body in self.bodies for e in body.get("events", [])]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def sync_once(folder, api):
    return subprocess.run([PY, os.path.join(DEVICE, "sync.py"), "--dir", folder, "--api", api, "--once"],
                          capture_output=True, text=True, timeout=60)


def test_sniffs_with_no_network_are_uploaded_when_it_returns():
    folder = tempfile.mkdtemp(prefix="gary-sync-")
    journal = os.path.join(folder, "journal.jsonl")
    try:
        with open(journal, "w") as f:
            for i in range(3):
                f.write(json.dumps({"id": "walk-%d" % i, "ts": "2026-11-21T15:0%d:00Z" % i, "type": "discovery",
                                    "device": "gary-01", "label": "bench", "friend": False}) + "\n")
        # 1. on the walk: nothing is listening
        offline = sync_once(folder, "http://127.0.0.1:%d" % free_port())
        assert offline.returncode == 1 and "offline" in offline.stdout, offline.stdout
        assert not os.path.exists(os.path.join(folder, "sync.state")), "nothing was marked as sent"
        assert len(read_lines(journal)) == 3, "the journal is untouched"

        # 2. back on Wi-Fi: all three go up, once
        stub = Stub(quests=[
            {"id": "q-active", "target": "dog", "xp": 20, "title": "Find a dog at Gibbons Park", "herd": True},
            {"id": "q-other", "target": "bench", "xp": 40, "title": "Find a bench\tat Harris Park"},
        ])
        try:
            online = sync_once(folder, stub.api)
            assert online.returncode == 0 and "uploaded 3 events" in online.stdout, online.stdout
            assert [e["id"] for e in stub.events()] == ["walk-0", "walk-1", "walk-2"]
            # the device says what its own clock reads, so the backend can correct a wrong one
            sent_at = stub.bodies[0]["sent_at"]
            assert sent_at.endswith("Z") and "T" in sent_at and "." in sent_at, sent_at
            # quests arrive in the backend's order: the active one stays first
            with open(os.path.join(folder, "quests.tsv")) as f:
                rows = [line.rstrip("\n").split("\t") for line in f if not line.startswith("#")]
            assert rows == [["q-active", "dog", "20", "Find a dog at Gibbons Park", "herd"],
                            ["q-other", "bench", "40", "Find a bench at Harris Park"]], rows

            again = sync_once(folder, stub.api)
            assert again.returncode == 0 and "uploaded" not in again.stdout
            assert len(stub.events()) == 3, "nothing is sent twice"

            # 3. a fourth sniff, then a power cut mid-write, then a fifth
            with open(journal, "a") as f:
                f.write(json.dumps({"id": "walk-3", "ts": "2026-11-21T15:10:00Z", "type": "miss"}) + "\n")
                f.write('{"id": "walk-cut", "ts": "20')
            sync_once(folder, stub.api)
            assert [e["id"] for e in stub.events()][3:] == ["walk-3"]
            with open(journal, "a") as f:     # Gary restarts, ends the torn line, writes the next
                f.write("\n" + json.dumps({"id": "walk-4", "ts": "2026-11-21T15:20:00Z", "type": "miss"}) + "\n")
            sync_once(folder, stub.api)
            assert [e["id"] for e in stub.events()][3:] == ["walk-3", "walk-4"], "only the torn line is lost"
        finally:
            stub.close()
    finally:
        shutil.rmtree(folder)


# --------------------------------------------------------------------------
# gary_numbers.py
# --------------------------------------------------------------------------
def test_odd_words_in_a_quest_cannot_break_the_quest_file():
    sync = load("sync")
    quests = [
        {"id": "q-1", "target": "dog", "xp": 20, "title": "Find a dog\tat\nGibbons Park", "herd": True},
        {"id": "q\t2\n", "target": "bench", "xp": 40, "title": None, "herd": "yes"},
        {"id": "", "target": "bird", "xp": 20, "title": "No id"},
        {"id": "q-4", "target": None, "xp": 20, "title": "No target"},
        {"id": "#q-5", "target": "bird", "xp": 20, "title": "Would read as a comment"},
    ]
    lines = [line for line in sync.quests_as_tsv(quests, "http://test").splitlines() if not line.startswith("#")]
    assert lines == ["q-1\tdog\t20\tFind a dog at Gibbons Park\therd", "q 2\tbench\t40\tFind a bench"], lines
    # and Gary reads the file the same way
    try:
        device = load("gary_device")
    except ImportError:
        raise Skip("the quest file is written correctly; reading it back needs the device requirements")
    folder = tempfile.mkdtemp(prefix="gary-tsv-")
    try:
        path = os.path.join(folder, "quests.tsv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(sync.quests_as_tsv(quests, "http://test"))
        loaded = [(q.id, q.label, q.xp, q.text, q.herd) for q in device.load_quests(path)]
        assert loaded == [("q-1", "dog", 20, "Find a dog at Gibbons Park", True),
                          ("q 2", "bench", 40, "Find a bench", False)], loaded
    finally:
        shutil.rmtree(folder)


def test_numbers_turns_a_run_into_a_table_row():
    numbers = load("gary_numbers")
    folder = tempfile.mkdtemp(prefix="gary-numbers-")
    try:
        # 101 frames, one every 100 ms: 10 frames per second for 10 seconds
        with open(os.path.join(folder, "latency.csv"), "w") as f:
            f.write("frame,frame_to_decision_ms,model_ms,t_ms\n")
            for i in range(101):
                f.write("%d,%.2f,%.2f,%.1f\n" % (i, 60 + (i % 10), 50.0, i * 100.0))
        now = time.time()
        stamp = lambda ago: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - ago))  # noqa: E731
        with open(os.path.join(folder, "journal.jsonl"), "w") as f:
            f.write(json.dumps({"id": "old", "ts": stamp(3600), "type": "discovery", "latency_ms": 999.0}) + "\n")
            for i, ms in enumerate((40.0, 50.0, 60.0)):
                f.write(json.dumps({"id": "s%d" % i, "ts": stamp(5 - i), "type": "discovery", "latency_ms": ms}) + "\n")
            f.write(json.dumps({"id": "m", "ts": stamp(1), "type": "mood", "phase": "before", "value": 3}) + "\n")
            f.write('{"id": "cut", "ts": "20')
        lat = numbers.read_latency(os.path.join(folder, "latency.csv"))
        assert lat["frames"] == 101 and abs(lat["fps"] - 10.0) < 1e-6 and lat["model_ms"] == 50.0
        assert lat["p50"] == 64.0 and lat["p95"] == 69.0 and lat["max"] == 69.0, lat   # nearest rank
        events, damaged = numbers.read_events(os.path.join(folder, "journal.jsonl"))
        assert len(events) == 5 and damaged == 1
        sniffs = numbers.sniff_times(events, now, lat["seconds"])
        assert sniffs == [40.0, 50.0, 60.0], "only this run's sniffs: %r" % sniffs
        row = numbers.table_row("QNX, normal", lat, sniffs)
        assert row == "| QNX, normal | 101 | 10.0 | 50 ms | 64 ms | 69 ms | 69 ms | 3 | 50 ms | 60 ms | 60 ms |", row

        # --append puts rows under the right table, in order, and leaves the rest of the page alone
        page = os.path.join(folder, "qnx-numbers.md")
        with open(page, "w") as f:
            f.write("# Numbers\n\nIntro.\n\n%s\n%s\n\n## Another table\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n"
                    % (numbers.HEADER, numbers.RULE))
        for label in ("first", "second"):
            out = subprocess.run([PY, os.path.join(DEVICE, "gary_numbers.py"), "--dir", folder, "--label", label,
                                  "--append", page], capture_output=True, text=True)
            assert out.returncode == 0, out.stderr
        with open(page) as f:
            lines = f.read().split("\n")
        at = lines.index(numbers.RULE)
        assert lines[at + 1].startswith("| first |") and lines[at + 2].startswith("| second |") and lines[at + 3] == ""
        assert lines[-4:] == ["| a | b |", "| --- | --- |", "| 1 | 2 |", ""]

        check = subprocess.run([PY, os.path.join(DEVICE, "gary_numbers.py"), "--dir", folder, "--check-journal"],
                               capture_output=True, text=True)
        assert "5 events" in check.stdout and "1 damaged line" in check.stdout and "Nothing else is lost" in check.stdout
        os.remove(os.path.join(folder, "latency.csv"))
        missing = subprocess.run([PY, os.path.join(DEVICE, "gary_numbers.py"), "--dir", folder], capture_output=True, text=True)
        assert missing.returncode != 0 and "latency.csv" in missing.stderr
    finally:
        shutil.rmtree(folder)


# --------------------------------------------------------------------------
# Gary himself (the Python version): quest choice and the torn-line repair
# --------------------------------------------------------------------------
def gary_device():
    try:
        return load("gary_device")
    except (ImportError, SystemExit) as exc:
        raise Skip("gary_device.py needs its requirements (%s)" % exc)


def test_a_quest_that_can_be_finished_wins_over_a_herd_quest_that_cannot():
    gd = gary_device()
    Q = gd.Quest
    quests = [Q("herd-bench", "bench", 20, "Bench, with a friend", True), Q("solo-bench", "bench", 20, "Bench", False),
              Q("dog", "dog", 20, "Dog", False)]
    pick = lambda done, things, friend: tuple(q.id if q else None for q in gd.choose_quest(quests, done, things, friend))  # noqa: E731
    assert pick(set(), {"bench": 0.9}, False) == ("solo-bench", "solo-bench"), "alone: the solo quest, not 'needs a friend'"
    assert pick(set(), {"bench": 0.9}, True) == ("herd-bench", "herd-bench"), "with a friend: file order (the active quest is first)"
    assert pick({"solo-bench"}, {"bench": 0.9}, False) == ("herd-bench", None), "only the herd quest is left: found, not completed"
    assert pick(set(), {"bench": 0.6, "dog": 0.9}, False) == ("dog", "dog"), "the surest target wins"
    assert pick(set(), {"cup": 0.9}, False) == (None, None)
    assert pick({"herd-bench", "solo-bench", "dog"}, {"bench": 0.9, "dog": 0.9}, True) == (None, None)


def test_gary_says_found_not_it_or_move_closer():
    gd = gary_device()
    say = gd.voice_clips
    # label, quest, completed, new, friend, any_open, all_done
    assert say("bottle", "q", "q", True, False, False, False) == ["good", "say_found_bottle"]
    assert say("bird", None, None, True, False, True, False) == ["bad", "say_not_it", "say_bird"], "a quest is open"
    assert say("bird", None, None, True, False, False, False) == ["good", "say_bird", "say_new"], "no quest: a first find"
    assert say("bird", None, None, False, False, False, False) == ["good", "say_bird"]
    assert say("bench", "q", None, False, False, True, False) == ["good", "say_bench", "say_need_friend"], "a herd quest"
    assert say("trash can", "q", "q", False, True, False, True) == ["good", "say_found_trash_can", "say_herd", "say_done"]
    # The beeps agree with the buzzer: one for good, three for bad.
    for clips, event, open_labels in ((say("bird", None, None, True, False, True, False), {"type": "discovery", "label": "bird"}, {"bottle"}),
                                      (say("bottle", "q", "q", True, False, False, False), {"type": "discovery", "label": "bottle", "quest_id": "q"}, {"bottle"}),
                                      (say("dog", None, None, True, False, False, False), {"type": "discovery", "label": "dog"}, set())):
        assert (clips[0] == "good") == gary_io.is_good(event, open_labels)
    for name in ("good", "bad", "unsure"):
        assert os.path.exists(os.path.join(DEVICE, "sounds", name + ".wav")), "commit sounds/%s.wav: the QNX Gary does not make it" % name


# --------------------------------------------------------------------------
# Talking to Gary (gary_talk.py). No network: Gemini and ElevenLabs are stand-ins.
# --------------------------------------------------------------------------
def test_go_gary_wakes_him_only_when_said_to_him():
    gt = load("gary_talk")
    assert gt.wake_split("Go Gary, what am I looking at?") == (True, "what am i looking at")
    assert gt.wake_split("Hey Garry!") == (True, "")
    assert gt.wake_split("uh, go Gary what's that") == (True, "what's that")
    assert gt.wake_split("Okay Gary.")[0] and gt.wake_split("yo gary")[0]
    for chatter in ("Gary is a good name", "I think the goat project is cool, go Gary go",
                    "let's go", "", None, "go team"):
        assert gt.wake_split(chatter)[0] is False, chatter

    # Gemini only writes down what it heard; the code decides. "Go Gary" alone gets "Go ahead".
    def wake(heard, answer="Ooh, a squirrel!"):
        reply = json.dumps({"heard": heard, "answer": answer})
        return gt.is_wake(b"\0\0" * 1600, "key", None, opener=stand_in(reply))
    assert wake("Go Gary") == (True, None), "Go Gary alone: Go ahead, then listen"
    woke, reply = wake("Go Gary, what's that?")
    assert woke and reply["say"] == "Ooh, a squirrel!" and reply["do"] is None
    assert wake("Gary is a good name") == (False, None)


def stand_in(text):
    """A stand-in for urlopen that returns a Gemini reply holding `text`."""
    import io

    class Reply(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False
    body = json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]}).encode()
    return lambda req, timeout=None: Reply(body)


def test_the_ears_cut_sound_into_things_said():
    import math
    import struct
    gt = load("gary_talk")

    def frames(level, seconds):
        n = int(seconds * 50)
        tone = struct.pack("<320h", *[int(level * math.sin(i / 3.0)) for i in range(320)])
        return [tone] * n

    ears = gt.Utterances()
    stream = frames(60, 1.0) + frames(4000, 0.8) + frames(60, 1.0) + frames(4000, 0.05) + frames(60, 1.0)
    said = [s for s in (ears.feed(f) for f in stream) if s]
    assert len(said) == 1, "one thing said; the 50 ms bump is not speech"
    assert 0.8 <= len(said[0]) / 32000.0 <= 1.8, "the words, a little before and the pause after"
    # a long, loud room raises the bar: steady noise is not speech
    ears = gt.Utterances()
    assert not [s for s in (ears.feed(f) for f in frames(500, 0.2) + frames(600, 3.0)) if s and len(s) > 32000 * 2.5]


def test_gary_hears_only_fresh_labels_and_never_a_person():
    gt = load("gary_talk")
    folder = tempfile.mkdtemp(prefix="gary-talk-")
    try:
        path = os.path.join(folder, "seeing.json")
        assert gt.read_seeing(path) is None
        with open(path, "w") as f:
            json.dump({"labels": {"bird": 0.86, "tree": 0.5}, "friend": True, "ts": 1000}, f)
        assert gt.read_seeing(path, clock=lambda: 1001.0)["labels"]["bird"] == 0.86
        assert gt.read_seeing(path, clock=lambda: 1010.0) is None, "old: Gary is not looking any more"
        import io
        url = gt.read_seeing("http://localhost:8800/api/seeing", clock=lambda: 1001.0,
                             opener=lambda u, timeout: io.BytesIO(open(path, "rb").read()))
        assert url["labels"]["bird"] == 0.86, "talk on a laptop reads the Pi's seeing over HTTP"
        def down(u, timeout):
            raise OSError("no route")
        assert gt.read_seeing("http://localhost:8800/api/seeing", opener=down) is None
        said = gt.now_context(gt.read_seeing(path, clock=lambda: 1001.0))
        assert "bird (86%), tree (50%)" in said and "A friend is in the frame." in said
        assert "person" not in said and "nothing he can name" in gt.now_context(None)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_go_gary_then_a_question_gets_go_ahead_then_an_answer():
    gt = load("gary_talk")
    played, log = [], []

    class Mouth:
        speaking = threading.Event()

        def say_clip(self, name):
            played.append(name)

        def say_pcm(self, pcm):
            played.append(("answer", pcm))

    now = [0.0]
    woke = iter([(True, ""), (False, ""), (True, "Hi! That's a duck.")])
    talk = gt.Talk(Mouth(), "g", "e", os.path.join(tempfile.gettempdir(), "no-seeing.json"), say=log.append,
                   ask_wake=lambda pcm, key, seeing: next(woke),
                   ask_answer=lambda q, key, seeing: "A goose! They mate for life.",
                   speak=lambda text, key: text.encode(), clock=lambda: now[0])
    speech = b"\1\0" * 16000
    assert talk.heard(speech) == "woke" and played == ["say_go_ahead"]
    assert talk.heard(speech) == "answered", "the next thing said is the question"
    assert played[1:] == ["say_thinking", ("answer", b"A goose! They mate for life.")]
    assert talk.state == talk.IDLE
    assert talk.heard(speech) == "ignored", "back to waiting for Go Gary"
    assert talk.heard(speech) == "answered" and played[-1] == ("answer", b"Hi! That's a duck."), "one breath"
    # Go Gary, then nothing: after a while he stops listening
    talk.wake()
    now[0] += gt.LISTEN_FOR + 1
    talk.tick()
    assert talk.state == talk.IDLE
    # Gemini down: Gary says so kindly, and the question is never printed
    def broken(*a):
        raise gt.TalkError("Gemini answered HTTP 503")
    talk.ask_answer = broken
    talk.wake()
    assert talk.heard(speech) == "error" and played[-1] == "say_ears"
    assert talk.heard(b"\1\0" * 16000 * 7) == "ignored", "too long for Go Gary: someone talking nearby"


def test_in_a_loud_room_every_question_needs_go_gary_even_after_gary_asks_one():
    gt = load("gary_talk")

    class Mouth:
        speaking = threading.Event()

        def say_clip(self, name):
            pass

        def say_pcm(self, pcm):
            pass

    asks = {"say": "A short one or a long one?", "listen": True}
    speech = b"\1\0" * 16000

    def talk_with(strict):
        woke = iter([(True, asks), (False, None)])
        return gt.Talk(Mouth(), "g", "e", "none.json", say=lambda *_: None, strict=strict,
                       ask_wake=lambda pcm, key, seeing: next(woke),
                       ask_answer=lambda q, key, seeing: "Short it is.", speak=lambda text, key: b"")

    easy = talk_with(False)
    assert easy.heard(speech) == "answered" and easy.state == easy.LISTENING
    assert easy.heard(speech) == "answered", "he asked, so the next thing said is taken as the answer"

    strict = talk_with(True)
    assert strict.heard(speech) == "answered" and strict.state == strict.IDLE
    assert strict.heard(speech) == "ignored", "a voice nearby, with no Go Gary: not an answer"
    # "Go Gary" alone still opens the short window for one question
    strict.wake()
    assert strict.state == strict.LISTENING


def test_gary_reads_the_app_but_never_a_mood():
    gt = load("gary_talk")
    with open(os.path.join(DEVICE, "..", "contract", "examples", "state.json"), encoding="utf-8") as f:
        state = json.load(f)
    said = gt.app_context(state, ["bench", "duck"])
    assert "Gary is a Scrambler with 80 XP, 70 XP to the next stage." in said
    assert '"Find a water bottle at your table" at Hack Western, your table' in said
    assert "If they pick long: no long quest is open." in said
    assert "your herd is 3 of 6 herds" in said and "THINGS GARY CAN FIND" in said
    assert "mood" not in said.lower() and "check-in" not in said.lower()
    assert "not reachable" in gt.app_context(None)
    things = gt.read_things()
    assert "duck" in things and "person" not in things and "laptop" not in things, "outdoor things only"
    # whatever Gemini sends back, Gary gets something safe to use
    assert gt.reply_of('{"say": "Hi!", "do": {"action": "delete_everything"}}')["do"] is None
    assert gt.reply_of("not json at all")["say"] == "not json at all"
    assert gt.reply_of('{"say": "Sure", "listen": "yes"}')["listen"] is False


def test_gary_can_pick_a_quest_and_make_one():
    gt = load("gary_talk")
    sent = []

    class Reply(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def backend(req, timeout=None):
        body = json.loads(req.data) if req.data else None
        sent.append((req.full_url, body, dict(req.header_items())))
        if req.full_url.endswith("/api/quest/choose"):
            quest = None if body["time"] == "long" else {"id": "q-1", "title": "Find a bench at Harris Park", "place": "Harris Park"}
            return Reply(json.dumps({"quest": quest, "state": {"quests_open": 2}}).encode())
        if req.full_url.endswith("/api/quests"):
            return Reply(json.dumps({"accepted": [q["id"] for q in body["quests"]], "rejected": []}).encode())
        return Reply(b"{}")

    app = gt.App("http://gary.test/", scout_key="sk", opener=backend)
    talk = gt.Talk(None, "g", "e", "none.json", say=lambda *_: None, app=app)
    pick = {"say": "Here's a bench quest!", "do": {"action": "choose_quest", "time": "short"}}
    assert talk.act(pick) == "Here's one: Find a bench at Harris Park, at Harris Park."
    assert sent[0][0] == "http://gary.test/api/quest/choose" and sent[0][1] == {"time": "short"}
    assert "No long quests are open" in talk.act({"say": "x", "do": {"action": "choose_quest", "time": "long"}})

    made = {"say": "Added!", "do": {"action": "create_quest", "target": "Duck", "place": "the pond", "time": "short"}}
    assert talk.act(made) == "Added!"
    url, body, headers = sent[-2]  # then a refresh of the state
    quest = body["quests"][0]
    assert url.endswith("/api/quests") and headers.get("X-scout-key") == "sk"
    assert quest["target"] == "duck" and quest["title"] == "Find a duck at the pond" and quest["xp"] == 20
    assert quest["source"] == "gary", "a quest Gary made is never marked as the scout's"
    n = len(sent)
    assert "wouldn't let me" in talk.act({"say": "Added!", "do": {"action": "create_quest", "target": "penguin"}})
    assert len(sent) == n, "a thing Gary cannot find is never sent"
    no_app = gt.Talk(None, "g", "e", "none.json", say=lambda *_: None, app=gt.App(""))
    assert "can't reach the app" in no_app.act(pick)


def test_let_me_think_is_never_the_same_twice_running():
    gt = load("gary_talk")

    class Mouth:
        def clip(self, name):
            return name if name in gt.THINKING else None
    talk = gt.Talk(Mouth(), "g", "e", "none.json")
    picks = [talk.thinking_clip() for _ in range(40)]
    assert all(a != b for a, b in zip(picks, picks[1:])) and set(picks) == set(gt.THINKING)
    for name in gt.THINKING + ("say_go_ahead", "say_ears"):
        assert os.path.exists(os.path.join(DEVICE, "sounds", name + ".wav")), name


def test_holding_the_button_asks_gary_to_listen():
    folder = tempfile.mkdtemp(prefix="gary-io-")
    asked, real = [], gary_io.ask_talk
    gary_io.ask_talk = lambda path: asked.append(path) or True
    try:
        pins, said = ScriptPins(), []
        io = gary_io.Io(pins, folder, said.append)
        t = 0.0
        for level, seconds in ((False, 0.2), (True, 0.3), (False, 0.6), (True, 1.2), (False, 0.3)):
            pins.level = level
            end = t + seconds
            while t < end:
                io.step(t)
                t += 0.005
        assert len(asked) == 1, "a short press is a sniff only; a long one also talks: %r" % said
        assert io.presses == 2
    finally:
        gary_io.ask_talk = real
        shutil.rmtree(folder, ignore_errors=True)


def test_the_voice_starts_when_the_cue_is_three_quarters_through():
    gd = gary_device()
    sounds = os.path.join(DEVICE, "sounds")
    assert abs(gd.wav_seconds(os.path.join(sounds, "good.wav")) - 0.35) < 0.02
    assert gd.wav_seconds(os.path.join(sounds, "missing.wav")) == 0.0
    started = []
    speaker = gd.Speaker(sounds, command="true")
    speaker._play_all = lambda paths, lead=None: started.append((len(paths), lead))
    real = gd.threading.Thread
    gd.threading.Thread = lambda target, args, daemon: type("T", (), {"start": lambda self: target(*args)})()
    try:
        speaker.play("unsure", "say_nothing")
        speaker.play("good")                  # a cue alone plays to its end
        speaker.play("say_bird", "say_new")   # not a cue: one after another
    finally:
        gd.threading.Thread = real
    want = gd.wav_seconds(os.path.join(sounds, "unsure.wav")) * 0.75
    assert started[0][0] == 2 and abs(started[0][1] - want) < 1e-9, started
    assert started[1:] == [(1, None), (2, None)], started


def test_every_clip_gary_can_ask_for_is_made_by_make_voice():
    import wave
    mv = load("make_voice")
    labels = mv.read_labels()
    made = mv.lines(labels)
    assert "person" not in labels, "a friend is never named"
    assert made["say_found_bottle"] == "Yes! You found the water bottle!"
    assert made["say_apple"] == "That's an apple!" and made["say_scissors"] == "Those are scissors!"
    assert made["say_nothing"].endswith("Can you move a little closer?")
    for label in labels:
        for prefix in ("say_found_", "say_"):
            assert prefix + label.replace(" ", "_") in made, label
    for fixed in ("say_hello", "say_nothing", "say_not_it", "say_new", "say_need_friend", "say_herd", "say_done"):
        assert fixed in made
        assert mv.performed(fixed, made[fixed], "eleven_v3").startswith("["), "every fixed line has its intonation"
    # eleven_v3 gets cues for how to say a line; any other model would read them aloud, so it gets none
    assert mv.performed("say_found_bottle", made["say_found_bottle"], "eleven_v3") == "[excited] Yes! You found the water bottle!"
    assert mv.performed("say_apple", made["say_apple"], "eleven_v3") == "[curious] That's an apple!"
    assert mv.performed("say_apple", made["say_apple"], "eleven_multilingual_v2") == "That's an apple!"
    # A clip is written whole, as 16-bit mono WAV, from the PCM ElevenLabs sends.
    folder = tempfile.mkdtemp()
    try:
        path = os.path.join(folder, "say_bird.wav")
        mv.write_wav(path, b"\x00\x01" * 800)
        with wave.open(path) as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, mv.RATE, 800)
        assert os.listdir(folder) == ["say_bird.wav"], "no temporary file is left behind"
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_yolo_output_becomes_one_box_per_thing():
    gd = gary_device()
    np = gd.np
    labels = ["person", "bottle", "tree"]
    # anchors: the same bottle twice (overlapping), a person beside it, a tree too faint
    boxes = [[0.5, 0.5, 0.2, 0.4], [0.51, 0.5, 0.2, 0.4], [0.2, 0.5, 0.3, 0.8], [0.8, 0.2, 0.1, 0.1]]
    scores = [[0, 0.9, 0], [0, 0.8, 0], [0.7, 0, 0], [0, 0, 0.3]]
    out = np.array([b + s for b, s in zip(boxes, scores)], dtype=np.float32).T  # [4+K, A], as the model gives it
    for given in (out, out.T):
        got = gd.decode_yolo(given, labels, 0.5)
        assert [f[0] for f in got] == ["bottle", "person"], got
        x0, y0, x1, y1 = got[0][2]
        assert abs(x0 - 0.4) < 1e-5 and abs(y1 - 0.7) < 1e-5, "cx, cy, w, h becomes corners"


def test_the_nature_name_wins_where_both_models_see_the_same_thing():
    gd = gary_device()
    ssd = [("cat", 0.98, (0.1, 0.1, 0.5, 0.5)), ("bottle", 0.9, (0.6, 0.6, 0.9, 0.9))]
    nature = [("squirrel", 0.7, (0.12, 0.1, 0.5, 0.52))]
    assert [f[0] for f in gd.merge(ssd, nature)] == ["bottle", "squirrel"]


def test_every_thing_the_model_knows_is_in_the_contract():
    model = set()
    for name in ("coco_labels.txt", "gary_nature_labels.txt"):  # Gary's two detectors
        with open(os.path.join(DEVICE, "models", name), encoding="utf-8") as f:
            model |= {line.strip() for line in f if line.strip()}
    with open(os.path.join(DEVICE, "..", "contract", "labels.json"), encoding="utf-8") as f:
        doc = json.load(f)
    assert doc["friend"] == "person" and "person" in model
    named = model - {"n/a", "person"}
    assert named == {item["name"] for item in doc["labels"]}, "the device's label files and contract/labels.json disagree"


def test_the_journal_survives_a_power_cut_mid_write():
    gd = gary_device()
    folder = tempfile.mkdtemp(prefix="gary-journal-")
    path = os.path.join(folder, "journal.jsonl")
    try:
        first = gd.Journal(path, "gary-01")
        first.add("discovery", label="bench", score=0.9, friend=False, new=True, quest_id="q-1", latency_ms=40.0)
        with open(path, "a") as f:
            f.write('{"id": "gary-01-1-2", "ts": "2026-11-2')      # the power goes here
        again = gd.Journal(path, "gary-01")                        # restart
        assert again.discovered == {"bench"} and again.done == {"q-1"}, "state is rebuilt from the intact lines"
        again.add("miss", friend=False, latency_ms=38.0)
        with open(path) as f:
            lines = f.read().split("\n")
        assert lines[-1] == "" and len(lines) == 4
        assert json.loads(lines[0])["label"] == "bench" and json.loads(lines[2])["type"] == "miss"
        try:
            json.loads(lines[1])
        except ValueError:
            pass
        else:
            raise AssertionError("the torn line should be the only unreadable one")
    finally:
        shutil.rmtree(folder)


# --------------------------------------------------------------------------
# start_gary.sh and stop_gary.sh, with the stand-in Gary
# --------------------------------------------------------------------------
def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:  # a finished child that nobody has collected yet is not alive
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return True


def test_start_and_stop_scripts_run_gary_as_a_field_device():
    if os.name != "posix" or not shutil.which("sh"):
        raise Skip("needs a POSIX shell")
    folder = tempfile.mkdtemp(prefix="gary-field-")
    stub = Stub()
    try:
        for name in ("start_gary.sh", "stop_gary.sh", "gary_io.py", "sync.py"):
            shutil.copy(os.path.join(DEVICE, name), folder)
        shutil.copy(os.path.join(TESTS, "fake_gary.py"), folder)
        with open(os.path.join(folder, "gary.env"), "w") as f:
            f.write('GARY_CMD="%s fake_gary.py"\nGARY_FLAGS=""\nGARY_PYTHON="%s"\nGARY_API=%s\n'
                    'GARY_BUTTON_PIN=none\nGARY_BUZZER_PIN=none\nGARY_START_WAIT=1\n' % (PY, PY, stub.api))
        with open(os.path.join(folder, "journal.jsonl"), "w") as f:
            f.write('{"id": "before-1", "ts": "2026-11-21T15:00:00Z", "type": "miss"}\n')
        with open(os.path.join(folder, "gary.pid"), "w") as f:
            f.write("1\n")     # a leftover from before a power cut

        def sh(*args):
            return subprocess.run(["sh", os.path.join(folder, "start_gary.sh")] + list(args), capture_output=True,
                                  text=True, timeout=60, stdin=subprocess.DEVNULL)

        def pid():
            try:
                with open(os.path.join(folder, "gary.pid")) as f:
                    return int(f.read())
            except (OSError, ValueError):
                return None

        out = sh()
        assert "Gary: up" in out.stdout, out.stdout + out.stderr
        first = pid()
        assert first and first != 1 and alive(first)
        assert wait_for(lambda: [e["id"] for e in stub.events()] == ["before-1"]), "sync uploads what was waiting"

        # a second start changes nothing
        again = sh()
        assert "Gary: already running" in again.stdout and "sync: already running" in again.stdout
        assert pid() == first

        # the button path works: a signal is one journal line
        os.kill(first, signal.SIGUSR1)
        assert wait_for(lambda: len(read_lines(os.path.join(folder, "journal.jsonl"))) == 2)
        assert wait_for(lambda: len(stub.events()) == 2), "and sync carries it to the backend"

        # logging out (a hangup) stops nothing
        os.kill(first, signal.SIGHUP)
        time.sleep(0.3)
        assert alive(first)

        # if Gary dies, he is started again
        os.kill(first, signal.SIGKILL)
        second = wait_for(lambda: pid() if pid() not in (None, first) and alive(pid()) else None, seconds=12)
        assert second, "Gary was not restarted"

        status = sh("status")
        assert "Gary: up (pid %d)" % second in status.stdout and "sync: up" in status.stdout, status.stdout

        stop = subprocess.run(["sh", os.path.join(folder, "stop_gary.sh")], capture_output=True, text=True, timeout=60)
        assert "Gary: stopped" in stop.stdout and "sync: stopped" in stop.stdout, stop.stdout
        assert wait_for(lambda: not alive(second)), "Gary is gone"
        assert pid() is None, "gary.pid is removed on a clean stop"
        assert "Gary: not running" in sh("status").stdout
        time.sleep(4)
        assert pid() is None, "and nothing starts him again"

        # --fresh sets the journal aside and starts clean
        fresh = sh("--fresh")
        assert "Fresh run" in fresh.stdout and "Gary: up" in fresh.stdout, fresh.stdout
        baks = [n for n in os.listdir(folder) if n.startswith("journal.") and n.endswith(".bak")]
        assert len(baks) == 1 and not os.path.exists(os.path.join(folder, "sync.state"))
        assert read_lines(os.path.join(folder, "journal.jsonl")) == []
    finally:
        subprocess.run(["sh", os.path.join(folder, "stop_gary.sh")], capture_output=True, timeout=60)
        stub.close()
        shutil.rmtree(folder, ignore_errors=True)


# --------------------------------------------------------------------------
if __name__ == "__main__":
    failed = skipped = 0
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn()
        except Skip as why:
            skipped += 1
            print("  skip  %s  (%s)" % (name, why))
        except Exception:
            failed += 1
            import traceback
            print("  FAIL  %s" % name)
            traceback.print_exc()
        else:
            print("  ok    %s" % name)
    print("%d device tests, %d failed, %d skipped" % (len(tests), failed, skipped))
    sys.exit(1 if failed else 0)
