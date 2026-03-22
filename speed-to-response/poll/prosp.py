"""
Prosp API: fetch LinkedIn conversations and normalize to signals.
Uses Prosp API (prosp.ai) for conversation/inbox endpoints.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

from config import (
    PROSP_API_BASE,
    PROSP_API_KEY,
    PROSP_CONVERSATIONS_PATH,
    PROSP_MAX_CAMPAIGNS,
    PROSP_MAX_LEADS_PER_CAMPAIGN,
    PROSP_SENDER,
)

logger = logging.getLogger(__name__)

Signal = dict[str, Any]


def _auth_headers() -> dict[str, str]:
    """Prosp API key: X-API-Key or Authorization Bearer common."""
    return {
        "X-API-Key": PROSP_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _auth_bearer() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {PROSP_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _post_json(path: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, int]:
    """POST to Prosp API; return (parsed JSON or None, status_code)."""
    url = f"{PROSP_API_BASE.rstrip('/')}/{path.lstrip('/')}"
    payload["api_key"] = PROSP_API_KEY
    for headers in (_auth_headers(), _auth_bearer()):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=30)
            if r.status_code != 200:
                return (None, r.status_code)
            ct = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
            if ct != "application/json" or (r.text or "").strip().upper().startswith("<!DOCTYPE"):
                return (None, r.status_code)
            return (r.json(), r.status_code)
        except Exception:
            continue
    return (None, 0)


def fetch_campaigns() -> list[dict[str, Any]]:
    """Fetch campaign list (campaign_id, campaign_name). POST api/v1/campaigns/lists."""
    out, code = _post_json("api/v1/campaigns/lists", {})
    if code != 200 or not out:
        return []
    data = out.get("data") if isinstance(out, dict) else None
    return list(data) if isinstance(data, list) else []


def fetch_leads_for_campaign(campaign_id: str) -> list[dict[str, Any]]:
    """Fetch leads in a campaign (name, linkedinUrl). POST api/v1/campaigns/leads."""
    out, code = _post_json("api/v1/campaigns/leads", {"campaign_id": campaign_id})
    if code != 200 or not out:
        return []
    data = out.get("data") if isinstance(out, dict) else None
    return list(data) if isinstance(data, list) else []


def _post_json_raw(path: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, int, str]:
    """POST to Prosp API; return (parsed JSON or None, status_code, response_text_preview)."""
    url = f"{PROSP_API_BASE.rstrip('/')}/{path.lstrip('/')}"
    payload["api_key"] = PROSP_API_KEY
    for headers in (_auth_headers(), _auth_bearer()):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=30)
            text = (r.text or "").strip()
            preview = text[:500] if text else ""
            if r.status_code != 200:
                return (None, r.status_code, preview)
            ct = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
            if ct != "application/json" or text.upper().startswith("<!DOCTYPE") or text.startswith("<html"):
                return (None, r.status_code, preview)
            return (r.json(), r.status_code, preview)
        except Exception as e:
            return (None, 0, str(e)[:200])
    return (None, 0, "no response")


def fetch_conversation_for_lead(linkedin_url: str, sender: str = "") -> dict[str, Any] | None:
    """Fetch conversation for one lead. POST api/v1/leads/conversation. Returns full JSON or None."""
    payload: dict[str, Any] = {"linkedin_url": linkedin_url, "sender": sender or PROSP_SENDER or "default"}
    out, code, _ = _post_json_raw("api/v1/leads/conversation", payload)
    return out if code == 200 else None


def fetch_conversation_for_lead_debug(linkedin_url: str, sender: str = "") -> tuple[dict[str, Any] | None, int, str]:
    """Same as fetch_conversation_for_lead but returns (data, status_code, response_preview) for debugging."""
    payload: dict[str, Any] = {"linkedin_url": linkedin_url, "sender": sender or PROSP_SENDER or "default"}
    out, code, preview = _post_json_raw("api/v1/leads/conversation", payload)
    return (out, code, preview)


def _request_conversations(
    method: str,
    url: str,
    headers: dict[str, str],
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], bool]:
    """Make request; return (parsed list, True if status was 200 and body is JSON else False)."""
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=30, **kwargs)
        else:
            r = requests.post(url, headers=headers, timeout=30, **kwargs)
        if r.status_code != 200:
            return ([], False)
        # Ignore 200 with HTML (e.g. SPA fallback); only accept JSON
        ct = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
        text = (r.text or "").strip()
        if ct != "application/json" or text.upper().startswith("<!DOCTYPE") or text.startswith("<html"):
            return ([], False)
        data = r.json()
        parsed = _parse_conversations_response(data)
        # Reject lists that are not conversations (e.g. campaigns/lists returns { data: [ { campaign_id, campaign_name } ] })
        if parsed and not _looks_like_conversation_list(parsed):
            return ([], False)
        if not parsed and data is not None:
            if isinstance(data, dict) and not (
                isinstance(data.get("items"), list)
                or isinstance(data.get("conversations"), list)
                or isinstance(data.get("results"), list)
                or isinstance(data.get("threads"), list)
                or isinstance(data.get("messages"), list)
                or isinstance(data.get("data"), list)
            ):
                logger.info(
                    "Prosp 200 but no conversation list parsed. URL=%s. Top-level keys: %s",
                    url,
                    list(data.keys()) if isinstance(data, dict) else type(data),
                )
        return (parsed, True)
    except Exception:
        return ([], False)


def fetch_unread_conversations() -> list[dict[str, Any]]:
    """
    Fetch conversations that need a reply (unread/unanswered).
    If PROSP_CONVERSATIONS_PATH is set, use that only; else try common paths.
    """
    if not PROSP_API_KEY:
        logger.debug("PROSP_API_KEY not set; skipping Prosp poll")
        return []

    base = PROSP_API_BASE.rstrip("/")
    # Prosp uses api_key in body for some endpoints; try header first
    for headers in (_auth_headers(), _auth_bearer()):
        if PROSP_CONVERSATIONS_PATH:
            path = PROSP_CONVERSATIONS_PATH.lstrip("/")
            for m in ("GET", "POST"):
                out, ok = _request_conversations(
                    m,
                    f"{base}/{path}",
                    headers,
                    **({"params": {"api_key": PROSP_API_KEY}} if m == "GET" else {"json": {"api_key": PROSP_API_KEY}}),
                )
                if ok:
                    return out
            continue

        # Try Prosp API paths (doc: https://prosp.apidocumentation.com/combined-api)
        # campaigns/lists returns 405 for GET → try POST
        candidates = [
            ("GET", f"{base}/api/v1/campaigns/lists", {"params": {"api_key": PROSP_API_KEY}}),
            ("POST", f"{base}/api/v1/campaigns/lists", {"json": {"api_key": PROSP_API_KEY}}),
            ("GET", f"{base}/api/v1/conversations", {"params": {"api_key": PROSP_API_KEY}}),
            ("GET", f"{base}/api/v1/campaigns/conversations", {"params": {"api_key": PROSP_API_KEY}}),
            ("GET", f"{base}/api/v1/inbox", {"params": {"api_key": PROSP_API_KEY}}),
            ("GET", f"{base}/api/v1/messages", {"params": {"api_key": PROSP_API_KEY}}),
            ("POST", f"{base}/api/v1/conversations", {"json": {"api_key": PROSP_API_KEY}}),
            ("POST", f"{base}/api/v1/inbox", {"json": {"api_key": PROSP_API_KEY}}),
        ]
        for method, url, kw in candidates:
            out, ok = _request_conversations(method, url, headers, **kw)
            if ok:
                return out

    logger.debug(
        "Prosp: no single list endpoint for conversations (expected). Using campaign→leads→conversation flow."
    )
    return []


def _looks_like_conversation_list(items: list[dict[str, Any]]) -> bool:
    """True if items look like conversation objects (have message/lead/reply etc), not e.g. campaign list."""
    if not items:
        return False
    first = items[0] if isinstance(items[0], dict) else {}
    conversation_keys = ("lastMessage", "last_message", "message", "replyText", "reply_text", "lead", "messages", "conversation_id", "conversationId", "thread_id")
    return any(first.get(k) is not None for k in conversation_keys)


def _parse_conversations_response(data: dict[str, Any] | list) -> list[dict[str, Any]]:
    """Extract list from API response."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("conversations", "items", "results", "threads", "messages", "data", "list", "lists"):
            val = data.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                for inner in ("conversations", "items", "results", "threads", "messages", "data"):
                    if isinstance(val.get(inner), list):
                        return val[inner]
    return []


