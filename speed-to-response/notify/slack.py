"""
Post lead alert to Slack with context and suggested reply draft.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from config import SLACK_ACCESS_TOKEN, SLACK_BOT_TOKEN, SLACK_CHANNEL_ID

# Prefer bot token for chat.postMessage (has chat:write when scope is added)
SLACK_TOKEN = SLACK_BOT_TOKEN or SLACK_ACCESS_TOKEN

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api"


def list_channels() -> tuple[list[dict[str, Any]], str | None]:
    """
    List public channels the bot can see. Requires Bot scope channels:read.
    Returns (list of {id, name}, error_message if failed).
    """
    if not SLACK_TOKEN:
        return [], "No Slack token"
    try:
        r = requests.get(
            f"{SLACK_API}/conversations.list",
            headers={"Authorization": f"Bearer {SLACK_TOKEN}"},
            params={"types": "public_channel", "limit": 100},
            timeout=10,
        )
        data = r.json()
        if not data.get("ok"):
            err = data.get("error", "unknown")
            logger.warning("conversations.list failed: %s", err)
            if err == "missing_scope":
                return [], "Add Bot scope 'channels:read' in Slack app → OAuth & Permissions, then reinstall."
            return [], str(err)
        return [{"id": c["id"], "name": c.get("name", "")} for c in data.get("channels", [])], None
    except requests.RequestException as e:
        logger.warning("list_channels failed: %s", e)
        return [], str(e)


def build_message(signal: dict[str, Any], suggested_response: str) -> dict[str, Any]:
    """Build Slack block payload for a lead alert."""
    lead_name = signal.get("leadName") or "Unknown"
    company = signal.get("company") or "—"
    campaign = signal.get("campaignOrSequence") or "—"
    channel_label = "Email" if signal.get("channel") == "email" else "LinkedIn"
    reply_excerpt = (signal.get("replyText") or "")[:300]
    if len(signal.get("replyText") or "") > 300:
        reply_excerpt += "…"

    return {
        "channel": SLACK_CHANNEL_ID,
        "text": f"Lead reply: {lead_name} ({company}) — {channel_label}",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "New lead reply", "emoji": True},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Lead:*\n{lead_name}"},
                    {"type": "mrkdwn", "text": f"*Company:*\n{company}"},
                    {"type": "mrkdwn", "text": f"*Campaign:*\n{campaign}"},
                    {"type": "mrkdwn", "text": f"*Channel:*\n{channel_label}"},
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Their reply:*\n```{reply_excerpt}```"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Suggested response:*\n{suggested_response}",
                },
            },
        ],
    }


def send_csv_to_slack(csv_content: str, filename: str = "leads_export.csv") -> bool:
    """
    Upload CSV content as a file to the configured Slack channel.
    Uses legacy files.upload API (deprecated but still available for existing apps).
    Returns True on success.
    Bot token needs scope files:write. Add in Slack app → OAuth & Permissions → Scopes → Bot Token.
    """
    if not SLACK_TOKEN or not SLACK_CHANNEL_ID:
        logger.warning("Slack not configured (SLACK_BOT_TOKEN or SLACK_ACCESS_TOKEN and SLACK_CHANNEL_ID missing)")
        return False
    url = f"{SLACK_API}/files.upload"
    try:
        r = requests.post(
            url,
            data={
                "channels": SLACK_CHANNEL_ID,
                "content": csv_content,
                "filename": filename,
                "title": filename,
            },
            headers={"Authorization": f"Bearer {SLACK_TOKEN}"},
            timeout=30,
        )
        if not r.ok:
            logger.error("Slack files.upload failed: %s %s", r.status_code, (r.text or "")[:500])
            return False
        resp = r.json()
        if not resp.get("ok"):
            err = resp.get("error", "unknown")
            logger.error("Slack files.upload API error: %s", err)
            if err == "not_in_channel":
                logger.error(
                    "Bot must be in the channel to upload files. In Slack, type: /invite @YourBotName"
                )
            return False
        return True
    except requests.RequestException as e:
        logger.error("Slack files.upload request failed: %s", e)
        return False


def send_alert(signal: dict[str, Any], suggested_response: str) -> bool:
    """
    Post to Slack. Returns True on success. Logs and returns False on failure.
    """
    if not SLACK_TOKEN or not SLACK_CHANNEL_ID:
        logger.warning("Slack not configured (SLACK_BOT_TOKEN or SLACK_ACCESS_TOKEN and SLACK_CHANNEL_ID missing)")
        return False
    payload = build_message(signal, suggested_response)
    url = f"{SLACK_API}/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {SLACK_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if not r.ok:
            logger.error(
                "Slack post failed: %s %s",
                r.status_code,
                r.text[:500],
                extra={"context": {"source": "slack", "status": r.status_code}},
            )
            return False
        data = r.json()
        if not data.get("ok"):
            err = data.get("error", "unknown")
            logger.error("Slack API error: %s", err)
            if err == "missing_scope":
                logger.error(
                    "Slack token needs chat:write. In Slack app settings: OAuth & Permissions → "
                    "Scopes → Bot/User Token → add chat:write, then reinstall to workspace."
                )
            elif err == "channel_not_found":
                cid = (SLACK_CHANNEL_ID or "").strip()
                logger.error(
                    "channel_not_found. Using SLACK_CHANNEL_ID=%r (len=%s). "
                    "Bot must be in the channel (invite it) or add scope chat:write.public and reinstall.",
                    cid,
                    len(cid),
                )
            return False
        return True
    except requests.RequestException as e:
        logger.error("Slack request failed: %s", e)
        return False
