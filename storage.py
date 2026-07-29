"""Letter storage. Bodies are encrypted at rest; metadata stays readable."""

import json
import uuid
from datetime import date, datetime
from pathlib import Path

from cryptography.fernet import Fernet

DATA_DIR = Path(__file__).parent / "data"
LETTERS_DIR = DATA_DIR / "letters"
KEY_FILE = DATA_DIR / "secret.key"


def _fernet() -> Fernet:
    LETTERS_DIR.mkdir(parents=True, exist_ok=True)
    if not KEY_FILE.exists():
        KEY_FILE.write_bytes(Fernet.generate_key())
        KEY_FILE.chmod(0o600)
    return Fernet(KEY_FILE.read_bytes())


def create_letter(to_email: str, subject: str, body: str, deliver_on: str) -> dict:
    letter = {
        "id": uuid.uuid4().hex[:12],
        "to": to_email,
        "subject": subject,
        "deliver_on": deliver_on,  # YYYY-MM-DD
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "sealed",  # sealed -> sent
        "unsealed_early": False,
        "body_encrypted": _fernet().encrypt(body.encode()).decode(),
    }
    _save(letter)
    return letter


def _save(letter: dict) -> None:
    # Write to a temp file then atomically replace, so a crash mid-write can
    # never leave a half-written letter that breaks the app on next read.
    path = LETTERS_DIR / f"{letter['id']}.json"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(letter, indent=2))
    tmp.replace(path)


def update(letter: dict) -> None:
    _save(letter)


def get(letter_id: str) -> dict | None:
    path = LETTERS_DIR / f"{letter_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def delete(letter_id: str) -> bool:
    path = LETTERS_DIR / f"{letter_id}.json"
    if not path.exists():
        return False
    path.unlink()
    return True


def list_all() -> list[dict]:
    LETTERS_DIR.mkdir(parents=True, exist_ok=True)
    letters = []
    for p in sorted(LETTERS_DIR.glob("*.json")):
        try:
            letters.append(json.loads(p.read_text()))
        except (json.JSONDecodeError, OSError):
            continue  # skip a corrupt/unreadable file rather than break every page
    return letters


def decrypt_body(letter: dict) -> str:
    return _fernet().decrypt(letter["body_encrypted"].encode()).decode()


def is_due(letter: dict) -> bool:
    return date.fromisoformat(letter["deliver_on"]) <= date.today()
