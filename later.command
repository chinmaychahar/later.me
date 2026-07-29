#!/usr/bin/env bash
# Double-click to open later.me. Starts the server if it isn't already running,
# then opens it in your browser. Safe to run repeatedly - it won't start twice.
cd "$(dirname "$0")"

URL="http://127.0.0.1:5170"

if [ ! -x .venv/bin/python ]; then
  echo "later.me isn't set up yet. Run ./setup.sh first."
  read -r -p "Press return to close."
  exit 1
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