def normalize_conversation_to_signal(conv: dict[str, Any]) -> Signal:
    """Map one Prosp conversation to normalized interest signal."""
    cid = (
        conv.get("id")
        or conv.get("conversation_id")
        or conv.get("conversationId")
        or conv.get("thread_id")
        or str(hash(str(conv)))
    )
    signal_id = f"prosp:{cid}"

    last_msg = conv.get("last_message") or conv.get("lastMessage") or conv.get("message") or conv.get("body") or {}
    if isinstance(last_msg, dict):
        msg_text = last_msg.get("text") or last_msg.get("content") or last_msg.get("body") or ""
    else:
        msg_text = str(last_msg)

    lead = conv.get("lead") or conv.get("sender") or conv.get("from") or {}
    if isinstance(lead, dict):
        lead_name = (lead.get("name") or "").strip() or (
            (lead.get("first_name") or "") + " " + (lead.get("last_name") or "")
        ).strip()
        company = lead.get("company") or lead.get("company_name") or ""
    else:
        lead_name = (conv.get("lead_name") or conv.get("from_name") or "").strip()
        company = conv.get("company") or conv.get("company_name") or ""

    campaign = conv.get("campaign_name") or conv.get("campaignName") or conv.get("campaign") or conv.get("sequence") or ""
    timestamp = conv.get("updated_at") or conv.get("updatedAt") or conv.get("created_at") or conv.get("createdAt") or ""

    return {
        "id": signal_id,
        "channel": "linkedin",
        "leadName": lead_name or "Unknown",
        "company": company or "",
        "campaignOrSequence": campaign or "",
        "replyText": (msg_text or conv.get("message") or "")[:5000],
        "timestamp": timestamp or "",
        "raw": conv,
    }


