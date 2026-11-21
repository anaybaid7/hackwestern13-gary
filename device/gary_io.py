#!/usr/bin/env python3
"""gary_io.py - Gary's button and buzzer. Standard library only.

It runs beside Gary and never touches the vision code:

    button pressed         ->  kill -USR1 <pid in gary.pid>   = one Sniff Test
    new line in the journal ->  a beep pattern on the buzzer

So a missing button, a missing buzzer or a crash of this script cannot stop
Gary. Enter in Gary's own terminal still works as the button.

(The plan called this file io.py. That name collides with Python's built-in
io module, so it is gary_io.py.)

Wiring (Grove cable: red = power, black = ground, yellow = signal, white unused)

    Button   red -> pin 1  (3.3 V)   black -> pin 6 (GND)   yellow -> pin 11 (GPIO17)
    Buzzer   red -> pin 17 (3.3 V)   black -> pin 9 (GND)   yellow -> pin 13 (GPIO27)

    Never use the 5 V pins: the Pi's inputs are 3.3 V only.
    Grove plugs do not fit the Pi's pins. Use Grove-to-jumper cables, or a
    Grove Base HAT (then pass its socket numbers, for example
    --button-pin 5 --buzzer-pin 16 for sockets D5 and D16).

Run it from the device folder (QNX, or Raspberry Pi OS)

    python3 gary_io.py                    button on GPIO17, buzzer on GPIO27
    python3 gary_io.py --demo             play every pattern once, then exit
    python3 gary_io.py --fake             no hardware: Enter = button, beeps are printed
    python3 gary_io.py --mood before 3    write one private mood check-in to the journal

What you hear

    one quick beep                  good: the quest's thing, or a find with no quest open
    three quick beeps               bad: not what the quest is looking for
    beep... beeep (two, the second  unsure: nothing Gary can name. Not a failure:
      longer, like a question)        he is puzzled and asks you to move closer
    three slow beeps                the button was pressed but Gary is not running

Hold the button for 0.8 s to talk to Gary (gary_talk.py), the same as saying "Go Gary".

Gary's speaker says the rest ("You found the water bottle!"): see make_voice.py.

On QNX the GPIO module is rpi_gpio; on Raspberry Pi OS it is RPi.GPIO or
gpiozero. This script uses whichever it finds, and only the plainest calls
(setup, input, output), so it does not depend on edge detection or PWM.
"""
import argparse
import datetime
import importlib
import json
import os
import re
import signal
import sys
import threading
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# Beep patterns
# --------------------------------------------------------------------------
# A pattern is a list of (seconds, tone). Tone 0 is silence. The Grove buzzer
# is an on/off part, so any other tone simply means "on" and the patterns
# differ by rhythm. With --tones the tone is also played as a pitch (PWM).
# Good is one beep and bad is three, so they are told apart by counting, even
# on a one-pitch buzzer. Gary's speaker says the details.
PATTERNS = {
    "good": [(0.06, 1320)],                                                  # beep
    "bad": [(0.06, 880), (0.06, 0), (0.06, 880), (0.06, 0), (0.06, 880)],    # beep-beep-beep
    "unsure": [(0.06, 1100), (0.12, 0), (0.15, 1320)],                       # beep... beeep? (puzzled)
    "tap": [(0.03, 1760)],
    "not_ready": [(0.20, 220), (0.20, 0), (0.20, 220), (0.20, 0), (0.20, 220)],
}
# What --demo plays, in order.
DEMO = [
    ("good (the quest's thing, or a find with no quest open): one quick beep",
     {"type": "discovery", "new": True, "quest_id": "q"}),
    ("bad (not what we're looking for): three quick beeps", {"type": "discovery", "label": "dog", "_open": ["bottle"]}),
    ("unsure (nothing he can name): beep... beeep?", {"type": "miss"}),
]


