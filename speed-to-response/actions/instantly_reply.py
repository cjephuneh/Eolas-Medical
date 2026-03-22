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


def _reply_subject_line(signal: dict[str, Any], explicit_subject: str) -> str:
    """Instantly requires a subject; default Re: from raw or thread text."""
    e = (explicit_subject or "").strip()
    if e:
        return e if e.lower().startswith("re:") else f"Re: {e}"
    raw = signal.get("raw") or {}
    s = (raw.get("subject") or "").strip()
    if s:
        return s if s.lower().startswith("re:") else f"Re: {s}"
    rt = (signal.get("replyText") or "")
    for line in rt.split("\n")[:12]:
        low = line.strip().lower()
        if low.startswith("subject:"):
            subj = line.split(":", 1)[1].strip()
            if subj:
                return subj if subj.lower().startswith("re:") else f"Re: {subj}"
    return "Re:"


def send_email_reply(signal: dict[str, Any], body: str, subject: str = "") -> bool:
    """
    Send reply via Instantly POST /emails/reply.

    Current API (v2) requires: reply_to_uuid, eaccount (connected mailbox),
    subject, body: { text and/or html }.

    signal.raw should contain reply_to_uuid, to_email (lead), from_email (our mailbox / eaccount).
    """
    if not INSTANTLY_API_KEY:
        logger.warning("INSTANTLY_API_KEY not set; skipping auto-reply")
        return False
    raw = signal.get("raw") or {}
    reply_to_uuid = raw.get("reply_to_uuid") or ""
    to_email = raw.get("to_email") or signal.get("leadName") or ""
    # eaccount = which connected Instantly mailbox sends the reply (same as from_address)
    eaccount = (raw.get("from_email") or "").strip() or INSTANTLY_REPLY_FROM_EMAIL.strip()
    if not reply_to_uuid or not to_email:
        logger.debug("Missing reply_to_uuid or to_email in signal; skip Instantly reply")
        return False
    if not eaccount:
        logger.warning(
            "INSTANTLY_REPLY_FROM_EMAIL or raw.from_email required for eaccount; cannot send reply"
        )
        return False
    reply_subject = _reply_subject_line(signal, subject)
    url = f"{INSTANTLY_BASE_URL.rstrip('/')}/emails/reply"
    payload = {
        "eaccount": eaccount,
        "reply_to_uuid": str(reply_to_uuid),
        "subject": reply_subject,
        "body": {"text": body},
    }
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