def _looks_like_message_dict(d: dict[str, Any]) -> bool:
    """True if dict plausibly represents one chat message."""
    if not isinstance(d, dict):
        return False
    text_keys = (
        "content", "text", "body", "message", "value", "snippet", "msg",
        "content_text", "message_text", "plain_text", "message_body",
    )
    if any(d.get(k) not in (None, "") for k in text_keys):
        return True
    nested = d.get("message") or d.get("content")
    if isinstance(nested, dict):
        return any(nested.get(k) not in (None, "") for k in ("text", "body", "content"))
    if isinstance(nested, str) and nested.strip():
        return True
    meta_keys = ("from_me", "is_from_me", "direction", "sender", "sender_type", "role", "created_at", "timestamp")
    return any(k in d for k in meta_keys)


def _looks_like_message_list(items: list[Any]) -> bool:
    """True if list looks like chat messages (majority dicts with message-like fields)."""
    if not items or not isinstance(items, list):
        return False
    dicts = [x for x in items if isinstance(x, dict)]
    if not dicts:
        return False
    sample = dicts[: min(5, len(dicts))]
    ok = sum(1 for d in sample if _looks_like_message_dict(d))
    return ok >= max(1, len(sample) // 2) or (len(sample) == 1 and ok == 1)


def _deep_find_message_lists(obj: Any, depth: int = 0, max_depth: int = 6) -> list[list[dict[str, Any]]]:
    """Find nested lists of message-like dicts (Prosp response shapes vary)."""
    found: list[list[dict[str, Any]]] = []
    if depth > max_depth or obj is None:
        return found
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj) and _looks_like_message_list(obj):
            found.append(obj)  # type: ignore[list-item]
        else:
            for item in obj:
                found.extend(_deep_find_message_lists(item, depth + 1, max_depth))
    elif isinstance(obj, dict):
        for val in obj.values():
            found.extend(_deep_find_message_lists(val, depth + 1, max_depth))
    return found


