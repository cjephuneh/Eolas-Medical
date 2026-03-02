"""
Optional: send lead alert via WAHA (WhatsApp HTTP API).
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from config import WAHA_BASE_URL, WAHA_SESSION

logger = logging.getLogger(__name__)


def send_alert(
    signal: dict[str, Any],
    suggested_response: str,
    to_number: str | None = None,
) -> bool:
    """
    Send shortened alert via WAHA. Returns True on success.
    If WAHA_BASE_URL or WAHA_SESSION not set, returns False without sending.
    """
    if not WAHA_BASE_URL or not WAHA_SESSION:
        logger.debug("WAHA not configured; skipping WhatsApp")
        return False
    if not to_number:
        logger.warning("WhatsApp: no to_number provided")
        return False
    lead_name = signal.get("leadName") or "Lead"
    company = signal.get("company") or ""
    text = (
        f"Eolas lead: {lead_name}"
        + (f" ({company})" if company else "")
        + f"\n\nSuggested reply:\n{suggested_response[:500]}"
    )
    url = f"{WAHA_BASE_URL.rstrip('/')}/api/sendText/{WAHA_SESSION}"
    try:
        r = requests.post(
            url,
            json={"phone": to_number, "text": text},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        if not r.ok:
            logger.error("WAHA send failed: %s %s", r.status_code, r.text[:200])
            return False
        return True
    except requests.RequestException as e:
        logger.error("WAHA request failed: %s", e)
        return False
