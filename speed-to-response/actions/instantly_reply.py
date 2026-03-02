"""
Send an email reply via Instantly API (POST /emails/reply).
Used when AUTO_REPLY_EMAIL is enabled and signal is classified as interested.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from config import (
    INSTANTLY_API_KEY,
    INSTANTLY_BASE_URL,
    INSTANTLY_REPLY_FROM_EMAIL,
)

logger = logging.getLogger(__name__)


def send_email_reply(signal: dict[str, Any], body: str, subject: str = "") -> bool:
    """
    Send reply via Instantly POST /emails/reply.
    signal.raw must contain reply_to_uuid, to_email (lead), from_email (our mailbox).
    Returns True if sent successfully.
    """
    if not INSTANTLY_API_KEY:
        logger.warning("INSTANTLY_API_KEY not set; skipping auto-reply")
        return False
    raw = signal.get("raw") or {}
    reply_to_uuid = raw.get("reply_to_uuid") or ""
    to_email = raw.get("to_email") or signal.get("leadName") or ""
    from_email = (raw.get("from_email") or "").strip() or INSTANTLY_REPLY_FROM_EMAIL.strip()
    if not reply_to_uuid or not to_email:
        logger.debug("Missing reply_to_uuid or to_email in signal; skip Instantly reply")
        return False
    if not from_email:
        logger.warning("INSTANTLY_REPLY_FROM_EMAIL not set; cannot send auto-reply")
        return False
    url = f"{INSTANTLY_BASE_URL.rstrip('/')}/emails/reply"
    payload = {
        "reply_to_uuid": str(reply_to_uuid),
        "from_email": from_email,
        "to_email": to_email,
        "body": body,
    }
    if subject:
        payload["subject"] = subject
    headers = {
        "Authorization": f"Bearer {INSTANTLY_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code in (200, 201, 204):
            logger.info("Instantly reply sent to %s", to_email)
            return True
        logger.warning("Instantly reply failed: %s %s", r.status_code, r.text[:200])
        return False
    except Exception as e:
        logger.exception("Instantly reply request failed: %s", e)
        return False
