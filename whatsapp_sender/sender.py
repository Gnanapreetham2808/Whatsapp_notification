"""
WhatsApp Web automation core.

Responsibilities:
- Launch / reuse a persistent Playwright browser session.
- Wait for the user to scan the QR code on first run.
- Navigate to a chat by phone number via the wa.me deep-link trick.
- Type and send a message with human-like delays.
"""

import random
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PWTimeout,
    sync_playwright,
)

import config
from logger import logger

# Selector constants – WhatsApp Web DOM is volatile; centralise them here.
# Chat input: tried in order, first match wins.
_CHAT_INPUT_CANDIDATES = [
    'div[contenteditable="true"][data-lexical-editor="true"]',   # current (Lexical)
    'div[aria-label="Type a message"][contenteditable="true"]',  # older builds
    'footer div[contenteditable="true"]',                        # footer-scoped fallback
    'div[role="textbox"][contenteditable="true"]',               # role-based fallback
    'div[contenteditable="true"][data-tab="10"]',                # legacy data-tab
]
# Send button: tried in order, first match wins.
_SEND_BUTTON_CANDIDATES = [
    'button[aria-label="Send"]',
    'span[data-icon="send"]',
    'button[data-tab="11"]',
]
_SEL_LOGGED_IN = '[aria-label="Chat list"]'
_SEL_INVALID_NUMBER = 'div[data-animate-modal-popup="true"]'    # "Phone number shared via URL is invalid"


class WhatsAppSender:
    """Manages the browser session and message-sending workflow."""

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        # launch_persistent_context returns a BrowserContext directly;
        # there is no separate Browser object in this mode.
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        config.SESSION_DIR.mkdir(parents=True, exist_ok=True)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Launch Playwright, reuse stored session, and ensure login."""
        logger.info("Starting browser …")
        self._playwright = sync_playwright().start()
        # launch_persistent_context is the correct API for user_data_dir;
        # it persists cookies and localStorage across runs so QR is only needed once.
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(config.SESSION_DIR),
            headless=config.HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        # Reuse the page that the persistent context opens, or create one.
        pages = self._context.pages
        self._page = pages[0] if pages else self._context.new_page()
        self._ensure_logged_in()

    def stop(self) -> None:
        """Close the persistent context and Playwright handle cleanly."""
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        logger.info("Browser closed.")

    def restart(self) -> None:
        """Stop and start again – used after a browser crash."""
        logger.warning("Restarting browser session …")
        self.stop()
        self.start()

    # ── Login / session ────────────────────────────────────────────────────

    def _ensure_logged_in(self) -> None:
        """
        Navigate to WhatsApp Web.  If the session is valid the chat list loads
        immediately.  Otherwise we wait for the user to scan the QR code.
        """
        assert self._page is not None
        logger.info("Opening WhatsApp Web …")
        self._page.goto(config.WHATSAPP_URL, wait_until="domcontentloaded")

        try:
            # Fast path: session cookie is valid → chat list appears quickly
            self._page.wait_for_selector(
                _SEL_LOGGED_IN,
                timeout=15_000,
            )
            logger.info("Session restored – no QR scan required.")
            return
        except PWTimeout:
            pass

        # Slow path: QR code is shown
        logger.info(
            "No saved session found.  "
            f"Please scan the QR code within {config.QR_SCAN_TIMEOUT} seconds …"
        )
        try:
            self._page.wait_for_selector(
                _SEL_LOGGED_IN,
                timeout=config.QR_SCAN_TIMEOUT * 1_000,
            )
            logger.info("QR code scanned successfully – session saved.")
        except PWTimeout as exc:
            raise RuntimeError(
                f"QR code was not scanned within {config.QR_SCAN_TIMEOUT}s."
            ) from exc

        # Give WhatsApp a moment to fully hydrate after login
        self._random_wait(2, 4)

    # ── Sending ────────────────────────────────────────────────────────────

    def send_message(self, phone: str, message: str) -> None:
        """
        Send *message* to *phone*.

        Phone must be in international format without '+' or spaces,
        e.g. '919876543210'.

        Raises:
            RuntimeError  – if the chat cannot be opened or the message fails.
        """
        assert self._page is not None

        url = f"{config.WHATSAPP_URL}/send?phone={phone}&text=&type=phone_number&app_absent=0"
        logger.debug(f"Navigating to chat URL for {phone}")

        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=config.BROWSER_TIMEOUT)
        except PWTimeout as exc:
            raise RuntimeError(f"Page load timed out for {phone}") from exc

        # Check for "invalid number" modal before waiting for the chat input
        try:
            self._page.wait_for_selector(_SEL_INVALID_NUMBER, timeout=3_000)
            raise RuntimeError(
                f"WhatsApp says the number {phone} is invalid or not registered."
            )
        except PWTimeout:
            pass  # no modal = good

        # Try each candidate selector in turn; use the first that appears
        input_box = None
        for sel in _CHAT_INPUT_CANDIDATES:
            try:
                self._page.wait_for_selector(sel, timeout=15_000)
                input_box = self._page.locator(sel).first
                logger.debug(f"Chat input matched with selector: {sel}")
                break
            except PWTimeout:
                logger.debug(f"Selector not found: {sel}")

        if input_box is None:
            raise RuntimeError(
                f"Chat input not found for {phone} – number may be invalid or not on WhatsApp."
            )

        self._random_wait(1, 3)

        # Click the input field to focus it
        input_box.click()
        self._random_wait(0.5, 1.5)

        # Type with human-like per-character delays
        self._human_type(input_box, message)
        self._random_wait(0.5, 1.5)

        # Try each send button candidate; fall back to Enter key
        sent = False
        for sel in _SEND_BUTTON_CANDIDATES:
            try:
                btn = self._page.locator(sel).first
                btn.wait_for(timeout=5_000)
                btn.click()
                sent = True
                logger.debug(f"Send button clicked with selector: {sel}")
                break
            except PWTimeout:
                pass
        if not sent:
            logger.debug("Send button not found via any selector, pressing Enter.")
            input_box.press("Enter")

        self._random_wait(1, 2)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _human_type(self, locator, text: str) -> None:
        """Type each character with a random inter-keystroke delay."""
        for char in text:
            locator.type(char, delay=0)          # type one char
            time.sleep(
                random.uniform(config.MIN_TYPING_DELAY, config.MAX_TYPING_DELAY)
            )

    @staticmethod
    def _random_wait(min_s: float, max_s: float) -> None:
        """Sleep for a random duration between min_s and max_s seconds."""
        time.sleep(random.uniform(min_s, max_s))

    def is_page_alive(self) -> bool:
        """Return False if the page has crashed or been closed."""
        try:
            if self._page is None or self._page.is_closed():
                return False
            # Lightweight DOM check
            self._page.evaluate("() => document.title")
            return True
        except Exception:
            return False
