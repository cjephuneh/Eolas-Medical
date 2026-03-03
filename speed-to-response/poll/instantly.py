"""
Fetch unread emails from Instantly Unibox and normalize to interest signals.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from config import EXCLUDE_SENDER_EMAILS, INSTANTLY_API_KEY, INSTANTLY_BASE_URL

logger = logging.getLogger(__name__)

Signal = dict[str, Any]


def fetch_unread_emails(limit: int = 50) -> list[dict[str, Any]]:
    """
    GET /emails?is_read=false. Returns raw email items from Instantly API.
    """
    if not INSTANTLY_API_KEY:
        logger.warning("INSTANTLY_API_KEY not set; skipping Instantly poll")
        return []
    url = f"{INSTANTLY_BASE_URL}/emails"
    params = {"is_read": "false", "limit": limit}
    headers = {
        "Authorization": f"Bearer {INSTANTLY_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "emails", "results"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []
    except requests.RequestException as e:
        logger.error(
            "SOURCE_FETCH_FAILED",
            extra={"context": {"source": "instantly", "message": str(e)}},
        )
        raise


def normalize_email_to_signal(email: dict[str, Any]) -> Signal:
    """Map one Instantly email object to normalized interest signal (API v1/v2)."""
    eid = (
        email.get("id")
        or email.get("uuid")
        or email.get("email_id")
        or email.get("message_id")
    )
    if not eid:
        eid = str(hash(str(email)))
    signal_id = f"instantly:{eid}"
    from_addr = (
        email.get("from_email")
        or email.get("from_address_email")
        or email.get("from")
        or ""
    )
    subject = email.get("subject") or ""
    body_obj = email.get("body")
    if isinstance(body_obj, dict):
        body = body_obj.get("text") or body_obj.get("html") or ""
    else:
        body = body_obj or email.get("text") or email.get("snippet") or ""
    thread_id = email.get("thread_id") or email.get("thread_uuid") or ""
    to_addr = (
        email.get("to_email")
        or email.get("to_address_email")
        or email.get("to")
        or ""
    )
    reply_to_uuid = (
        email.get("uuid")
        or email.get("id")
        or email.get("email_id")
        or email.get("message_id")
    )
    campaign = email.get("campaign_name") or email.get("campaign_id") or ""
    timestamp = (
        email.get("created_at")
        or email.get("timestamp_created")
        or email.get("timestamp_email")
        or email.get("date")
        or ""
    )

    return {
        "id": signal_id,
        "channel": "email",
        "leadName": from_addr,
        "company": email.get("company_name") or "",
        "campaignOrSequence": campaign,
        "replyText": f"Subject: {subject}\n\n{body}".strip()[:5000],
        "timestamp": timestamp,
        "raw": {
            "thread_id": thread_id,
            "subject": subject,
            "reply_to_uuid": str(reply_to_uuid) if reply_to_uuid else "",
            "to_email": from_addr,
            "from_email": to_addr,
        },
    }


def get_unread_signals(limit: int = 50) -> list[Signal]:
    """Fetch unread emails from Instantly and return normalized signals.
    Excludes any email whose sender (from) is in EXCLUDE_SENDER_EMAILS (our sending mailboxes).
    """
    emails = fetch_unread_emails(limit=limit)
    signals = [normalize_email_to_signal(e) for e in emails]
    if not EXCLUDE_SENDER_EMAILS:
        return signals
    out = []
    for s in signals:
        sender = (s.get("leadName") or "").strip().lower()
        if sender and sender in EXCLUDE_SENDER_EMAILS:
            continue
        out.append(s)
    return out