def is_good(event, open_labels=()):
    """A sniff is good when it finds the quest's thing, or when no quest is
    open; bad when it names something else while a quest is open.
    voice_clips() in gary_device.py makes the same call. (A miss is neither:
    see pattern_for.)"""
    return bool(event.get("quest_id")) or not open_labels or event.get("label") in open_labels


def pattern_for(event, open_labels=()):
    """One journal line -> the beeps for it. [] for a line that makes no sound.
    open_labels: the targets of the quests still open (QuestBook)."""
    kind = event.get("type")
    if kind == "miss":
        return list(PATTERNS["unsure"])
    if kind == "discovery":
        return list(PATTERNS["good" if is_good(event, open_labels) else "bad"])
    if kind == "mood":
        return list(PATTERNS["tap"])  # a quiet "noted". Nothing about the mood itself
    return []


class QuestBook:
    """Which quests are still open, from quests.tsv (or quests.seed.tsv until
    sync.py has written it, as Gary does) and the quest ids in the journal."""

    def __init__(self, folder, journal_path, friend_label="person"):
        self.folder, self.friend_label = folder, friend_label
        self.done = set()
        try:
            with open(journal_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    self.note(line)
        except OSError:
            pass

    def note(self, line_or_event):
        """Remember a finished quest from a journal line (text or parsed)."""
        event = line_or_event
        if isinstance(event, str):
            try:
                event = json.loads(event)
            except ValueError:
                return
        if isinstance(event, dict) and event.get("quest_id"):
            self.done.add(event["quest_id"])

    def open_labels(self):
        for name in ("quests.tsv", "quests.seed.tsv"):
            path = os.path.join(self.folder, name)
            if not os.path.exists(path):
                continue
            labels = set()
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    for raw in f:
                        if raw.lstrip().startswith("#") or not raw.strip():
                            continue
                        parts = raw.rstrip("\n").split("\t")
                        if len(parts) > 1 and parts[0].strip() not in self.done:
                            label = parts[1].strip().lower()
                            if label and label != self.friend_label:
                                labels.add(label)
            except OSError:
                return set()
            return labels
        return set()


class Beeper:
    """Plays patterns one after another without ever blocking the loop.
    Call tick(now) often; it switches the buzzer when a step is due."""

    GAP = 0.25         # silence between two patterns
    MAX_QUEUED = 4.0   # seconds. Beyond this, new patterns are dropped

    def __init__(self, sound):
        self.sound = sound      # sound(tone): 0 = off
        self.steps = deque()
        self.until = None       # when the step being played ends
        self.queued = 0.0

    def play(self, steps):
        if not steps or self.queued > self.MAX_QUEUED:
            return
        if self.busy():
            steps = [(self.GAP, 0)] + list(steps)
        for step in steps:
            self.steps.append(step)
            self.queued += step[0]

    def busy(self):
        return bool(self.steps) or self.until is not None

    def tick(self, now):
        if self.until is not None and now < self.until:
            return
        if self.steps:
            seconds, tone = self.steps.popleft()
            self.queued = max(0.0, self.queued - seconds)
            self.sound(tone)
            self.until = now + seconds
        elif self.until is not None:
            self.sound(0)  # always end silent
            self.until = None

    def stop(self):
        self.steps.clear()
        self.queued, self.until = 0.0, None
        self.sound(0)


# --------------------------------------------------------------------------
# Button
# --------------------------------------------------------------------------
class Button:
    """Turns a noisy level into clean presses. The level must hold for
    `debounce` seconds to count, and two presses closer than `gap` are one,
    so one push of the button is exactly one Sniff Test."""

    def __init__(self, debounce=0.03, gap=0.4):
        self.debounce, self.gap = debounce, gap
        self.state = None       # the accepted level. None until the first reading
        self.since = None       # when the raw level started to differ from it
        self.last_press = None

    def update(self, level, now):
        """Feed the raw level (True = pressed). Returns True once per press."""
        level = bool(level)
        if self.state is None:
            self.state = level  # a button held (or stuck) at start is not a press
            return False
        if level == self.state:
            self.since = None
            return False
        if self.since is None:
            self.since = now
        if now - self.since < self.debounce:
            return False
        self.state, self.since = level, None
        if not level:
            return False        # released
        if self.last_press is not None and now - self.last_press < self.gap:
            return False        # a bounce or a double tap: still one press
        self.last_press = now
        return True


# --------------------------------------------------------------------------
# The journal, followed like `tail -f`
# --------------------------------------------------------------------------
class JournalTail:
    """Yields the events written after this script started."""

    BURST = 3  # more new lines than this at once: beep for the last one only

    def __init__(self, path):
        self.path = path
        try:
            self.pos = os.path.getsize(path)  # old lines make no sound
        except OSError:
            self.pos = 0

    def poll(self):
        try:
            size = os.path.getsize(self.path)
        except OSError:
            self.pos = 0  # no journal (not yet, or set aside): read the next one from its top
            return []
        if size < self.pos:
            self.pos = 0  # a new, shorter journal took its place
        if size == self.pos:
            return []
        with open(self.path, "rb") as f:
            f.seek(self.pos)
            data = f.read()
        end = data.rfind(b"\n")
        if end < 0:
            return []  # a line still being written
        self.pos += end + 1
        events = []
        for line in data[:end].split(b"\n"):
            try:
                event = json.loads(line.decode("utf-8"))
            except ValueError:
                continue  # a torn line after a power cut
            if isinstance(event, dict):
                events.append(event)
        return events[-1:] if len(events) > self.BURST else events


# --------------------------------------------------------------------------
# Talking to Gary
# --------------------------------------------------------------------------
def looks_like_gary(name):
    return name == "gary" or name.startswith(("gary_device", "gary_qnx", "fake_gary"))


def looks_like_talk(name):
    return name.startswith(("gary_talk", "fake_talk"))


def gary_pid(pid_path, looks_like=looks_like_gary):
    """The running Gary's process id, or None.

    gary.pid can be stale after a power cut, and by then its number may belong
    to some other program. Where the system shows a process's command line,
    check that it really is Gary before any signal goes out.
    """
    try:
        with open(pid_path, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
        if pid <= 1 or pid == os.getpid():
            return None
        os.kill(pid, 0)
    except (OSError, ValueError):
        return None
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            words = [w for w in re.split(rb"[\0\s]+", f.read()) if w][:3]
    except OSError:
        return pid  # no way to look here: trust the file
    if not words:
        return pid
    names = [os.path.basename(w.decode("utf-8", "replace")) for w in words]
    return pid if any(looks_like(n) for n in names) else None


def press_gary(pid_path):
    """Ask Gary for one Sniff Test. Returns False if he is not running."""
    pid = gary_pid(pid_path)
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGUSR1)
    except OSError:
        return False
    return True


def ask_talk(pid_path):
    """Ask gary_talk.py to listen (the button was held). False if it is not running."""
    pid = gary_pid(pid_path, looks_like_talk)
    if pid is None or not hasattr(signal, "SIGUSR2"):
        return False
    try:
        os.kill(pid, signal.SIGUSR2)
    except OSError:
        return False
    return True


def write_mood(journal_path, device, phase, value):
    """Append one private mood check-in to the journal. sync.py uploads it like
    any other line. This is the hook for a knob or any other input (issue #12)."""
    if phase not in ("before", "after"):
        raise ValueError('phase must be "before" or "after"')
    value = int(value)
    if not 1 <= value <= 5:
        raise ValueError("value must be 1 to 5")
    now = datetime.datetime.now(datetime.timezone.utc)
    event = {
        "id": "%s-%d-m%d" % (device, int(now.timestamp() * 1000), os.getpid()),
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": "mood",
        "device": device,
        "phase": phase,
        "value": value,
    }
    line = (json.dumps(event) + "\n").encode("utf-8")
    try:
        with open(journal_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            if f.tell() > 0:
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":
                    line = b"\n" + line  # the last line was cut short: start a new one
    except OSError:
        pass
    fd = os.open(journal_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line)  # one write, so it cannot mix with a line of Gary's
        os.fsync(fd)
    finally:
        os.close(fd)
    return event


# --------------------------------------------------------------------------
# GPIO: whichever library this machine has
# --------------------------------------------------------------------------
class LibPins:
    """rpi_gpio on QNX and RPi.GPIO on Raspberry Pi OS share these calls."""

    def __init__(self, gpio, button, buzzer, active_low, tones, say):
        self.gpio, self.active_low, self.tones = gpio, active_low, tones
        self.button = self.buzzer = self.pwm = None
        try:
            gpio.setmode(gpio.BCM)
        except Exception:
            pass  # older builds number pins the Broadcom way without being asked
        if button is not None:
            try:
                pull = gpio.PUD_UP if active_low else gpio.PUD_DOWN
                gpio.setup(button, gpio.IN, pull)
                self.button = button
            except Exception as exc:
                say("the button on GPIO%d is off: %s" % (button, exc))
        if buzzer is not None:
            try:
                gpio.setup(buzzer, gpio.OUT)
                gpio.output(buzzer, gpio.LOW)
                self.buzzer = buzzer
            except Exception as exc:
                say("the buzzer on GPIO%d is off: %s" % (buzzer, exc))

    has_button = property(lambda self: self.button is not None)
    has_buzzer = property(lambda self: self.buzzer is not None)

    def read_button(self):
        return (self.gpio.input(self.button) == self.gpio.HIGH) != self.active_low

    def sound(self, tone):
        if self.buzzer is None:
            return
        if self.tones:
            try:
                if tone and self.pwm is None:
                    self.pwm = self.gpio.PWM(self.buzzer, tone)
                    self.pwm.start(50)
                elif tone:
                    self.pwm.ChangeFrequency(tone)
                    self.pwm.ChangeDutyCycle(50)
                elif self.pwm is not None:
                    self.pwm.ChangeDutyCycle(0)
                return
            except Exception:
                self.tones = False  # no PWM here after all: plain on and off
        self.gpio.output(self.buzzer, self.gpio.HIGH if tone else self.gpio.LOW)

    def close(self):
        try:
            if self.pwm is not None:
                self.pwm.stop()
            if self.buzzer is not None:
                self.gpio.output(self.buzzer, self.gpio.LOW)  # QNX's cleanup() leaves pins as they are
            self.gpio.cleanup()
        except Exception:
            pass


class ZeroPins:
    """gpiozero, which Raspberry Pi OS ships and which works on the Pi 5."""

    def __init__(self, button, buzzer, active_low, say):
        from gpiozero import DigitalInputDevice, DigitalOutputDevice
        self._in = self._out = None
        if button is not None:
            try:
                self._in = DigitalInputDevice(button, pull_up=active_low)
            except Exception as exc:
                say("the button on GPIO%d is off: %s" % (button, exc))
        if buzzer is not None:
            try:
                self._out = DigitalOutputDevice(buzzer)
            except Exception as exc:
                say("the buzzer on GPIO%d is off: %s" % (buzzer, exc))

    has_button = property(lambda self: self._in is not None)
    has_buzzer = property(lambda self: self._out is not None)

    def read_button(self):
        return bool(self._in.value)  # gpiozero already reports "pressed", whichever way it is wired

    def sound(self, tone):
        if self._out is not None:
            (self._out.on if tone else self._out.off)()

    def close(self):
        for part in (self._in, self._out):
            try:
                if part is not None:
                    part.close()
            except Exception:
                pass


class FakePins:
    """No hardware (--fake, and the tests). Enter is the button."""

    has_button = has_buzzer = True

    def __init__(self, keyboard=True):
        self.pressed = threading.Event()
        self.down_until = 0.0
        if keyboard:
            threading.Thread(target=self._keys, daemon=True).start()

    def _keys(self):
        for _ in sys.stdin:
            self.pressed.set()

    def read_button(self):
        if self.pressed.is_set():
            self.pressed.clear()
            self.down_until = time.monotonic() + 0.1  # held for a tenth of a second
        return time.monotonic() < self.down_until

    def sound(self, tone):
        pass

    def close(self):
        pass


def open_pins(button, buzzer, active_low, tones, say):
    """The first GPIO library that gives at least one working pin, or None."""
    for name in ("rpi_gpio", "RPi.GPIO"):
        try:
            gpio = importlib.import_module(name)
        except Exception:
            continue  # not installed, or not this kind of board
        try:
            pins = LibPins(gpio, button, buzzer, active_low, tones, say)
        except Exception as exc:
            say("%s is here but did not start: %s" % (name, exc))
            continue
        if pins.has_button or pins.has_buzzer:
            say("GPIO through %s" % name)
            return pins
        pins.close()
    try:
        pins = ZeroPins(button, buzzer, active_low, say)
    except Exception:
        return None
    if pins.has_button or pins.has_buzzer:
        say("GPIO through gpiozero")
        return pins
    return None


# --------------------------------------------------------------------------
# The loop
# --------------------------------------------------------------------------
class Io:
    """One step of work at a time, so the tests can drive it."""

    JOURNAL_EVERY = 0.05
    HOLD = 0.8          # seconds: a press held this long also means "talk to Gary"

    def __init__(self, pins, folder, say, debounce=0.03, gap=0.4):
        self.pins, self.say = pins, say
        self.pid_path = os.path.join(folder, "gary.pid")
        self.talk_path = os.path.join(folder, "gary_talk.pid")
        self.held = False
        self.tail = JournalTail(os.path.join(folder, "journal.jsonl"))
        self.quests = QuestBook(folder, os.path.join(folder, "journal.jsonl"))
        self.button = Button(debounce, gap)
        self.beeper = Beeper(self._sound)
        self.button_ok, self.buzzer_ok = pins.has_button, pins.has_buzzer
        self.next_journal = 0.0
        self.presses = 0

    def _sound(self, tone):
        if not self.buzzer_ok:
            return
        try:
            self.pins.sound(tone)
        except Exception as exc:
            self.buzzer_ok = False
            self.say("the buzzer stopped working (%s). Carrying on without it." % exc)

    def step(self, now):
        if self.button_ok:
            try:
                level = self.pins.read_button()
            except Exception as exc:
                self.button_ok = False
                self.say("the button stopped working (%s). Enter in Gary's terminal still sniffs." % exc)
            else:
                if self.button.update(level, now):
                    self.presses += 1
                    if press_gary(self.pid_path):
                        self.say("button: Sniff Test")
                    else:
                        self.say("button: Gary is not running (no live gary.pid)")
                        self.beeper.play(PATTERNS["not_ready"])
                # Held down: talk to Gary, as if you had said "Go Gary".
                if not self.button.state:
                    self.held = False
                elif (not self.held and self.button.last_press is not None
                      and now - self.button.last_press >= self.HOLD):
                    self.held = True
                    self.say("button held: talk" if ask_talk(self.talk_path)
                             else "button held: talking is off (gary_talk.py is not running)")
        if now >= self.next_journal:
            self.next_journal = now + self.JOURNAL_EVERY
            for event in self.tail.poll():
                # Open quests as they were before this sniff: one it finishes was still open.
                steps = pattern_for(event, self.quests.open_labels() if event.get("type") == "discovery" else ())
                self.quests.note(event)
                if steps:
                    self.say("buzzer: %s%s" % (describe(event), "" if self.buzzer_ok else " (no buzzer)"))
                    self.beeper.play(steps)
        self.beeper.tick(now)


def describe(event):
    if event.get("type") == "miss":
        return "nothing he can name"
    if event.get("type") == "mood":
        return "check-in noted"
    what = "quest complete" if event.get("quest_id") else ("new discovery" if event.get("new") else "seen before")
    label = event.get("label")
    return "%s%s%s" % (what, ": " + label if label else "", ", with a friend" if event.get("friend") else "")


def pin(text):
    if str(text).lower() in ("none", "off", "-1", ""):
        return None
    return int(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gary's button and buzzer")
    ap.add_argument("--button-pin", type=pin, default=17, help='GPIO number of the button (default 17), or "none"')
    ap.add_argument("--buzzer-pin", type=pin, default=27, help='GPIO number of the buzzer (default 27), or "none"')
    ap.add_argument("--active-low", action="store_true",
                    help="the button connects the pin to ground when pressed (a Grove button does not)")
    ap.add_argument("--debounce-ms", type=float, default=30, help="the level must hold this long (default 30)")
    ap.add_argument("--gap-ms", type=float, default=400, help="presses closer than this are one (default 400)")
    ap.add_argument("--tones", action="store_true", help="also vary the pitch, where the GPIO library has PWM")
    ap.add_argument("--dir", default=HERE, help="the device folder (gary.pid, journal.jsonl)")
    ap.add_argument("--demo", action="store_true", help="play every pattern once, then exit")
    ap.add_argument("--fake", action="store_true", help="no hardware: Enter is the button, beeps are printed")
    ap.add_argument("--mood", nargs=2, metavar=("PHASE", "VALUE"),
                    help="write one mood check-in to the journal (before or after, 1 to 5), then exit")
    ap.add_argument("--device", default="gary-01", help="name written into a --mood line")
    args = ap.parse_args(argv)

    def say(text):
        print(time.strftime("%H:%M:%S"), text, flush=True)

    if args.mood:
        try:
            event = write_mood(os.path.join(args.dir, "journal.jsonl"), args.device, args.mood[0], args.mood[1])
        except ValueError as exc:
            ap.error(str(exc))
        say("noted in the journal: %s" % json.dumps(event))
        return 0

    if args.fake:
        pins = FakePins()
        say("Fake mode: press Enter for the button. Beeps are printed.")
    else:
        pins = open_pins(args.button_pin, args.buzzer_pin, args.active_low, args.tones, say)
    if pins is None:
        # Fail quietly: Gary himself is a separate program and is not affected.
        say("No GPIO here, so the button and buzzer are off. Gary is not affected: "
            "Enter in his terminal still sniffs.")
        return 0

    io = Io(pins, args.dir, say, args.debounce_ms / 1000.0, args.gap_ms / 1000.0)
    stopping = threading.Event()
    for name in ("SIGINT", "SIGTERM"):
        signal.signal(getattr(signal, name), lambda *_: stopping.set())
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal.SIG_IGN)  # keep running after the terminal closes

    try:
        if args.demo:
            for title, event in DEMO:
                say(title)
                io.beeper.play(pattern_for(event, event.get("_open", ())))
                while io.beeper.busy() and not stopping.is_set():
                    io.beeper.tick(time.monotonic())
                    time.sleep(0.005)
                stopping.wait(1.0)
                if stopping.is_set():
                    break
            return 0

        say("button: %s. buzzer: %s. Watching %s"
            % ("GPIO%s" % args.button_pin if io.button_ok else "off",
               "GPIO%s" % args.buzzer_pin if io.buzzer_ok else "off", io.tail.path))
        try:
            if io.button_ok and not args.fake and pins.read_button():
                say("The button reads as pressed right now. If it is not, check the wiring or try --active-low.")
        except Exception:
            pass  # io.step() reports a button that cannot be read
        io.beeper.play(PATTERNS["tap"])  # one tick: this script is alive
        while not stopping.is_set():
            io.step(time.monotonic())
            time.sleep(0.005)
        return 0
    finally:
        io.beeper.stop()
        pins.close()


if __name__ == "__main__":
    sys.exit(main())
