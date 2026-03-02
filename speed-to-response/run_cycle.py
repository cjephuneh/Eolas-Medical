"""
Single poll → classify → notify cycle. Called by scheduler or POST /run-cycle.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from config import AUTO_REPLY_EMAIL, AUTO_REPLY_LINKEDIN, PROSP_API_KEY
from classify import classify
from poll.instantly import get_unread_signals as get_instantly_signals
from poll.prosp import get_unread_signals as get_prosp_signals
from poll.prosp import get_prosp_signals_via_campaigns
from suggest_reply import suggest_reply
from notify.slack import send_alert as send_slack_alert
from store import is_processed, append
from actions.instantly_reply import send_email_reply
from actions.prosp_reply import send_linkedin_reply

logger = logging.getLogger(__name__)


def _lead_display_name(lead_name: str) -> str:
    """Derive a display name for personalization: use part before @ if email, else lead_name; fallback 'there'."""
    if not lead_name or not str(lead_name).strip():
        return "there"
    s = str(lead_name).strip()
    if "@" in s:
        local = s.split("@", 1)[0].strip()
        return (local[0].upper() + local[1:].lower()) if local else "there"
    return s


def _suggested_to_linkedin_message(suggested: str) -> str:
    """Strip email-style 'Subject: ...' prefix so we send only the message body to LinkedIn."""
    if not suggested or not suggested.strip():
        return suggested
    s = suggested.strip()
    if s.upper().startswith("SUBJECT:") and "\n" in s:
        return s.split("\n", 1)[1].strip()
    return s


def _personalize_suggested(suggested: str, lead_name: str) -> str:
    """Replace [Name], [Lead's Name], [Recipient's Name], etc. with the lead's display name before sending."""
    if not suggested:
        return suggested
    name = _lead_display_name(lead_name)
    out = suggested
    for placeholder in ("[Name]", "[Lead's Name]", "[Recipient's Name]", "[Lead Name]", "[Recipient]", "[lead name]"):
        out = out.replace(placeholder, name)
    return out


def run_cycle() -> dict[str, int]:
    """
    Fetch Instantly + LinkedIn (Prosp) unread, dedupe, classify, notify for "interested", log.
    Returns counts: { "fetched": N, "interested": M, "notified": K, "skipped_already_processed": P }.
    """
    counts = {"fetched": 0, "interested": 0, "notified": 0, "skipped_already_processed": 0}

    signals: list[dict] = []
    try:
        signals.extend(get_instantly_signals(limit=50))
    except Exception as e:
        logger.exception("Instantly fetch failed: %s", e)
    try:
        if PROSP_API_KEY:
            signals.extend(get_prosp_signals())
            # Also pull via campaign → leads → conversation (when list endpoint returns no threads)
            signals.extend(get_prosp_signals_via_campaigns())  # uses PROSP_MAX_CAMPAIGNS (0=all), PROSP_MAX_LEADS_PER_CAMPAIGN from config
    except Exception as e:
        logger.exception("LinkedIn (Prosp) fetch failed: %s", e)

    counts["fetched"] = len(signals)

    now = datetime.now(tz=timezone.utc).isoformat()
    for signal in signals:
        signal_id = signal.get("id") or ""
        if not signal_id:
            continue
        if is_processed(signal_id):
            counts["skipped_already_processed"] += 1
            continue

        reply_text = signal.get("replyText") or ""
        subject = (signal.get("raw") or {}).get("subject") or ""
        label, _reason = classify(reply_text, subject=subject)

        if label == "interested":
            counts["interested"] += 1
            suggested = suggest_reply(signal)
            suggested = _personalize_suggested(suggested, signal.get("leadName") or "")
            if send_slack_alert(signal, suggested):
                counts["notified"] += 1
            if signal.get("channel") == "email" and AUTO_REPLY_EMAIL:
                subject = (signal.get("raw") or {}).get("subject") or ""
                send_email_reply(signal, suggested, subject=subject)
            if signal.get("channel") == "linkedin" and AUTO_REPLY_LINKEDIN:
                linkedin_message = _suggested_to_linkedin_message(suggested)
                send_linkedin_reply(signal, linkedin_message)
            raw = signal.get("raw") or {}
            append(
                signal_id=signal_id,
                channel=signal.get("channel", ""),
                lead_name=signal.get("leadName") or "",
                company=signal.get("company") or "",
                campaign=signal.get("campaignOrSequence") or "",
                reply_text=reply_text[:2000],
                classification=label,
                suggested_response=suggested,
                notified_at=now,
                email=raw.get("to_email") or "",
                linkedin_url=raw.get("linkedin_url") or "",
                reply_to_uuid=raw.get("reply_to_uuid") or "",
                from_email=raw.get("from_email") or "",
            )
        else:
            raw = signal.get("raw") or {}
            append(
                signal_id=signal_id,
                channel=signal.get("channel", ""),
                lead_name=signal.get("leadName") or "",
                company=signal.get("company") or "",
                campaign=signal.get("campaignOrSequence") or "",
                reply_text=reply_text[:2000],
                classification=label,
                suggested_response="",
                notified_at=now,
                email=raw.get("to_email") or "",
                linkedin_url=raw.get("linkedin_url") or "",
                reply_to_uuid=raw.get("reply_to_uuid") or "",
                from_email=raw.get("from_email") or "",
            )

    return counts
