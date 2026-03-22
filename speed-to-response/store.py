"""
JSON file store for processed signals. Idempotency by signal id; atomic writes.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PROCESSED_JSON

_RECORDS: list[dict[str, Any]] | None = None


def _ensure_data_dir() -> None:
    PROCESSED_JSON.parent.mkdir(parents=True, exist_ok=True)


def _load() -> list[dict[str, Any]]:
    global _RECORDS
    if _RECORDS is not None:
        return _RECORDS
    _ensure_data_dir()
    if not PROCESSED_JSON.exists():
        _RECORDS = []
        return _RECORDS
    with open(PROCESSED_JSON, "r", encoding="utf-8") as f:
        _RECORDS = json.load(f)
    return _RECORDS


def _save(records: list[dict[str, Any]]) -> None:
    global _RECORDS
    _ensure_data_dir()
    tmp = PROCESSED_JSON.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    tmp.replace(PROCESSED_JSON)
    _RECORDS = records


def is_processed(signal_id: str) -> bool:
    """Return True if this signal id has already been processed."""
    records = _load()
    return any(r.get("id") == signal_id for r in records)


def append(
    signal_id: str,
    channel: str,
    lead_name: str,
    company: str,
    campaign: str,
    reply_text: str,
    classification: str,
    suggested_response: str,
    notified_at: str,
    *,
    email: str = "",
    linkedin_url: str = "",
    reply_to_uuid: str = "",
    from_email: str = "",
    subject: str = "",
) -> None:
    """Append a processed signal and persist atomically. Optional email/reply metadata for send-reply from UI."""
    records = _load()
    records.append(
        {
            "id": signal_id,
            "channel": channel,
            "lead_name": lead_name,
            "company": company,
            "campaign": campaign,
            "reply_text": reply_text[:2000],
            "classification": classification,
            "suggested_response": suggested_response[:2000],
            "notified_at": notified_at,
            "created_at": notified_at,
            "email": (email or "")[:500],
            "linkedin_url": (linkedin_url or "")[:500],
            "reply_to_uuid": (reply_to_uuid or "")[:200],
            "from_email": (from_email or "")[:500],
            "subject": (subject or "")[:500],
        }
    )
    _save(records)


def get_all() -> list[dict[str, Any]]:
    """Return all processed records (for tests)."""
    return list(_load())


def mark_replied(lead_id: str) -> str | None:
    """Set replied_at (UTC ISO) on the record with matching id. Returns timestamp or None if not found."""
    records = _load()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    found = False
    for r in records:
        if str(r.get("id", "")) == str(lead_id):
            r["replied_at"] = ts
            found = True
            break
    if not found:
        return None
    _save(records)
    return ts
