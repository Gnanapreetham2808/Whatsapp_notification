# WhatsApp Bulk Sender

Send personalised WhatsApp messages from your own account using WhatsApp Web automation.  
Built with **Python 3.11+**, **Playwright**, and **Pandas**.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Playwright Setup](#playwright-setup)
4. [Project Structure](#project-structure)
5. [CSV Format](#csv-format)
6. [Message Template](#message-template)
7. [Configuration](#configuration)
8. [Running the Application](#running-the-application)
9. [Console Output](#console-output)
10. [Sent Log](#sent-log)
11. [Recovery After Crash](#recovery-after-crash)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python      | 3.11+   |
| pip         | latest  |
| A WhatsApp account linked to a phone | – |

---

## Installation

```bash
# 1. Clone or copy the project folder
cd whatsapp_sender

# 2. (Recommended) Create a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt
```

---

## Playwright Setup

Playwright needs to download the Chromium browser binary once:

```bash
python -m playwright install chromium
```

If you are behind a corporate proxy, set `PLAYWRIGHT_BROWSERS_PATH` to a
writable directory and ensure the proxy allows HTTPS to `playwright.azureedge.net`.

---

## Project Structure

```
whatsapp_sender/
├── app.py              ← entry point
├── config.py           ← all tuneable settings
├── sender.py           ← Playwright / WhatsApp Web automation
├── logger.py           ← Python logger + CSV log helpers
├── requirements.txt
├── contacts.csv        ← your contact list
├── sent_log.csv        ← auto-generated delivery log
├── templates/
│   └── message.txt     ← message template
└── .session/           ← auto-created; stores the browser session
```

---

## CSV Format

Edit **`contacts.csv`** before running.  The file must have exactly these
two columns (case-insensitive):

```
name,phone
John,919876543210
Sarah,919876543211
```

* **name** – used to personalise the message via `{name}` placeholder.  
* **phone** – international format, digits only, **no** `+`, spaces, or dashes.  
  Example: India `91` + `9876543210` → `919876543210`.

Up to **150** contacts are processed per run.

---

## Message Template

Edit **`templates/message.txt`**.  Use `{name}` anywhere you want the
recipient's name inserted:

```
Hi {name},

This is a reminder regarding our upcoming event.

Thank you.
```

The file is read fresh on every run, so you can edit it between runs without
restarting.

---

## Configuration

All settings live in **`config.py`**:

| Setting | Default | Description |
|---------|---------|-------------|
| `BATCH_SIZE` | `30` | Messages per batch before a long pause |
| `MIN_DELAY` | `5` | Minimum seconds between messages |
| `MAX_DELAY` | `15` | Maximum seconds between messages |
| `BATCH_PAUSE_MINUTES` | `20` | Minutes to pause between batches |
| `MIN_TYPING_DELAY` | `0.04` | Minimum seconds per keystroke |
| `MAX_TYPING_DELAY` | `0.12` | Maximum seconds per keystroke |
| `HEADLESS` | `False` | `True` = invisible browser (not recommended) |
| `BROWSER_TIMEOUT` | `60000` | Milliseconds to wait for page elements |
| `QR_SCAN_TIMEOUT` | `120` | Seconds given to scan the QR code |
| `MAX_RETRIES` | `2` | Retry attempts per contact on failure |
| `RETRY_DELAY` | `5` | Seconds to wait before each retry |

---

## Running the Application

```bash
python app.py
```

**First run:**  
A Chromium window opens to `web.whatsapp.com`.  
Open WhatsApp on your phone → **Linked Devices** → **Link a Device** and scan the QR code.  
The session is saved to `.session/` so you only do this once.

**Subsequent runs:**  
The saved session is reused automatically — no QR scan required.

---

## Console Output

```
[1/150] Sending to John (919876543210)
  Message sent.
  Waiting 11 seconds …

[2/150] Sending to Sarah (919876543211)
  Message sent.
  Waiting 8 seconds …

…

[30/150] Sending to … (…)

Batch complete.  Sleeping 20 minutes …
  Resuming in 19:42 …

[31/150] Sending to …
```

---

## Sent Log

`sent_log.csv` is created automatically and appended after each contact:

```
phone,name,status,timestamp,error
919876543210,John,SENT,2024-06-01 10:05:23,
919876543211,Sarah,FAILED,2024-06-01 10:05:45,Chat input not found …
919876543212,Michael,SKIPPED,2024-06-01 10:05:45,
```

| Status | Meaning |
|--------|---------|
| `SENT` | Message delivered successfully |
| `FAILED` | All retry attempts exhausted |
| `SKIPPED` | Phone already had a `SENT` entry from a previous run |

---

## Recovery After Crash

If the application crashes mid-run, simply restart it:

```bash
python app.py
```

On startup, `sent_log.csv` is read and every phone number with status `SENT`
is skipped.  The run continues from where it left off.

---

## Troubleshooting

### "QR code was not scanned within 120s"
Increase `QR_SCAN_TIMEOUT` in `config.py` or restart and scan faster.

### "Chat input not found for … – number may be invalid or not on WhatsApp"
The phone number is not registered on WhatsApp, or it has blocked your
account.  The contact is marked `FAILED` and processing continues.

### Messages stop sending after ~50 contacts
WhatsApp may have temporarily rate-limited your account.  Increase
`MIN_DELAY` / `MAX_DELAY` and reduce `BATCH_SIZE`.

### Browser crashes repeatedly
Set `HEADLESS = False` (already the default) and watch the window for clues.
If Chromium fails to launch, run `python -m playwright install chromium` again.

### Session expires unexpectedly
Delete the `.session/` folder and re-scan the QR code on the next run.

### "Failed to read contacts.csv"
Ensure the file is saved as UTF-8 and uses comma as the delimiter.  Avoid
Excel's default ANSI encoding — use "Save As → CSV UTF-8" instead.
