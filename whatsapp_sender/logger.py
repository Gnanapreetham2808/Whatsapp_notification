"""
Logging utilities: Python logger setup + CSV sent-log management.
"""

import csv
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import LOG_LEVEL, SENT_LOG_CSV

# ── CSV columns ────────────────────────────────────────────────────────────
CSV_FIELDS = ["phone", "name", "status", "timestamp", "error"]
STATUS_SENT = "SENT"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"


def setup_logger(name: str = "whatsapp_sender") -> logging.Logger:
    """Return a logger that writes to stdout with a clean format."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


logger = setup_logger()


# ── Sent-log helpers ───────────────────────────────────────────────────────

def _ensure_log_file() -> None:
    """Create sent_log.csv with headers if it does not exist."""
    if not SENT_LOG_CSV.exists():
        with open(SENT_LOG_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()


def load_sent_phones() -> set[str]:
    """
    Return the set of phone numbers that already have a SENT entry in the log.
    Used on startup to skip contacts that were successfully messaged before.
    """
    _ensure_log_file()
    sent: set[str] = set()
    with open(SENT_LOG_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status") == STATUS_SENT:
                sent.add(row["phone"].strip())
    return sent


def write_log_entry(
    phone: str,
    name: str,
    status: str,
    error: Optional[str] = None,
) -> None:
    """Append one row to sent_log.csv."""
    _ensure_log_file()
    with open(SENT_LOG_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writerow(
            {
                "phone": phone,
                "name": name,
                "status": status,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": error or "",
            }
        )
