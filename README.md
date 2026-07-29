# later.me ✉︎

Write letters to your future self. A tiny, self-hosted FutureMe.

- **Sealed means sealed** - letters are encrypted on disk the moment you seal
  them. Peeking early costs a 24-hour cooling-off period and a permanent
  "peeked" mark.
- **Yours, entirely** - no accounts, no cloud, no company. Letters live on
  your machine and are delivered through your own email.
- **Set and forget** - a daily job emails each letter when its date arrives.
  One morning years from now, past you says hello.

## Setup

```bash
git clone https://github.com/chinmaychahar/later.me.git
cd later.me
./setup.sh
```

The script installs dependencies, asks for your email + app password, tests
the login, and offers to schedule daily delivery. That's it.

> **Gmail users:** create an app password at
> <https://myaccount.google.com/apppasswords> (requires 2-step verification).
> Other providers work too - just enter their SMTP host/port when asked.

Then open the app: **double-click `later.command`** (drop it in your Dock to
keep it handy). It starts the app and opens your browser; if it's already
running, it just opens the tab. Prefer the terminal? Run `.venv/bin/python app.py`.

Write a letter at <http://127.0.0.1:5170>, pick a future date, seal it.

## How delivery works

`deliver.py` checks for sealed letters whose date has arrived, emails them
via SMTP, and never re-sends. `setup.sh` schedules it daily at 9:00
(launchd on macOS; on Linux it prints the cron line to add). You can also
run it manually or click "check & deliver due letters now" in the UI.

**Is something always running on my machine?** No. There's no background
app - just a note in your system's built-in scheduler (the same one that
handles things like backups) saying "run this check once a day at 9:00".
The check takes about a second, then exits. If your machine is asleep at
9:00, it runs on wake; if it's off all day, the letter simply arrives the
next day the machine is on. Nothing is ever lost.

To remove the schedule: on macOS,
`launchctl unload ~/Library/LaunchAgents/com.laterme.deliver.plist` and
delete that file; on Linux, remove the cron line. You can then deliver
manually from the UI whenever you like.

## Manual setup

If you'd rather not use the script:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config.example.json config.json   # fill in your SMTP details
```

Schedule `deliver.py` with cron:

```
0 9 * * * /PATH/TO/later.me/.venv/bin/python /PATH/TO/later.me/deliver.py
```

## What never leaves your machine

`data/` (your letters + encryption key) and `config.json` (your email
credentials) are gitignored - only code is published. The encryption key is
`data/secret.key`; back it up if your letters matter to you, since letters
are only readable with it. The "back them up" link on the home page saves a
zip of everything for you.