def _extract_messages_from_conversation(raw: dict[str, Any] | list[Any] | None) -> list[dict[str, Any]]:
    """Try to get messages array from leads/conversation API response (shape may vary)."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw if _looks_like_message_list(raw) else []
    if not isinstance(raw, dict):
        return []
    # Top-level keys (and camelCase variants) that might hold the message list
    candidates = [
        "messages", "data", "conversation", "thread", "thread_messages",
        "conversation_messages", "items", "results", "chat_messages",
        "messageList", "message_list", "conversationMessages",
        "history", "chat_history", "chatHistory", "dm_messages", "direct_messages",
    ]
    for key in candidates:
        val = raw.get(key)
        if isinstance(val, list):
            if _looks_like_message_list(val):
                return val
            continue
        if isinstance(val, dict):
            for inner_key in ("messages", "data", "items", "results", "thread", "conversation", "history"):
                inner = val.get(inner_key)
                if isinstance(inner, list) and _looks_like_message_list(inner):
                    return inner
            # Single nested object that is itself one message
            if _looks_like_message_dict(val):
                return [val]
    # Last resort: shallow walk
    for val in raw.values():
        if isinstance(val, list) and _looks_like_message_list(val):
            return val
        if isinstance(val, dict):
            for inner in (val.get("messages"), val.get("data"), val.get("items")):
                if isinstance(inner, list) and _looks_like_message_list(inner):
                    return inner
    # Deep walk: pick longest plausible message list
    deep = _deep_find_message_lists(raw)
    if deep:
        deep.sort(key=len, reverse=True)
        return deep[0]
    return []


def _normalize_message_for_display(msg: dict[str, Any]) -> dict[str, Any]:
    """Extract content, sender label, and timestamp from a raw message for UI display."""
    nested = msg.get("message") or msg.get("content")
    content = (
        msg.get("content")
        or msg.get("text")
        or msg.get("body")
        or msg.get("message")
        or msg.get("snippet")
        or msg.get("msg")
        or msg.get("content_text")
        or msg.get("message_text")
        or msg.get("value")
        or msg.get("plain_text")
        or ""
    )
    if content is None:
        content = ""
    if isinstance(content, dict):
        content = content.get("text") or content.get("body") or content.get("content") or str(content)
    if isinstance(nested, dict) and not str(content).strip():
        content = nested.get("text") or nested.get("body") or nested.get("content") or ""
    if isinstance(nested, str) and not str(content).strip():
        content = nested
    created = (
        msg.get("created_at")
        or msg.get("timestamp")
        or msg.get("date")
        or msg.get("sent_at")
        or msg.get("createdAt")
        or msg.get("updated_at")
        or ""
    )
    from_me = msg.get("from_me") if isinstance(msg.get("from_me"), bool) else None
    if from_me is None:
        st = str(msg.get("sender_type") or msg.get("role") or "").lower()
        if st in ("user", "me", "self", "outbound", "sender"):
            from_me = True
        elif st in ("lead", "recipient", "inbound", "contact"):
            from_me = False
    if from_me is None:
        dir_ = str(msg.get("direction") or "").lower()
        if dir_ in ("inbound", "incoming", "received"):
            from_me = False
        elif dir_ in ("outbound", "outgoing", "sent"):
            from_me = True
    if from_me is None:
        from_me = (
            msg.get("sender") == "me"
            or msg.get("is_from_me") is True
            or msg.get("is_outgoing") is True
        )
    return {"content": str(content)[:5000], "from_me": bool(from_me), "created_at": str(created)}


def _fetch_lead_with_conversation(lead: dict[str, Any]) -> dict[str, Any]:
    """Fetch one lead's conversation; used for parallel execution."""
    name = lead.get("name") or lead.get("full_name") or "Unknown"
    linkedin_url = lead.get("linkedinUrl") or lead.get("linkedin_url") or lead.get("url") or ""
    conv = fetch_conversation_for_lead(linkedin_url) if linkedin_url else None
    messages_raw = _extract_messages_from_conversation(conv) if conv else []
    if conv and not messages_raw and isinstance(conv, dict):
        logger.debug(
            "Prosp conversation returned but no messages extracted for %s. Top-level keys: %s",
            (linkedin_url or "")[:50],
            list(conv.keys()) if isinstance(conv, dict) else [],
        )
    messages = [_normalize_message_for_display(m) for m in messages_raw if isinstance(m, dict)]
    return {
        "name": name,
        "linkedin_url": linkedin_url,
        "company": lead.get("company") or lead.get("company_name") or "",
        "messages": messages,
        "messages_count": len(messages),
    }


