#!/bin/sh
# check_secrets.sh - look for keys and passwords in git before the repo goes public.
#
#   sh scripts/check_secrets.sh
#
# The repo is private while we build. The Devpost page needs its link, and a
# judge has to be able to open it. Before you make it public, run this: it
# searches every commit on every branch, and the files you are about to commit,
# for things that look like a key or a password. It prints where it found
# them, never the whole value.
#
# Exit code 0: nothing found. 1: something found. A key that is in a commit is
# still there after you delete the file: change the key at its source (TinyFish,
# Google, Tiger Data), then decide whether the repo can go public.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 2
command -v git >/dev/null 2>&1 || { echo "git is not installed"; exit 2; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "$ROOT is not a git repository"; exit 2; }

# What a real secret looks like here. Placeholders in the docs (PASSWORD, <key>,
# ..., a local test database with no password) are not matched.
PATTERNS='postgres(ql)?://[A-Za-z0-9_.-]+:[^@/[:space:]]{6,}@|AIza[0-9A-Za-z_-]{30,}|sk-[A-Za-z0-9_-]{24,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(TINYFISH_API_KEY|GEMINI_API_KEY|SCOUT_KEY|GARY_ADMIN_KEY)[[:space:]]*[=:][[:space:]]*["'"'"']?[A-Za-z0-9_/+-]{12,}'
# Lines that are known to be examples, not secrets.
ALLOW='PASSWORD@HOST|:PASSWORD@|<[a-z -]+>|\.\.\.|[=:] *choose-|[=:] *change-me|for-test|secret-[12]|the-real-one|example\.'

found=0
hide() { sed -E 's/(:[^@/[:space:]]{2})[^@/[:space:]]+@/\1****@/; s/((AIza|sk-)[A-Za-z0-9_-]{4})[A-Za-z0-9_-]+/\1****/; s/((KEY)[[:space:]]*[=:][[:space:]]*["'"'"']?[A-Za-z0-9_/+-]{3})[A-Za-z0-9_/+-]+/\1****/'; }

echo "Looking through every commit on every branch..."
hits="$(git log --all -p --no-color --format='commit %h %s' 2>/dev/null \
  | awk '/^commit /{c=$2} /^\+\+\+ /{f=$2} /^\+[^+]/{print c" "f": "substr($0,2)}' \
  | grep -E -- "$PATTERNS" | grep -v -E -- "$ALLOW" | sort -u)"
if [ -n "$hits" ]; then
  found=1
  echo "FOUND in commits (commit, file, line):"
  printf '%s\n' "$hits" | hide | sed 's/^/  /'
fi

echo "Looking through the files in this folder that git would add..."
hits="$(git ls-files -co --exclude-standard -z 2>/dev/null | xargs -0 grep -n -I -E -- "$PATTERNS" 2>/dev/null \
  | grep -v -E -- "$ALLOW" | grep -v '^scripts/check_secrets.sh:')"
if [ -n "$hits" ]; then
  found=1
  echo "FOUND in files:"
  printf '%s\n' "$hits" | hide | sed 's/^/  /'
fi

for file in backend/.env device/gary.env .env; do
  if [ -f "$file" ] && ! git check-ignore -q "$file"; then
    found=1
    echo "FOUND: $file is not ignored by git. It would be committed."
  fi
  if git ls-files --error-unmatch "$file" >/dev/null 2>&1; then
    found=1
    echo "FOUND: $file is tracked by git."
  fi
done

echo
if [ "$found" = 1 ]; then
  echo "Something that looks like a secret is in the repo. Do not make it public yet."
  echo "Change that key at its source first: a key in an old commit stays readable."
  exit 1
fi
echo "Nothing that looks like a key or a password was found."
