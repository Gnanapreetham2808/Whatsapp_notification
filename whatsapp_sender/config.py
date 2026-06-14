"""
Central configuration for WhatsApp Bulk Sender.
Edit these values before running the application.
"""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).parent
CONTACTS_CSV: Path = BASE_DIR / "contacts.csv"
SENT_LOG_CSV: Path = BASE_DIR / "sent_log.csv"
MESSAGE_TEMPLATE: Path = BASE_DIR / "templates" / "message.txt"
SESSION_DIR: Path = BASE_DIR / ".session"        # persisted browser profile

# ── Sending behaviour ──────────────────────────────────────────────────────
BATCH_SIZE: int = 30                             # contacts per batch
MIN_DELAY: int = 5                               # seconds between messages (min)
MAX_DELAY: int = 15                              # seconds between messages (max)
BATCH_PAUSE_MINUTES: int = 20                    # pause between batches (minutes)

# ── Typing simulation ──────────────────────────────────────────────────────
MIN_TYPING_DELAY: float = 0.04                   # seconds between keystrokes (min)
MAX_TYPING_DELAY: float = 0.12                   # seconds between keystrokes (max)

# ── Browser ────────────────────────────────────────────────────────────────
HEADLESS: bool = False                           # False = visible browser window
BROWSER_TIMEOUT: int = 60_000                    # ms – page/element wait timeout
WHATSAPP_URL: str = "https://web.whatsapp.com"

# ── QR-code wait ───────────────────────────────────────────────────────────
QR_SCAN_TIMEOUT: int = 120                       # seconds user has to scan QR code

# ── Retry ──────────────────────────────────────────────────────────────────
MAX_RETRIES: int = 2                             # retries per contact on failure
RETRY_DELAY: int = 5                             # seconds before a retry attempt

# ── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")  # DEBUG | INFO | WARNING | ERROR
