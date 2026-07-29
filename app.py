"""later.me - write letters to your future self. Run: python app.py"""

import io
import json
import os
import zipfile
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

from flask import Flask, abort, flash, redirect, render_template, request, send_file, url_for

import deliver
import storage
from mailer import CONFIG_FILE

app = Flask(__name__)
app.secret_key = "laterme-local-only"  # only used for flash messages on localhost

OVERRIDE_PHRASE = "i really want to"
PEEK_COOLDOWN = timedelta(hours=24)

# This app is single-user and local. It holds private letters and hands out the
# encryption key via /backup, so it must never answer a request that didn't come
# from you on this machine. Two guards below enforce that with no login needed.
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _hostname(value: str) -> str:
    """Bare hostname from a Host header or an Origin/Referer URL (port stripped)."""
    prefix = "" if "://" in value else "//"
    return (urlsplit(prefix + value).hostname or "").lower()


@app.before_request
def _local_only():
    # 1. Block DNS-rebinding: the browser's Host must be loopback. A malicious
    #    site pointing its domain at 127.0.0.1 sends its own name here, so this
    #    rejects it - and stops that trick from reading /backup as same-origin.
    if _hostname(request.host) not in LOCAL_HOSTS:
        abort(403)
    # 2. Block CSRF: a state-changing request must originate from this app. A
    #    cross-site POST from another page carries that page's Origin/Referer.
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        source = request.headers.get("Origin") or request.headers.get("Referer")
        if source and _hostname(source) not in LOCAL_HOSTS:
            abort(403)

WRITING_PROMPTS = [
    "What are you hoping is true by the time you read this?",
    "What's weighing on you today that you'll want to remember?",
    "What are you grateful for right now?",
    "What advice would past-you give the person reading this?",
    "What are you working toward? Did it happen?",
    "Describe an ordinary moment from today you don't want to forget.",
]


@app.template_filter("until")
def until(deliver_on: str) -> str:
    """'2027-01-01' -> 'in 2 years, 4 months' - a gentle countdown."""
    days = (date.fromisoformat(deliver_on) - date.today()).days
    if days <= 0:
        return "any moment now"
    if days == 1:
        return "tomorrow"
    if days < 30:
        return f"in {days} days"
    years, rest = divmod(days, 365)
    months = rest // 30
    parts = []
    if years:
        parts.append(f"{years} year" + ("s" if years > 1 else ""))
    if months:
        parts.append(f"{months} month" + ("s" if months > 1 else ""))
    return "in " + ", ".join(parts or [f"{days} days"])


@app.route("/")
def index():
    letters = sorted(storage.list_all(), key=lambda l: l["deliver_on"])
    sealed = [l for l in letters if l["status"] == "sealed"]
    sent = [l for l in letters if l["status"] == "sent"]
    return render_template("index.html", sealed=sealed, sent=sent, today=date.today().isoformat())


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/write", methods=["GET", "POST"])
def write():
    if request.method == "POST":
        to_email = request.form["to"].strip()
        subject = request.form["subject"].strip() or "A letter from your past self"
        body = request.form["body"].strip()
        deliver_on = request.form["deliver_on"]
        if not to_email or not body:
            flash("Email and letter body are required.")
        elif deliver_on <= date.today().isoformat():
            flash("Pick a date in the future - that's the whole point!")
        else:
            letter = storage.create_letter(to_email, subject, body, deliver_on)
            flash(f"Sealed. Letter {letter['id']} will be delivered on {deliver_on}.")
            return redirect(url_for("index"))

    default_to = ""
    if CONFIG_FILE.exists():
        default_to = json.loads(CONFIG_FILE.read_text()).get("default_to", "")
    suggestions = {
        "6 months": (date.today() + timedelta(days=182)).isoformat(),
        "1 year": (date.today() + timedelta(days=365)).isoformat(),
        "3 years": (date.today() + timedelta(days=3 * 365)).isoformat(),
    }
    return render_template("write.html", default_to=default_to,
                           min_date=(date.today() + timedelta(days=1)).isoformat(),
                           suggestions=suggestions, prompts=WRITING_PROMPTS)


