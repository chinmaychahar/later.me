"""Sends letters over SMTP using settings from config.json."""

import json
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "config.json"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            "config.json not found. Copy config.example.json to config.json "
            "and fill in your SMTP details."
        )
    return json.loads(CONFIG_FILE.read_text())


def send_letter(letter: dict, body: str) -> None:
    cfg = load_config()
    msg = EmailMessage()
    msg["From"] = f"{cfg.get('from_name', 'later.me')} <{cfg['smtp_user']}>"
    msg["To"] = letter["to"]
    msg["Subject"] = f"later.me: {letter['subject']}"

    written = letter["created_at"][:10]
    msg.set_content(
        f"You wrote this to yourself on {written}, "
        f"to be delivered on {letter['deliver_on']}.\n"
        f"{'-' * 40}\n\n"
        f"{body}\n"
    )

    port = int(cfg.get("smtp_port", 465))
    timeout = 30  # never let the unattended daily job hang on a stuck server
    if port == 465:
        with smtplib.SMTP_SSL(cfg["smtp_host"], port, timeout=timeout,
                              context=ssl.create_default_context()) as s:
            s.login(cfg["smtp_user"], cfg["smtp_password"])
            s.send_message(msg)
    else:  # 587 / STARTTLS
        with smtplib.SMTP(cfg["smtp_host"], port, timeout=timeout) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(cfg["smtp_user"], cfg["smtp_password"])
            s.send_message(msg)