def get_campaign_leads_with_messages(
    campaign_id: str,
    max_leads: int = 25,
    max_workers: int = 8,
) -> dict[str, Any]:
    """
    Fetch leads for a campaign and each lead's conversation messages.
    Uses parallel requests (max_workers) so many conversations load at once.
    Returns structure for dashboard: campaign_id, campaign_name, leads with messages array.
    """
    if not PROSP_API_KEY or not PROSP_SENDER:
        return {"error": "PROSP_API_KEY or PROSP_SENDER not set", "campaign_id": campaign_id, "leads": []}
    campaigns = fetch_campaigns()
    campaign = next((c for c in campaigns if (c.get("campaign_id") or c.get("campaignId")) == campaign_id), None)
    if not campaign:
        return {"error": "Campaign not found", "campaign_id": campaign_id, "leads": []}
    cname = campaign.get("campaign_name") or campaign.get("campaignName") or campaign.get("name") or ""
    leads_raw = fetch_leads_for_campaign(campaign_id)
    batch = leads_raw[:max_leads]
    leads_out: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(batch) or 1)) as executor:
        futures = {executor.submit(_fetch_lead_with_conversation, lead): lead for lead in batch}
        for future in as_completed(futures):
            try:
                leads_out.append(future.result())
            except Exception as e:
                logger.warning("Campaign lead conversation fetch failed: %s", e)
                lead = futures[future]
                leads_out.append({
                    "name": lead.get("name") or lead.get("full_name") or "Unknown",
                    "linkedin_url": lead.get("linkedinUrl") or lead.get("linkedin_url") or "",
                    "company": lead.get("company") or lead.get("company_name") or "",
                    "messages": [],
                    "messages_count": 0,
                })
    return {
        "campaign_id": campaign_id,
        "campaign_name": cname,
        "leads_count": len(leads_raw),
        "leads": leads_out,
    }


def pull_campaign_conversations(
    campaign_id: str | None = None,
    max_leads: int = 10,
) -> dict[str, Any]:
    """
    Test helper: for a campaign, fetch leads then each lead's conversation.
    Use after creating a reply in LinkedIn to see if we can pull it via API.
    Returns campaign_id, campaign_name, leads, and for each lead the raw conversation + parsed messages preview.
    """
    if not PROSP_API_KEY:
        return {"error": "PROSP_API_KEY not set", "campaign_id": campaign_id}
    campaigns = fetch_campaigns()
    if not campaigns:
        return {"error": "No campaigns returned from Prosp", "campaign_id": campaign_id}
    if campaign_id:
        campaign = next((c for c in campaigns if c.get("campaign_id") == campaign_id), campaigns[0])
    else:
        campaign = campaigns[0]
    cid = campaign.get("campaign_id") or campaign_id
    cname = campaign.get("campaign_name") or ""
    leads = fetch_leads_for_campaign(cid)
    if not leads:
        return {
            "campaign_id": cid,
            "campaign_name": cname,
            "leads_count": 0,
            "leads": [],
            "note": "No leads in this campaign or API returned empty.",
        }
    results: list[dict[str, Any]] = []
    for i, lead in enumerate(leads[:max_leads]):
        name = lead.get("name") or lead.get("full_name") or "Unknown"
        linkedin_url = lead.get("linkedinUrl") or lead.get("linkedin_url") or lead.get("url") or ""
        if not linkedin_url:
            results.append({"name": name, "linkedin_url": "", "conversation": None, "error": "No linkedin_url"})
            continue
        # First lead: return debug info so we can see why conversation might be null
        if i == 0:
            conv, status_code, response_preview = fetch_conversation_for_lead_debug(linkedin_url)
            messages = _extract_messages_from_conversation(conv) if conv else []
            last_msg = messages[-1] if messages else None
            last_text = ""
            if isinstance(last_msg, dict):
                last_text = last_msg.get("content") or last_msg.get("text") or last_msg.get("body") or str(last_msg)[:200]
            results.append({
                "name": name,
                "linkedin_url": linkedin_url[:80] + "..." if len(linkedin_url) > 80 else linkedin_url,
                "conversation_keys": list(conv.keys()) if isinstance(conv, dict) else [],
                "messages_count": len(messages),
                "last_message_preview": last_text[:300] if last_text else None,
                "conversation": conv,
                "conversation_status_code": status_code,
                "conversation_response_preview": response_preview[:400] if response_preview else None,
            })
        else:
            conv = fetch_conversation_for_lead(linkedin_url)
            messages = _extract_messages_from_conversation(conv) if conv else []
            last_msg = messages[-1] if messages else None
            last_text = ""
            if isinstance(last_msg, dict):
                last_text = last_msg.get("content") or last_msg.get("text") or last_msg.get("body") or str(last_msg)[:200]
            results.append({
                "name": name,
                "linkedin_url": linkedin_url[:80] + "..." if len(linkedin_url) > 80 else linkedin_url,
                "conversation_keys": list(conv.keys()) if isinstance(conv, dict) else [],
                "messages_count": len(messages),
                "last_message_preview": last_text[:300] if last_text else None,
                "conversation": conv,
            })
    return {
        "campaign_id": cid,
        "campaign_name": cname,
        "leads_count": len(leads),
        "pulled": len(results),
        "leads": results,
    }