@app.route("/letter/<letter_id>", methods=["GET", "POST"])
def view_letter(letter_id):
    letter = storage.get(letter_id)
    if letter is None:
        flash("No such letter.")
        return redirect(url_for("index"))

    readable = letter["status"] == "sent" or storage.is_due(letter)
    body = None
    peek_state, unseal_at = None, None
    if not readable and letter.get("peek_requested_at"):
        unseal_at = datetime.fromisoformat(letter["peek_requested_at"]) + PEEK_COOLDOWN
        peek_state = "cooling" if datetime.now() < unseal_at else "ready"

    if readable:
        body = storage.decrypt_body(letter)
    elif request.method == "POST":
        if peek_state != "ready":
            flash("No shortcuts. The cooling-off period stands.")
        else:
            phrase = request.form.get("override_phrase", "").strip().lower()
            if phrase == OVERRIDE_PHRASE:
                body = storage.decrypt_body(letter)
                letter["unsealed_early"] = True
                storage.update(letter)
                flash("Unsealed early. Future-you saw nothing…")
            else:
                flash(f'Type exactly "{OVERRIDE_PHRASE}" if you really mean it.')

    return render_template("letter.html", letter=letter, body=body,
                           peek_state=peek_state, unseal_at=unseal_at,
                           override_phrase=OVERRIDE_PHRASE)


@app.route("/letter/<letter_id>/peek", methods=["POST"])
def peek(letter_id):
    letter = storage.get(letter_id)
    if letter is None:
        flash("No such letter.")
        return redirect(url_for("index"))
    action = request.form.get("action")
    if action == "request" and not letter.get("peek_requested_at"):
        letter["peek_requested_at"] = datetime.now().isoformat(timespec="seconds")
        storage.update(letter)
        opens = datetime.fromisoformat(letter["peek_requested_at"]) + PEEK_COOLDOWN
        flash(f"Cooling-off started. If you still want to peek after "
              f"{opens.strftime('%d %b %H:%M')}, come back then.")
    elif action == "cancel" and letter.get("peek_requested_at"):
        letter.pop("peek_requested_at")
        storage.update(letter)
        flash("Seal restored. Future you is proud of you. 🤍")
    return redirect(url_for("view_letter", letter_id=letter_id))


@app.route("/letter/<letter_id>/delete", methods=["POST"])
def delete_letter(letter_id):
    letter = storage.get(letter_id)
    if letter is None:
        flash("No such letter.")
    elif storage.delete(letter_id):
        flash(f"Deleted {letter['subject']!r}. It's gone for good.")
    return redirect(url_for("index"))


@app.route("/deliver-now", methods=["POST"])
def deliver_now():
    try:
        results = deliver.deliver_due()
    except FileNotFoundError as exc:
        flash(str(exc))
        return redirect(url_for("index"))
    if not results:
        flash("No letters due today.")
    for letter, err in results:
        if err is None:
            flash(f"Sent {letter['subject']!r} to {letter['to']}.")
        else:
            flash(f"Failed to send {letter['subject']!r}: {err}")
    return redirect(url_for("index"))


@app.route("/backup")
def backup():
    """Zip up data/ (letters + key) so nothing is ever lost to a dead disk."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(storage.DATA_DIR.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(storage.DATA_DIR.parent))
    buf.seek(0)
    stamp = date.today().isoformat()
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"laterme-backup-{stamp}.zip")


if __name__ == "__main__":
    # Bind to loopback only, and keep the debugger off unless explicitly asked
    # for (LATERME_DEBUG=1) - the Werkzeug debugger allows code execution.
    app.run(host="127.0.0.1", port=5170, debug=bool(os.environ.get("LATERME_DEBUG")))
