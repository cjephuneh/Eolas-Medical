"""
Send a LinkedIn message reply via Prosp API (POST /api/v1/leads/send-message).
Used when AUTO_REPLY_LINKEDIN is enabled and signal is classified as interested.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from config import PROSP_API_BASE, PROSP_API_KEY, PROSP_SENDER

logger = logging.getLogger(__name__)


def send_prosp_message(linkedin_url: str, message: str, sender_override: str = "") -> tuple[bool, str | None]:
    """
    Send a LinkedIn message via Prosp POST /api/v1/leads/send-message.
    Uses PROSP_SENDER and PROSP_API_KEY from config.
    Returns (True, None) if sent successfully, (False, error_message) otherwise.
    """
    if not PROSP_API_KEY:
        logger.warning("PROSP_API_KEY not set; skipping Prosp send-message")
        return (False, "PROSP_API_KEY not set")
    sender = (sender_override or PROSP_SENDER or "").strip().rstrip("/")
    if not sender:
        logger.warning("PROSP_SENDER not set; cannot send LinkedIn message")
        return (False, "PROSP_SENDER not set")
    linkedin_url = (linkedin_url or "").strip()
    if not linkedin_url:
        logger.debug("Missing linkedin_url; skip Prosp send-message")
        return (False, "Missing linkedin_url")
    url = f"{PROSP_API_BASE.rstrip('/')}/api/v1/leads/send-message"
    payload = {
        "api_key": PROSP_API_KEY,
        "linkedin_url": linkedin_url,
        "sender": sender,
        "message": message,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-Key": PROSP_API_KEY,
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code in (200, 201, 204):
            logger.info("Prosp send-message succeeded for %s", linkedin_url[:50])
            return (True, None)
        try:
            err_body = r.json()
            msg = err_body.get("message") or err_body.get("error") or r.text or r.reason
        except Exception:
            msg = (r.text or r.reason or str(r.status_code))[:500]
        logger.warning("Prosp send-message failed: %s %s", r.status_code, msg[:200])
        return (False, msg)
    except Exception as e:
        logger.exception("Prosp send-message request failed: %s", e)
        return (False, str(e))


def send_linkedin_reply(signal: dict[str, Any], message: str) -> bool:
    """
    Send message via Prosp POST /api/v1/leads/send-message.
    signal.raw must contain linkedin_url (lead's LinkedIn profile URL).
    sender is PROSP_SENDER (your LinkedIn profile URL). Returns True if sent successfully.
    """
    raw = signal.get("raw") or {}
    linkedin_url = (raw.get("linkedin_url") or "").strip()
    if not linkedin_url:
        logger.debug("Missing linkedin_url in signal; skip Prosp send-message")
        return False
    ok, _ = send_prosp_message(linkedin_url, message)
    return ok
