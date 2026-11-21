#!/usr/bin/env python3
"""e2e.py - the whole loop, with no hardware.

Runs the whole chain on this machine and checks the result:

    scout (saved reply) --> backend <-- sync.py <-- device (laptop version, test photos)

    pip install -r backend/requirements.txt -r device/requirements.txt
    python3 scripts/e2e.py

It starts its own backend on a free port and cleans up after itself. Nothing
it does touches your journal, your quests or a running backend.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def call(api, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(api + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as reply:
        return json.loads(reply.read().decode("utf-8"))


def run(cmd, cwd=ROOT):
    out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit("FAILED: %s\n%s\n%s" % (" ".join(cmd), out.stdout[-2000:], out.stderr[-2000:]))
    return out.stdout


def check(what, ok, detail=""):
    print("  %s  %s%s" % ("ok  " if ok else "FAIL", what, ("  (%s)" % detail) if detail else ""))
    if not ok:
        raise SystemExit("\nEnd-to-end check FAILED at: " + what)


def main():
    port = free_port()
    api = "http://127.0.0.1:%d" % port
    work = tempfile.mkdtemp(prefix="gary-e2e-")
    journal, quests = os.path.join(work, "journal.jsonl"), os.path.join(work, "quests.tsv")
    device = os.path.join(ROOT, "device")
    # A known, clean backend that keeps its data in memory. It must never be
    # the team's real one: GARY_NO_ENV_FILE keeps it from reading backend/.env,
    # where the real database's address lives.
    env = dict(os.environ)
    for key in ("SCOUT_KEY", "GARY_ADMIN_KEY", "GARY_SEED", "GARY_NAP_SECONDS", "GARY_TZ"):
        env.pop(key, None)
    env["GARY_NO_ENV_FILE"] = "1"
    env["DATABASE_URL"] = ""
    backend = subprocess.Popen([PY, "-m", "uvicorn", "app:app", "--port", str(port), "--log-level", "warning"],
                               cwd=os.path.join(ROOT, "backend"), env=env)
    try:
        print("1. Backend")
        for _ in range(60):
            try:
                health = call(api, "/api/health")
                break
            except OSError:
                time.sleep(0.25)
        else:
            raise SystemExit("the backend did not start")
        check("it is a fresh backend that keeps its data in memory (never the team's real one)",
              health.get("store") == "memory" and health.get("events") == 0, str(health))
        check("starts with the seed quests", health["quests"] == 3)
        check("Gary starts as a napping kid", call(api, "/api/state")["gary"]["napping"] is True)

        print("2. Scout (from the saved reply; a live run needs TINYFISH_API_KEY)")
        out = run([PY, os.path.join("scout", "scout.py"), "--from-file",
                   os.path.join("scout", "sample_result.json"), "--api", api])
        check("the backend accepts the scout's quests", "accepted 3 quests" in out, out.strip().splitlines()[-1])
        call(api, "/api/quests", {"id": "q-e2e-dog", "title": "Find a dog at Gibbons Park", "place": "Gibbons Park",
                                  "time": "short", "target": "dog", "xp": 20})

        chosen = call(api, "/api/quest/choose", {"time": "short"})
        check("short or long picks the active quest: today's scout quest first",
              chosen["quest"] is not None and chosen["quest"]["source"] == "tinyfish"
              and chosen["state"]["quest"]["id"] == chosen["quest"]["id"])

        print("3. Sync brings the quests to the device")
        run([PY, "sync.py", "--dir", work, "--api", api, "--once"], cwd=device)
        with open(quests, encoding="utf-8") as f:
            text = f.read()
        check("quests.tsv holds seed and scout quests", "q-demo-bottle" in text and "q-e2e-dog\tdog" in text)
        first = [line for line in text.splitlines() if not line.startswith("#")][0]
        check("the active quest is the first line the device reads", first.startswith(chosen["quest"]["id"] + "\t"))

        print("4. Device: two Sniff Tests on test photos (the laptop version of Gary)")
        base = [PY, "gary_device.py", "--mute", "--log", journal, "--quests", quests, "--image"]
        first = run(base + [os.path.join("test", "pets.jpg")], cwd=device)
        check("a dog completes the dog quest", "SNIFF: dog" in first and "Quest complete: Find a dog at Gibbons Park" in first)
        second = run(base + [os.path.join("test", "kite_and_cold.jpg")], cwd=device)
        check("a kite with people in frame is a Herd Mode find", "SNIFF: kite" in second and "Herd Mode" in second)
        with open(journal, encoding="utf-8") as f:
            lines = [json.loads(line) for line in f]
        check("the journal has two events and no XP in it", len(lines) == 2 and all("xp" not in e for e in lines))

        # A private mood check-in written on the device (the hook a knob would use).
        run([PY, "gary_io.py", "--dir", work, "--mood", "before", "3"], cwd=device)

        print("5. Sync uploads the journal")
        out = run([PY, "sync.py", "--dir", work, "--api", api, "--once"], cwd=device)
        check("two sniffs and one mood check-in uploaded", "uploaded 3 events" in out)
        state = call(api, "/api/state")
        labels = [entry["label"] for entry in state["journal"]]
        check("the backend's journal shows both finds", labels == ["kite", "dog"], str(labels))
        check("XP rose: quest 20 + outdoor find with a friend 20", state["gary"]["xp"] == 40, "xp %d" % state["gary"]["xp"])
        cleared = [tile["place"] for tile in state["map"] if tile["cleared"]]
        check("the map tile for Gibbons Park cleared", cleared == ["Gibbons Park"], str(cleared))
        check("the field guide lists both", state["guide"]["found"] == ["dog", "kite"])
        check("the herd counted the shared find", state["herd"]["shared"] == 1 and "first-herd" in state["herd"]["badges"])
        check("Gary woke up", state["gary"]["napping"] is False)
        wellness = call(api, "/api/wellness")
        check("the mood check-in is private: in wellness, never in the state",
              [(c["value"], c["source"]) for c in wellness["checkins"]] == [(3, "device")]
              and "mood" not in json.dumps(state).lower())
        check("wellness counts the outdoor finds", wellness["outdoor_minutes"] >= 10 and wellness["shared"] == 1)
        tile = [t for t in state["map"] if t["place"] == "Gibbons Park"][0]
        check("the tile remembers what was found there", [f["label"] for f in tile["finds"]] == ["dog"])

        print("6. Nothing is counted twice")
        os.remove(os.path.join(work, "sync.state"))  # as if the device forgot how far it got
        run([PY, "sync.py", "--dir", work, "--api", api, "--once"], cwd=device)
        check("re-sending the whole journal changes nothing", call(api, "/api/state")["gary"]["xp"] == 40)

        print("7. Web page")
        if os.path.isdir(os.path.join(ROOT, "web", "dist")):
            with urllib.request.urlopen(api + "/", timeout=10) as reply:
                page = reply.read().decode("utf-8")
            check("the backend serves the built page", '<div id="root">' in page)
        else:
            print("  skip  web/dist is not built (cd web && npm install && npm run build)")
        print("\nEnd-to-end check PASSED. The whole loop works on this machine.")
    finally:
        backend.terminate()
        try:
            backend.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend.kill()
        for name in os.listdir(work):
            os.remove(os.path.join(work, name))
        os.rmdir(work)
        for name in ("latency.csv", "gary.pid"):
            try:
                os.remove(os.path.join(device, name))
            except OSError:
                pass


if __name__ == "__main__":
    main()