def _conversation_response_to_signal(
    conv: dict[str, Any],
    lead: dict[str, Any],
    campaign_id: str,
    campaign_name: str,
) -> Signal | None:
    """Build a normalized signal from leads/conversation API response + lead/campaign context."""
    messages = _extract_messages_from_conversation(conv)
    if not messages:
        return None
    last_msg = messages[-1]
    if not isinstance(last_msg, dict):
        return None
    msg_text = last_msg.get("content") or last_msg.get("text") or last_msg.get("body") or str(last_msg)
    if not msg_text:
        return None
    name = lead.get("name") or lead.get("full_name") or "Unknown"
    linkedin_url = lead.get("linkedinUrl") or lead.get("linkedin_url") or lead.get("url") or ""
    signal_id = f"prosp:{campaign_id}:{hash(linkedin_url) & 0x7FFFFFFF}"
    raw = dict(conv) if isinstance(conv, dict) else {}
    raw["linkedin_url"] = linkedin_url
    return {
        "id": signal_id,
        "channel": "linkedin",
        "leadName": name,
        "company": lead.get("company") or lead.get("company_name") or "",
        "campaignOrSequence": campaign_name,
        "replyText": msg_text[:5000],
        "timestamp": last_msg.get("created_at") or last_msg.get("timestamp") or "",
        "raw": raw,
    }


def get_prosp_signals_via_campaigns(
    max_campaigns: int | None = None,
    max_leads_per_campaign: int | None = None,
) -> list[Signal]:
    """
    Pull LinkedIn messages from Prosp and return normalized signals (same shape as Instantly).
    Used by run_cycle() so LinkedIn replies appear in the same leads list as email.

    Prosp API used:
    - POST api/v1/campaigns/lists  → campaign list
    - POST api/v1/campaigns/leads  → leads per campaign (body: campaign_id)
    - POST api/v1/leads/conversation → messages per lead (body: linkedin_url, sender)

    Uses PROSP_MAX_CAMPAIGNS (0 = all) and PROSP_MAX_LEADS_PER_CAMPAIGN from config when args are None.
    Requires PROSP_SENDER (your LinkedIn profile URL) or the conversation API returns 400.
    """
    if not PROSP_API_KEY:
        return []
    if not PROSP_SENDER:
        logger.warning(
            "Prosp: PROSP_SENDER not set. Conversation API requires a valid sender LinkedIn URL; "
            "no LinkedIn signals will be pulled. Set PROSP_SENDER in .env (e.g. https://www.linkedin.com/in/yourprofile)."
        )
        return []
    campaigns = fetch_campaigns()
    if not campaigns:
        return []
    cap_campaigns = max_campaigns if max_campaigns is not None else (PROSP_MAX_CAMPAIGNS or None)
    cap_leads = max_leads_per_campaign if max_leads_per_campaign is not None else PROSP_MAX_LEADS_PER_CAMPAIGN
    campaign_list = campaigns if (cap_campaigns is None or cap_campaigns <= 0) else campaigns[:cap_campaigns]
    signals: list[Signal] = []
    for campaign in campaign_list:
        cid = campaign.get("campaign_id") or ""
        cname = campaign.get("campaign_name") or ""
        leads = fetch_leads_for_campaign(cid)
        lead_list = leads if (cap_leads is None or cap_leads <= 0) else leads[:cap_leads]
        for lead in lead_list:
            linkedin_url = lead.get("linkedinUrl") or lead.get("linkedin_url") or lead.get("url") or ""
            if not linkedin_url:
                continue
            conv = fetch_conversation_for_lead(linkedin_url)
            if not conv:
                continue
            sig = _conversation_response_to_signal(conv, lead, cid, cname)
            if sig:
                signals.append(sig)
    return signals


def get_unread_signals() -> list[Signal]:
    """Fetch Prosp conversations and return normalized signals."""
    convs = fetch_unread_conversations()
    return [normalize_conversation_to_signal(c) for c in convs]
