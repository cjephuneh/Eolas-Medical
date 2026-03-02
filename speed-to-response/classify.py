"""
Classify reply text as interested / not_interested / out_of_office / bounce.
Uses Azure OpenAI or OpenAI when configured; otherwise keyword heuristics.
"""
from __future__ import annotations

import logging
import re
from typing import Literal

from llm_client import get_client, get_model_name

logger = logging.getLogger(__name__)

Label = Literal["interested", "not_interested", "out_of_office", "bounce"]

BOUNCE_PATTERNS = [
    r"mailer-daemon",
    r"delivery status",
    r"undeliverable",
    r"recipient.*unknown",
    r"mailbox.*full",
    r"address.*invalid",
]
OOO_PATTERNS = [
    r"out of (the )?office",
    r"out of office",
    r"away from",
    r"on leave",
    r"annual leave",
    r"limited access to (my )?email",
    r"auto.?reply",
    r"automatic reply",
]
NOT_INTERESTED_PATTERNS = [
    r"not interested",
    r"no thanks",
    r"unsubscribe",
    r"remove me",
    r"stop (contacting|emailing)",
    r"do not (contact|email|reach out)",
    r"please remove",
    r"opt.?out",
]


def _keyword_classify(text: str) -> tuple[Label, str]:
    """Classify using keyword rules. Returns (label, reason)."""
    if not text or not text.strip():
        return "not_interested", "Empty or missing reply text"
    lower = text.lower().strip()
    for pattern in BOUNCE_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return "bounce", "Bounce/delivery failure pattern"
    for pattern in OOO_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return "out_of_office", "Out of office / auto-reply"
    for pattern in NOT_INTERESTED_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return "not_interested", "Explicit not interested / unsubscribe"
    # Default: treat as interested if it looks like a real reply (some length, no bulk headers)
    if len(lower) < 10:
        return "not_interested", "Reply too short to be meaningful"
    return "interested", "No negative pattern; likely genuine reply"


def _llm_classify(reply_text: str, subject: str = "") -> tuple[Label, str]:
    """Classify using Azure OpenAI or OpenAI. Returns (label, reason)."""
    client = get_client()
    if not client:
        return _keyword_classify(reply_text)
    prompt = f"""You classify sales lead reply text. Reply text:
---
Subject: {subject or '(none)'}
Body: {reply_text[:2000]}
---
Labels: interested | not_interested | out_of_office | bounce
- interested: person shows interest in learning more, booking a demo, or engaging.
- not_interested: explicit no, unsubscribe, stop contacting, or clearly not a fit.
- out_of_office: auto-reply, on leave, limited access to email.
- bounce: delivery failure, invalid address, mailer-daemon.

Respond with exactly two lines:
Line 1: one label only (interested, not_interested, out_of_office, or bounce)
Line 2: one short reason (e.g. "Asks for a demo" or "Out of office auto-reply")."""
    try:
        resp = client.chat.completions.create(
            model=get_model_name(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
        )
        content = (resp.choices[0].message.content or "").strip()
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        raw_label = (lines[0] or "interested").lower().replace(" ", "_")
        if raw_label in ("interested", "not_interested", "out_of_office", "bounce"):
            label = raw_label
        elif "not_interested" in raw_label or "notinterested" in raw_label:
            label = "not_interested"
        elif "out_of_office" in raw_label or "outofoffice" in raw_label or "ooo" in raw_label:
            label = "out_of_office"
        elif "bounce" in raw_label:
            label = "bounce"
        else:
            label = "interested"
        reason = lines[1] if len(lines) > 1 else "LLM classification"
        return label, reason  # type: ignore
    except Exception as e:
        logger.warning("LLM classify failed, falling back to keywords: %s", e)
        return _keyword_classify(reply_text)


def classify(reply_text: str, subject: str = "") -> tuple[Label, str]:
    """
    Classify reply text. Returns (label, reason).
    Uses Azure OpenAI or OpenAI when configured; else keyword rules.
    """
    if get_client():
        return _llm_classify(reply_text, subject)
    return _keyword_classify(reply_text)
