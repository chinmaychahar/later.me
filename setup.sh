#!/usr/bin/env bash
# later.me setup - run once: ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"

say() { printf "\n\033[1m%s\033[0m\n" "$1"; }

say "✉︎  later.me setup"

# 1. python + venv
# Find a Python 3.10+ (system python3 may be too old, e.g. macOS ships 3.9).
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
if ! PY="$(find_python)"; then
  echo "Python 3.10+ not found. Install it first (https://python.org)." >&2
  exit 1
fi
# Rebuild if the venv is missing or its Python was removed (dangling symlink).
if [ ! -x .venv/bin/python ]; then
  say "Creating virtual environment ($("$PY" --version))..."
  rm -rf .venv
  "$PY" -m venv .venv
fi
say "Installing dependencies..."
.venv/bin/pip install --quiet --disable-pip-version-check --upgrade -r requirements.txt

# 2. email config
if [ -f config.json ]; then
  say "config.json already exists - keeping it."
else
  say "Email setup"
  echo "later.me delivers letters through your own email account (SMTP)."
  echo "For Gmail: create an app password at https://myaccount.google.com/apppasswords"
  echo "(requires 2-step verification). Other providers: use their SMTP settings."
  echo
  read -rp "Your email address: " EMAIL
  read -rsp "App password (input hidden): " APP_PASS; echo
  read -rp "SMTP host [smtp.gmail.com]: " HOST
  read -rp "SMTP port [465]: " PORT
  HOST=${HOST:-smtp.gmail.com}
  PORT=${PORT:-465}

  EMAIL="$EMAIL" APP_PASS="$APP_PASS" HOST="$HOST" PORT="$PORT" \
  .venv/bin/python - <<'PY'
import json, os
cfg = {
    "smtp_host": os.environ["HOST"],
    "smtp_port": int(os.environ["PORT"]),
    "smtp_user": os.environ["EMAIL"],
    "smtp_password": os.environ["APP_PASS"],
    "from_name": "later.me",
    "default_to": os.environ["EMAIL"],
}
with open("config.json", "w") as f:
    json.dump(cfg, f, indent=2)
os.chmod("config.json", 0o600)
print("Wrote config.json (kept out of git, readable only by you).")
PY

  say "Testing SMTP login..."
  if .venv/bin/python - <<'PY'
import json, smtplib, ssl, sys
cfg = json.load(open("config.json"))
port = int(cfg["smtp_port"])
try:
    if port == 465:
        s = smtplib.SMTP_SSL(cfg["smtp_host"], port, context=ssl.create_default_context())
    else:
        s = smtplib.SMTP(cfg["smtp_host"], port)
        s.starttls(context=ssl.create_default_context())
    s.login(cfg["smtp_user"], cfg["smtp_password"])
    s.quit()
except Exception as e:
    print(f"Login failed: {e}", file=sys.stderr)
    sys.exit(1)
PY
  then
    echo "Email login works."
  else
    echo "SMTP login failed - check the app password. You can edit config.json and re-run ./setup.sh"
    exit 1
  fi
fi

# 3. daily delivery schedule (macOS launchd / linux cron)
PYBIN="$PWD/.venv/bin/python"
if [ "$(uname)" = "Darwin" ]; then
  PLIST="$HOME/Library/LaunchAgents/com.laterme.deliver.plist"
  if [ -f "$PLIST" ]; then
    say "Daily delivery already scheduled - keeping it."
  else
    read -rp "Schedule daily delivery at 9:00 via launchd? [Y/n] " YN
    if [ "${YN:-Y}" != "n" ] && [ "${YN:-Y}" != "N" ]; then
      cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.laterme.deliver</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYBIN</string>
    <string>$PWD/deliver.py</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
</dict>
</plist>
EOF
      launchctl unload "$PLIST" 2>/dev/null || true
      launchctl load "$PLIST"
      echo "Scheduled. Letters will be checked every morning at 9:00."
    else
      echo "Skipped. Run '$PYBIN deliver.py' manually, or re-run ./setup.sh later."
    fi
  fi
else
  say "To schedule daily delivery, add this line to your crontab (crontab -e):"
  echo "0 9 * * * $PYBIN $PWD/deliver.py"
fi

say "Done! Start later.me with:  .venv/bin/python app.py"
echo "Then open http://127.0.0.1:5170 and write your first letter."
