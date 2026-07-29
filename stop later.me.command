#!/usr/bin/env bash
# Double-click to stop the later.me server. This only closes the app window's
# server - it does NOT affect delivery. Your letters still arrive on schedule.
cd "$(dirname "$0")"

if pgrep -f "[a]pp.py" > /dev/null; then
  pkill -f "[a]pp.py"
  sleep 1
  if pgrep -f "[a]pp.py" > /dev/null; then
    echo "Tried to stop later.me but it's still running. You can close this window."
  else
    echo "later.me is stopped. (Delivery still runs on schedule - nothing changes there.)"
  fi
else
  echo "later.me wasn't running. Nothing to stop."
fi

echo
echo "You can close this window."
