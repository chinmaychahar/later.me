"""Delivery check: emails every sealed letter whose date has arrived.

Run manually with `python deliver.py`, or on a schedule via launchd/cron
(see README). Safe to run as often as you like - already-sent letters
are never re-sent.
"""

from datetime import datetime

import mailer
import storage

LOG_FILE = storage.DATA_DIR / "deliver.log"


def _log(line: str) -> None:
    storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().isoformat(timespec="seconds")
    with LOG_FILE.open("a") as f:
        f.write(f"{stamp}  {line}\n")


def deliver_due() -> list[tuple[dict, Exception | None]]:
    results = []
    for letter in storage.list_all():
        if letter["status"] != "sealed" or not storage.is_due(letter):
            continue
        try:
            mailer.send_letter(letter, storage.decrypt_body(letter))
            letter["status"] = "sent"
            letter["sent_at"] = datetime.now().isoformat(timespec="seconds")
            letter.pop("last_error", None)  # clear any prior failure
            storage.update(letter)
            _log(f"SENT {letter['id']} to {letter['to']}")
            results.append((letter, None))
        except Exception as exc:  # leave sealed; retried on next run
            letter["last_error"] = str(exc)  # surfaced in the UI so you notice
            storage.update(letter)
            _log(f"FAILED {letter['id']}: {exc}")
            results.append((letter, exc))
    return results


if __name__ == "__main__":
    delivered = deliver_due()
    if not delivered:
        print("No letters due today.")
    for letter, err in delivered:
        if err is None:
            print(f"Sent {letter['id']} ({letter['subject']!r}) to {letter['to']}")
        else:
            print(f"FAILED {letter['id']} ({letter['subject']!r}): {err}")
