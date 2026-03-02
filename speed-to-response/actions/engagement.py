"""
Custom-written outreach for LinkedIn engagers and uno-reverse (Eolas engagers).
Content-driven: NHS case study and Ask Eolas demo video when configured.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from llm_client import get_client, get_model_name

from config import EOLAS_DEMO_VIDEO_URL, EOLAS_NHS_CASE_STUDY_URL

logger = logging.getLogger(__name__)

EOLAS_CONTEXT_PATH = Path(__file__).resolve().parent.parent.parent / "eolas" / "context.md"


def _load_eolas_context() -> str:
    if EOLAS_CONTEXT_PATH.exists():
        return EOLAS_CONTEXT_PATH.read_text(encoding="utf-8")[:4000]
    return "Eolas: AI-powered knowledge retrieval for healthcare. UK/NHS focus. No cold pitch."


def generate_linkedin_engager_email(
    name: str,
    email: str = "",
    linkedin_url: str = "",
    engagement_type: str = "connected",
) -> dict[str, str]:
    """
    Generate a custom, content-driven outreach email for someone who engaged on LinkedIn
    (liked post, viewed profile, connected but no reply). Not a cold pitch; reference their engagement.
    """
    engagement_label = {
        "liked_post": "liked a recent Eolas post",
        "viewed_profile": "viewed the Eolas profile",
        "connected": "connected with us on LinkedIn",
    }.get(engagement_type, "engaged with Eolas on LinkedIn")

    content_links = []
    if EOLAS_NHS_CASE_STUDY_URL:
        content_links.append(f"NHS case study: {EOLAS_NHS_CASE_STUDY_URL}")
    if EOLAS_DEMO_VIDEO_URL:
        content_links.append(f"Ask Eolas demo: {EOLAS_DEMO_VIDEO_URL}")
    content_line = " ".join(content_links) if content_links else ""

    if not get_client():
        subject = "Quick follow-up from Eolas"
        body = (
            f"Hi {name or 'there'},\n\n"
            "We noticed you recently {engagement_label}. "
            "If you're curious how Eolas supports clinical decision-making at point of care, "
            "we'd be happy to share a short demo or the NHS case study.\n\n"
            f"{content_line}\n\nBest,\nEolas"
        )
        return {"subject": subject, "body": body}

    context = _load_eolas_context()
    prompt = f"""Eolas context:
{context[:2000]}

Write a short, custom outreach EMAIL (not LinkedIn DM) for this prospect:
- Name: {name or 'there'}
- They recently {engagement_label}. This is event-triggered, not cold.
- Keep it to 3-4 sentences. One clear CTA (e.g. short demo or case study).
- Content-driven: do NOT cold pitch. Offer value: NHS case study or Ask Eolas demo if relevant.
{f'- Include one of these when relevant: {content_line}' if content_line else ''}
- Subject line: one short line (under 60 chars), conversational.

Respond with exactly two lines:
Line 1: SUBJECT: <subject>
Line 2: BODY: <email body>"""

    try:
        client = get_client()
        if not client:
            raise RuntimeError("No LLM client")
        resp = client.chat.completions.create(
            model=get_model_name(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        text = (resp.choices[0].message.content or "").strip()
        subject = "Quick follow-up from Eolas"
        body = ""
        for line in text.split("\n"):
            if line.upper().startswith("SUBJECT:"):
                subject = line.split(":", 1)[-1].strip()[:200]
            elif line.upper().startswith("BODY:"):
                body = line.split(":", 1)[-1].strip()
            elif body and line.strip():
                body += "\n" + line
        if not body:
            body = (
                f"Hi {name or 'there'},\n\n"
                f"We noticed you recently {engagement_label}. "
                "If you'd like to see how Eolas supports clinical teams, we're happy to share a short demo.\n\nBest,\nEolas"
            )
        return {"subject": subject, "body": body}
    except Exception as e:
        logger.warning("generate_linkedin_engager_email failed: %s", e)
        return {
            "subject": "Quick follow-up from Eolas",
            "body": f"Hi {name or 'there'},\n\nWe noticed you recently {engagement_label}. We'd be happy to share a short demo or case study.\n\nBest,\nEolas",
        }


def generate_uno_reverse_outreach(
    engagers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    For each engager (Eolas's own LinkedIn engagers), generate content-driven outreach.
    engagers: list of { name, email?, linkedin_url? }.
    Returns list of { name, email, subject, body }.
    """
    out = []
    for eng in engagers:
        name = eng.get("name") or eng.get("full_name") or "there"
        email = eng.get("email") or ""
        linkedin_url = eng.get("linkedin_url") or eng.get("linkedinUrl") or ""
        result = generate_linkedin_engager_email(
            name=name,
            email=email,
            linkedin_url=linkedin_url,
            engagement_type=eng.get("engagement_type") or "connected",
        )
        out.append(
            {
                "name": name,
                "email": email,
                "linkedin_url": linkedin_url,
                "subject": result["subject"],
                "body": result["body"],
            }
        )
    return out
