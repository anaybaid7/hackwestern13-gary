"""Tests for scripts/check_secrets.sh, on throwaway git repositories.

    python3 scripts/tests/test_check_secrets.py      # or: pytest scripts
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPT = os.path.join(ROOT, "scripts", "check_secrets.sh")

# Made up for these tests, and split so that this file itself never looks like a secret.
GOOGLE_KEY = "AIza" + "SyD3x4mpleOnlyNotARealKey0123456789ab"
DATABASE = "postgres://tsdbadmin:" + "s3cretPassw0rd" + "@abc123.tsdb.cloud.timescale.com:31234/tsdb"
TINYFISH = "TINYFISH_API_KEY=" + "tf_live_9f8e7d6c5b4a3210"
TINYFISH_SK = "sk-" + "tinyfish-" + "Ab3_dE6-gH9jK2mN5pQ8rS1tU4vW7xYz"   # the shape of a real TinyFish key
PLACEHOLDER = "TINYFISH_API_KEY=" + "your-key-here"                       # what scout/README.md tells people to replace
PASSPHRASE = "GARY_PRIVATE_KEY=" + "sunny goats 42"


class Repo:
    def __init__(self):
        self.path = tempfile.mkdtemp(prefix="gary-secrets-")
        os.makedirs(os.path.join(self.path, "scripts"))
        shutil.copy(SCRIPT, os.path.join(self.path, "scripts", "check_secrets.sh"))
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.org")
        self.git("config", "user.name", "Test")
        self.write(".gitignore", ".env\ngary.env\n")
        self.write("README.md", "# A repo\n\nexport TINYFISH_API_KEY=...\nDATABASE_URL=postgres://tsdbadmin:PASSWORD@HOST.tsdb.cloud.timescale.com:PORT/tsdb\n"
                                "SCOUT_KEY=choose-a-long-random-string\n"
                                "Put your key in scout/.env:\n\n" + PLACEHOLDER + "\n")
        self.commit("start")

    def git(self, *args):
        return subprocess.run(["git"] + list(args), cwd=self.path, capture_output=True, text=True, check=True)

    def write(self, name, text):
        path = os.path.join(self.path, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def check(self):
        return subprocess.run(["sh", os.path.join(self.path, "scripts", "check_secrets.sh")], capture_output=True, text=True)

    def close(self):
        shutil.rmtree(self.path)


def test_placeholders_in_the_docs_are_not_secrets():
    repo = Repo()
    try:
        out = repo.check()
        assert out.returncode == 0, out.stdout + out.stderr
        assert "Nothing that looks like a key or a password was found." in out.stdout
    finally:
        repo.close()


def test_a_key_in_an_old_commit_is_found_even_after_the_file_is_deleted():
    repo = Repo()
    try:
        repo.write("notes.txt", "GEMINI key: %s\n" % GOOGLE_KEY)
        repo.commit("notes")
        os.remove(os.path.join(repo.path, "notes.txt"))
        repo.commit("remove the notes")
        out = repo.check()
        assert out.returncode == 1, out.stdout
        assert "FOUND in commits" in out.stdout and "notes.txt" in out.stdout
        assert GOOGLE_KEY not in out.stdout, "the value itself is never printed"
        assert "Do not make it public yet" in out.stdout
    finally:
        repo.close()


def test_a_database_password_and_an_api_key_in_the_working_files_are_found():
    repo = Repo()
    try:
        repo.write("backend/settings.txt", "DATABASE_URL=%s\n" % DATABASE)
        repo.write("scout/run.sh", "export %s\npython3 scout.py\n" % TINYFISH)
        repo.write("notes/server.txt", "%s\n" % PASSPHRASE)
        repo.write("notes/chat.md", "here is the key: %s\n" % TINYFISH_SK)       # a bare key, no name before it
        repo.write("scout/setup.md", "TINYFISH_API_KEY=%s\n" % TINYFISH_SK)      # a real key where the placeholder goes
        out = repo.check()
        assert out.returncode == 1, out.stdout
        assert "FOUND in files" in out.stdout
        for name in ("backend/settings.txt", "scout/run.sh", "notes/server.txt", "notes/chat.md", "scout/setup.md"):
            assert name in out.stdout, name
        assert "s3cretPassw0rd" not in out.stdout and "tf_live_9f8e7d6c5b4a3210" not in out.stdout
        assert TINYFISH_SK not in out.stdout and TINYFISH_SK[12:] not in out.stdout
        assert "sunny" not in out.stdout and "goats" not in out.stdout, "no word of a passphrase is printed"
    finally:
        repo.close()


def test_a_settings_file_that_git_would_commit_is_found():
    repo = Repo()
    try:
        # ignored: fine, even with a real-looking value in it
        repo.write(".env", "DATABASE_URL=%s\n" % DATABASE)
        assert repo.check().returncode == 0
        # the same file in backend/ is covered by the same line of .gitignore
        repo.write("backend/.env", "GARY_NAP_SECONDS=60\n")
        assert repo.check().returncode == 0
        # but if .gitignore stops covering it, git would add it: that is found
        repo.write(".gitignore", "/.env\n")
        out = repo.check()
        assert out.returncode == 1 and "backend/.env is not ignored by git" in out.stdout, out.stdout
        # the scout keeps its key in scout/.env: the same holds for that file
        repo.write("scout/.env", "TINYFISH_API_KEY=%s\n" % TINYFISH_SK)
        out = repo.check()
        assert "scout/.env is not ignored by git" in out.stdout, out.stdout
        assert TINYFISH_SK not in out.stdout
    finally:
        repo.close()


def test_this_repo_has_no_secret_in_any_commit():
    out = subprocess.run(["sh", SCRIPT], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


if __name__ == "__main__":
    failed = 0
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn()
            print("ok   " + name)
        except Exception:
            failed += 1
            import traceback
            print("FAIL " + name)
            traceback.print_exc()
    print("%d secrets check tests, %d failed" % (len(tests), failed))
    sys.exit(1 if failed else 0)
