"""
Fetch unread emails from Instantly Unibox and normalize to interest signals.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from config import INSTANTLY_API_KEY, INSTANTLY_BASE_URL, is_our_sending_address

logger = logging.getLogger(__name__)

Signal = dict[str, Any]


def _looks_outbound(email: dict[str, Any]) -> bool:
    """Instantly may mark sent/outbound items."""
    if email.get("is_outbound") is True or email.get("isOutbound") is True:
        return True
    for key in ("direction", "email_direction", "Direction"):
        v = str(email.get(key) or "").strip().lower()
        if v in ("outbound", "outgoing", "sent", "send"):
            return True
    for key in ("type", "email_type", "message_type", "emailType"):
        v = str(email.get(key) or "").strip().lower()
        if v in ("sent", "outbound", "send", "out"):
            return True
    return False


def _resolve_respondent_and_mailbox(
    email: dict[str, Any],
    from_addr: str,
    to_addr: str,
) -> tuple[str, str] | None:
    """
    Return (respondent_email, our_mailbox_email) or None to skip this row.

    Instantly Unibox often lists items with **from = our connected mailbox** and **to = the
    external contact** even for inbound replies. In that case the real **sender of the message
    content** is **to_addr** (the prospect), not Declan.

    We skip rows that are clearly **our outbound** sends (direction/type) when from=ours and
    to=external.
    """
    fa, ta = from_addr.strip(), to_addr.strip()

    # Classic inbound: external sender (From = prospect)
    if fa and not is_our_sending_address(fa):
        return (fa, ta)

    # From is ours (Declan…) — either outbound we sent, or API-inverted inbound
    if is_our_sending_address(fa):
        if not ta or is_our_sending_address(ta):
            return None
        if _looks_outbound(email):
            return None
        return (ta, fa)

    if ta and not is_our_sending_address(ta):
        return (ta, fa)

    return None


def _extract_from_to(email: dict[str, Any]) -> tuple[str, str]:
    """Return (from_address, to_address) from common Instantly field names."""
    from_addr = (
        email.get("from_email")
        or email.get("from_address_email")
        or email.get("from")
        or email.get("sender_email")
        or email.get("sender")
        or ""
    )
    if isinstance(from_addr, dict):
        from_addr = from_addr.get("email") or from_addr.get("address") or ""
    to_addr = (
        email.get("to_email")
        or email.get("to_address_email")
        or email.get("to")
        or email.get("recipient_email")
        or ""
    )
    if isinstance(to_addr, dict):
        to_addr = to_addr.get("email") or to_addr.get("address") or ""
    if isinstance(to_addr, list) and to_addr:
        first = to_addr[0]
        to_addr = first.get("email") if isinstance(first, dict) else str(first)
    return str(from_addr or "").strip(), str(to_addr or "").strip()


def _fetch_emails(limit: int = 50, unread_only: bool = True) -> list[dict[str, Any]]:
    """
    GET /emails. Returns raw email items from Instantly API.
    When unread_only=True uses is_read=false; when False, omits filter to get all messages from all inboxes.
    """
    if not INSTANTLY_API_KEY:
        logger.warning("INSTANTLY_API_KEY not set; skipping Instantly poll")
        return []
    url = f"{INSTANTLY_BASE_URL}/emails"
    params = {"limit": limit}
    if unread_only:
        params["is_read"] = "false"
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


def fetch_unread_emails(limit: int = 50) -> list[dict[str, Any]]:
    """GET /emails?is_read=false. Returns raw unread email items."""
    return _fetch_emails(limit=limit, unread_only=True)


def _extract_instantly_message_id(email: dict[str, Any]) -> str:
    """UUID/id for POST /emails/reply — Instantly field names vary by version."""
    for key in (
        "id",
        "uuid",
        "email_id",
        "message_id",
        "email_uuid",
        "message_uuid",
    ):
        v = email.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def normalize_email_to_signal(email: dict[str, Any]) -> Signal | None:
    """Map one Instantly email object to normalized interest signal (API v1/v2).

    Only **inbound** replies from prospects are kept: if the **sender** (From) is one of our
    mailboxes, this is our outbound message — skipped (not a response from a lead).

    raw.to_email = respondent (prospect) — recipient of our reply when using Instantly /emails/reply.
    raw.from_email = our mailbox (Declan, etc.).
    """
    msg_id = _extract_instantly_message_id(email)
    if not msg_id:
        msg_id = str(hash(str(email)))
    signal_id = f"instantly:{msg_id}"
    from_addr, to_addr = _extract_from_to(email)

    resolved = _resolve_respondent_and_mailbox(email, from_addr, to_addr)
    if not resolved:
        logger.debug(
            "Instantly: skip email (could not resolve respondent or outbound): from=%s to=%s",
            from_addr[:80],
            to_addr[:80],
        )
        return None
    respondent, our_mailbox = resolved

    subject = email.get("subject") or ""
    body_obj = email.get("body")
    if isinstance(body_obj, dict):
        body = body_obj.get("text") or body_obj.get("html") or ""
    else:
        body = body_obj or email.get("text") or email.get("snippet") or ""
    thread_id = email.get("thread_id") or email.get("thread_uuid") or ""
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
        "leadName": respondent,
        "company": email.get("company_name") or "",
        "campaignOrSequence": campaign,
        "replyText": f"Subject: {subject}\n\n{body}".strip()[:5000],
        "timestamp": timestamp,
        "raw": {
            "thread_id": thread_id,
            "subject": subject,
            "reply_to_uuid": msg_id,
            # send_email_reply: to_email = lead (respondent), from_email = our mailbox
            "to_email": respondent,
            "from_email": our_mailbox,
            "respondent_email": respondent,
            "our_mailbox": our_mailbox,
            "instantly_from_raw": from_addr,
            "instantly_to_raw": to_addr,
        },
    }


def get_unread_signals(limit: int = 50) -> list[Signal]:
    """Fetch unread emails from Instantly and return normalized signals.
    Excludes any email whose sender (from) is in EXCLUDE_SENDER_EMAILS (our sending mailboxes).
    """
    emails = fetch_unread_emails(limit=limit)
    signals = [_s for e in emails for _s in [normalize_email_to_signal(e)] if _s is not None]
    return _filter_excluded_sender_signals(signals)


def get_all_email_signals(limit: int = 100) -> list[Signal]:
    """Fetch all emails (read + unread) from Instantly — all inboxes. Returns normalized signals.
    Excludes sending mailboxes (EXCLUDE_SENDER_EMAILS).
    """
    emails = _fetch_emails(limit=limit, unread_only=False)
    signals = [_s for e in emails for _s in [normalize_email_to_signal(e)] if _s is not None]
    return _filter_excluded_sender_signals(signals)


def _filter_excluded_sender_signals(signals: list[Signal]) -> list[Signal]:
    """Drop signals whose respondent still looks like our mailbox (safety net)."""
    out = []
    for s in signals:
        sender = (s.get("leadName") or "").strip()
        if sender and is_our_sending_address(sender):
            continue
        out.append(s)
    return out
