#!/usr/bin/env bash
# Double-click to open later.me. Starts the server if it isn't already running,
# then opens it in your browser. Safe to run repeatedly - it won't start twice.
cd "$(dirname "$0")"

URL="http://127.0.0.1:5170"

# Find a Python 3.10+ on this machine (prints its path, or nothing).
find_python() {
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 \
       && "$c" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)' 2>/dev/null; then
      command -v "$c"
      return 0
    fi
  done
  return 1
}

# The venv only holds a symlink to the Python it was built from. A Homebrew
# upgrade can remove that Python and leave the symlink dangling. Rebuild the
# venv when its python is gone instead of giving up.
if [ ! -x .venv/bin/python ]; then
  if [ ! -d .venv ]; then
    echo "later.me isn't set up yet. Run ./setup.sh first."
    read -r -p "Press return to close."
    exit 1
  fi
  PY="$(find_python)" || {
    echo "later.me needs Python 3.10+. Install it from https://python.org, then run ./setup.sh"
    read -r -p "Press return to close."
    exit 1
  }
  echo "Rebuilding later.me's environment (the Python it used was upgraded)..."
  rm -rf .venv
  "$PY" -m venv .venv
  if ! .venv/bin/pip install --quiet --disable-pip-version-check --upgrade -r requirements.txt; then
    echo "Rebuild failed. Run ./setup.sh and see the output."
    read -r -p "Press return to close."
    exit 1
  fi
fi

# Already running? Just open the browser.
if curl -s -o /dev/null "$URL/"; then
  open "$URL"
  exit 0
fi

# Start the server in the background, detached from this window.
nohup .venv/bin/python app.py > /tmp/laterme.log 2>&1 &

# Wait for it to answer, then open the browser.
for _ in $(seq 1 20); do
  if curl -s -o /dev/null "$URL/"; then
    open "$URL"
    exit 0
  fi
  sleep 0.25
done

echo "later.me didn't start. See /tmp/laterme.log for details."
read -r -p "Press return to close."
exit 1
