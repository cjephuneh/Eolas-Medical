"""
Generate a short, reply-ready draft for Ryan/Declan using signal + Eolas context.
Uses Azure OpenAI or OpenAI when configured.
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
    """Load Eolas context for prompt (product, ICP, tone)."""
    if EOLAS_CONTEXT_PATH.exists():
        return EOLAS_CONTEXT_PATH.read_text(encoding="utf-8")[:5000]
    return (
        "Eolas: AI-powered knowledge retrieval for healthcare. "
        "UK/NHS focus. Medical directors, department heads. "
        "No hard sell; reference their reply and offer value."
    )


def _is_academic_medical_director(signal: dict[str, Any]) -> bool:
    """True if lead/company/campaign suggests academic medical director segment (highest response rate)."""
    text = " ".join(
        [
            str(signal.get("leadName") or ""),
            str(signal.get("company") or ""),
            str(signal.get("campaignOrSequence") or ""),
        ]
    ).lower()
    return any(
        phrase in text
        for phrase in ("medical director", "academic", "university", "nhs trust")
    )


def suggest_reply(signal: dict[str, Any]) -> str:
    """
    Return a 2–4 sentence reply draft for the lead.
    Content-driven: when URLs are set, include NHS case study or Ask Eolas demo when relevant.
    Academic medical director segment gets a double-down tone.
    """
    if not get_client():
        draft = (
            "Thanks for your reply. We'd love to show you how Eolas can help. "
            "When can we schedule a short demo?"
        )
        if EOLAS_DEMO_VIDEO_URL:
            draft += f" Here's a short demo: {EOLAS_DEMO_VIDEO_URL}"
        elif EOLAS_NHS_CASE_STUDY_URL:
            draft += f" NHS case study: {EOLAS_NHS_CASE_STUDY_URL}"
        return draft
    context = _load_eolas_context()
    lead_name = signal.get("leadName") or "there"
    company = signal.get("company") or ""
    campaign = signal.get("campaignOrSequence") or ""
    reply_text = (signal.get("replyText") or "")[:2000]
    channel = signal.get("channel", "email")
    is_amd = _is_academic_medical_director(signal)

    content_instruction = ""
    if EOLAS_NHS_CASE_STUDY_URL or EOLAS_DEMO_VIDEO_URL:
        parts = []
        if EOLAS_NHS_CASE_STUDY_URL:
            parts.append(f"NHS case study: {EOLAS_NHS_CASE_STUDY_URL}")
        if EOLAS_DEMO_VIDEO_URL:
            parts.append(f"Ask Eolas demo video: {EOLAS_DEMO_VIDEO_URL}")
        content_instruction = (
            "\n- Content-driven: when relevant, naturally include one of these links in your draft: "
            + " | ".join(parts)
        )
    amd_instruction = (
        "\n- This lead is likely an academic medical director (highest response segment): double down with a concise value prop and clear demo ask."
        if is_amd
        else ""
    )

    prompt = f"""Eolas context (use for tone and product):
{context[:2500]}

Lead reply (channel: {channel}):
{reply_text}

Write a short, reply-ready draft (2–4 sentences) for the sales team to send back. 
- UK/NHS focus; medical directors/department heads.
- No hard sell. Reference what they said and offer a next step (e.g. short demo).
- Sound human and concise. Do not use bullet lists unless the lead did.{content_instruction}{amd_instruction}"""

    try:
        client = get_client()
        if not client:
            return _fallback_draft(lead_name)
        resp = client.chat.completions.create(
            model=get_model_name(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        draft = (resp.choices[0].message.content or "").strip()
        return draft if draft else _fallback_draft(lead_name)
    except Exception as e:
        logger.warning("suggest_reply LLM failed: %s", e)
        return _fallback_draft(lead_name)


def _fallback_draft(lead_name: str) -> str:
    return (
        f"Thanks for getting back to us. We'd love to show you how Eolas can help. "
        f"When would work for a short demo?"
    )


def _first_name(full_name: str) -> str:
    """Extract first name for greeting; fallback 'there' if empty."""
    if not full_name or not str(full_name).strip():
        return "there"
    return str(full_name).strip().split()[0]


def format_prosp_thread_for_prompt(messages: list[dict[str, Any]], max_messages: int = 25) -> str:
    """Turn dashboard message rows into a compact thread for the LLM prompt."""
    lines: list[str] = []
    slice_msgs = messages[-max_messages:] if len(messages) > max_messages else messages
    for m in slice_msgs:
        if not isinstance(m, dict):
            continue
        role = "You" if m.get("from_me") else "Lead"
        c = str(m.get("content") or "").strip()
        if c:
            lines.append(f"{role}: {c}")
    return "\n".join(lines)


def generate_linkedin_message(
    lead_name: str,
    context: str = "",
    *,
    thread_context: str = "",
) -> str:
    """
    Generate a LinkedIn DM: cold outreach (Hello …) or a follow-up when thread_context is set.
    context = campaign name / description; thread_context = recent messages (You:/Lead: lines).
    """
    first = _first_name(lead_name)
    tc = (thread_context or "").strip()
    if not get_client():
        if tc:
            return (
                "Thanks for your message. I'd be happy to share how Eolas helps clinical teams "
                "get instant answers from their knowledge. Would a brief call this week work?"
            )
        return (
            f"Hello {first},\n\n"
            "I noticed your profile and thought Eolas could be relevant for your work in healthcare. "
            "We help teams get instant answers from their clinical knowledge. "
            "Would you be open to a short demo?"
        )
    if tc:
        prompt = f"""You are replying in an existing LinkedIn DM thread with {first} (lead name for context only).

