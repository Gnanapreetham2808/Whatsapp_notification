"""
WhatsApp Bulk Sender – main entry point.

Run:
    python app.py
"""

import random
import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd

import config
from logger import (
    STATUS_FAILED,
    STATUS_SENT,
    STATUS_SKIPPED,
    load_sent_phones,
    logger,
    write_log_entry,
)
from sender import WhatsAppSender


# ── Contact loading ────────────────────────────────────────────────────────

def load_contacts() -> list[dict]:
    """
    Read contacts.csv and return a list of {'name': str, 'phone': str} dicts.
    Validates that required columns exist and normalises phone numbers.
    """
    if not config.CONTACTS_CSV.exists():
        logger.error(f"contacts.csv not found at {config.CONTACTS_CSV}")
        sys.exit(1)

    try:
        df = pd.read_csv(config.CONTACTS_CSV, dtype=str)
    except Exception as exc:
        logger.error(f"Failed to read contacts.csv: {exc}")
        sys.exit(1)

    required = {"name", "phone"}
    missing = required - set(df.columns.str.lower())
    if missing:
        logger.error(f"contacts.csv is missing columns: {missing}")
        sys.exit(1)

    df.columns = df.columns.str.lower().str.strip()
    df["phone"] = df["phone"].str.strip().str.replace(r"\D", "", regex=True)
    df["name"] = df["name"].str.strip()
    df = df.dropna(subset=["phone", "name"])
    df = df[df["phone"].str.len() >= 7]          # rudimentary length check

    contacts = df[["name", "phone"]].to_dict("records")
    logger.info(f"Loaded {len(contacts)} contacts from {config.CONTACTS_CSV}")
    return contacts


# ── Template loading ───────────────────────────────────────────────────────

def load_template() -> str:
    """Read the message template file and return its contents."""
    if not config.MESSAGE_TEMPLATE.exists():
        logger.error(f"Template not found at {config.MESSAGE_TEMPLATE}")
        sys.exit(1)

    text = config.MESSAGE_TEMPLATE.read_text(encoding="utf-8").strip()
    if not text:
        logger.error("Message template is empty.")
        sys.exit(1)

    logger.info(f"Template loaded from {config.MESSAGE_TEMPLATE}")
    return text


def render_message(template: str, contact: dict) -> str:
    """Replace every {column} placeholder with the corresponding value from the contact row."""
    message = template
    for key, value in contact.items():
        message = message.replace(f"{{{key}}}", str(value))
    return message


# ── Batch helpers ──────────────────────────────────────────────────────────

def _batch_pause() -> None:
    """Sleep between batches and print a countdown every minute."""
    total_seconds = config.BATCH_PAUSE_MINUTES * 60
    print(f"\nBatch complete.  Sleeping {config.BATCH_PAUSE_MINUTES} minutes …\n")
    end = time.time() + total_seconds
    while time.time() < end:
        remaining = int(end - time.time())
        mins, secs = divmod(remaining, 60)
        print(f"\r  Resuming in {mins:02d}:{secs:02d} …", end="", flush=True)
        time.sleep(min(10, remaining))
    print("\r  Resuming now.                     ")


def _inter_message_delay(index: int, total: int) -> None:
    """Print delay countdown and sleep between messages."""
    delay = random.randint(config.MIN_DELAY, config.MAX_DELAY)
    print(f"  Waiting {delay} seconds …")
    if index < total:                            # no delay after the last contact
        time.sleep(delay)


# ── Send loop ──────────────────────────────────────────────────────────────

def run_send_loop(wa: WhatsAppSender, contacts: list[dict], template: str) -> None:
    """
    Iterate over contacts, skip already-sent ones, and send messages in
    batches.  Handles per-message retries and browser crash recovery.
    """
    sent_phones = load_sent_phones()
    total = len(contacts)
    processed = 0                                # counts contacts handled this run
    in_batch = 0                                 # counts sends in the current batch

    for idx, contact in enumerate(contacts, start=1):
        phone: str = contact["phone"]
        name: str = contact["name"]

        # ── Skip check ─────────────────────────────────────────────────────
        if phone in sent_phones:
            print(f"[{idx}/{total}] Skipping {name} ({phone}) – already SENT")
            write_log_entry(phone, name, STATUS_SKIPPED)
            continue

        print(f"\n[{idx}/{total}] Sending to {name} ({phone})")

        # ── Browser crash recovery ─────────────────────────────────────────
        if not wa.is_page_alive():
            logger.warning("Browser is unresponsive – restarting …")
            wa.restart()

        # ── Send with retries ──────────────────────────────────────────────
        sent = False
        last_error: Optional[str] = None

        for attempt in range(1, config.MAX_RETRIES + 2):   # +2: original + retries
            try:
                message = render_message(template, contact)
                wa.send_message(phone, message)
                print("  Message sent.")
                write_log_entry(phone, name, STATUS_SENT)
                sent_phones.add(phone)
                sent = True
                break
            except Exception as exc:
                last_error = str(exc)
                logger.warning(f"  Attempt {attempt} failed: {exc}")
                if attempt <= config.MAX_RETRIES:
                    logger.info(f"  Retrying in {config.RETRY_DELAY}s …")
                    time.sleep(config.RETRY_DELAY)
                    # Re-check page health before retry
                    if not wa.is_page_alive():
                        wa.restart()

        if not sent:
            logger.error(f"  Giving up on {name} ({phone}): {last_error}")
            write_log_entry(phone, name, STATUS_FAILED, error=last_error)

        processed += 1
        in_batch += 1

        # ── Batch boundary ─────────────────────────────────────────────────
        if in_batch == config.BATCH_SIZE and idx < total:
            print(f"\n[{idx}/{total}] Batch of {config.BATCH_SIZE} complete.")
            _batch_pause()
            in_batch = 0
            continue

        # ── Inter-message delay (not after the very last contact) ──────────
        if idx < total:
            _inter_message_delay(idx, total)

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print(f"Done.  Processed {processed} contact(s) this run.")
    print(f"Results written to {config.SENT_LOG_CSV}")
    print("=" * 50)


# ── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    contacts = load_contacts()
    template = load_template()

    # Cap at 150 per the specification
    if len(contacts) > 150:
        logger.warning("Contact list exceeds 150 – processing first 150 only.")
        contacts = contacts[:150]

    wa = WhatsAppSender()
    try:
        wa.start()
        run_send_loop(wa, contacts, template)
    except KeyboardInterrupt:
        print("\nInterrupted by user.  Progress has been saved to sent_log.csv.")
    except Exception as exc:
        logger.error(f"Fatal error: {exc}", exc_info=True)
    finally:
        wa.stop()


if __name__ == "__main__":
    main()