Recent messages in the thread (oldest to newest):
{tc[:6000]}

Write a short follow-up message (2–5 sentences). Reference what they said if relevant.
- Professional, UK/NHS healthcare context where appropriate.
- Eolas: AI-powered knowledge retrieval for clinical teams; offer a short demo or next step if natural.
- Do not paste the whole thread back. Do not use a subject line."""
        if context:
            prompt += f"\n\nCampaign/campaign context:\n{context[:800]}"
        prompt += "\n\nOutput only the message body to send."
    else:
        prompt = f"""Write a short LinkedIn message to this lead. Rules:
- Start exactly with "Hello {first}," (use this first name).
- 2-4 sentences max. Professional, no hard sell.
- Eolas: AI-powered knowledge retrieval for healthcare (UK/NHS focus). Offer a short demo or value.
"""
        if context:
            prompt += f"\nCampaign/context to guide the message:\n{context[:800]}"
        prompt += "\nOutput only the message, no subject line."
    try:
        client = get_client()
        if not client:
            return f"Hello {first},\n\nWould you be open to a short demo of Eolas?"
        resp = client.chat.completions.create(
            model=get_model_name(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=350,
        )
        draft = (resp.choices[0].message.content or "").strip()
        if tc:
            return draft if draft else (
                "Thanks for your message — I'd be happy to share more about Eolas. "
                "Would a short call work this week?"
            )
        if draft and not draft.lower().startswith("hello"):
            draft = f"Hello {first},\n\n{draft}"
        return draft if draft else f"Hello {first},\n\nWould you be open to a short demo of Eolas?"
    except Exception as e:
        logger.warning("generate_linkedin_message failed: %s", e)
        return (
            f"Thanks for your message. Would you be open to a short demo of Eolas?"
            if tc
            else f"Hello {first},\n\nWould you be open to a short demo of Eolas for your team?"
        )


def generate_linkedin_bulk_template(campaign_name: str, campaign_description: str = "") -> str:
    """
    Generate a LinkedIn message template for bulk send. Use literal {name} so each lead gets "Hello X,".
    Caller will replace {name} with the lead's first name.
    """
    if not get_client():
        return (
            "Hello {name},\n\n"
            "I thought Eolas could be relevant for your work in healthcare. "
            "We help teams get instant answers from their clinical knowledge. "
            "Would you be open to a short demo?"
        )
    prompt = f"""Write a short LinkedIn message template for a campaign. Rules:
- Use the literal placeholder {{name}} for the lead's first name (e.g. "Hello {{name}},").
- 2-4 sentences after the greeting. Professional, no hard sell.
- Eolas: AI-powered knowledge retrieval for healthcare (UK/NHS focus). Offer a short demo.
"""
    if campaign_name:
        prompt += f"\nCampaign name: {campaign_name}"
    if campaign_description:
        prompt += f"\nCampaign description/context:\n{campaign_description[:1000]}"
    prompt += "\nOutput only the message. Keep {name} as literal placeholder."
    try:
        client = get_client()
        resp = client.chat.completions.create(
            model=get_model_name(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
        )
        draft = (resp.choices[0].message.content or "").strip()
        if draft and "{name}" not in draft and "{ name }" not in draft:
            draft = "Hello {name},\n\n" + draft
        return draft if draft else "Hello {name},\n\nWould you be open to a short demo of Eolas?"
    except Exception as e:
        logger.warning("generate_linkedin_bulk_template failed: %s", e)
        return "Hello {name},\n\nWould you be open to a short demo of Eolas for your team?"
