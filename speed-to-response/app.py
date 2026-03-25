"""
Flask app: health check, optional POST /run-cycle for cron, background scheduler.
"""
from __future__ import annotations

import csv
import io
import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, Response, jsonify, request

from config import INSTANTLY_REPLY_FROM_EMAIL, is_our_sending_address, SLACK_CHANNEL_ID


def _enrich_email_lead_for_reply(lead: dict) -> dict:
    """Fill missing Instantly reply fields: infer reply_to_uuid from id, default from_email, copy email from lead_name."""
    out = dict(lead)
    if (out.get("channel") or "").lower() != "email":
        return out
    lid = str(out.get("id") or "")
    if not (out.get("reply_to_uuid") or "").strip() and lid.startswith("instantly:"):
        suffix = lid.split(":", 1)[1].strip()
        if suffix:
            out["reply_to_uuid"] = suffix
    if not (out.get("from_email") or "").strip():
        fe = (INSTANTLY_REPLY_FROM_EMAIL or "").strip()
        if fe:
            out["from_email"] = fe
    if not (out.get("email") or "").strip():
        ln = (out.get("lead_name") or "").strip()
        if "@" in ln and not is_our_sending_address(ln):
            out["email"] = ln
    return out


def _filter_excluded_senders(records: list[dict]) -> list[dict]:
    """Drop any lead whose sender (lead_name and/or email) is our mailbox / org domain."""
    out = []
    for r in records:
        ln = (r.get("lead_name") or "").strip()
        em = (r.get("email") or "").strip()
        if ln and is_our_sending_address(ln):
            continue
        if em and is_our_sending_address(em):
            continue
        out.append(r)
    return out


def _cors_response(resp: Response) -> Response:
    """Allow dashboard (and other origins) to call the API."""
    origin = request.headers.get("Origin", "*")
    resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp
from run_cycle import run_cycle
from suggest_reply import suggest_reply
from notify.slack import list_channels as slack_list_channels
from notify.slack import send_alert as send_slack_alert
from notify.slack import send_csv_to_slack

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.after_request(_cors_response)

scheduler: BackgroundScheduler | None = None


@app.route("/", methods=["OPTIONS"])
def _cors_preflight_root() -> tuple[dict, int]:
    """Respond to CORS preflight for root."""
    return {}, 204


@app.route("/", methods=["GET"])
def index() -> tuple[dict, int]:
    """List available endpoints so you can confirm this app is the one running."""
    return jsonify({
        "app": "speed-to-response",
        "endpoints": {
            "health": "/health",
            "test_slack": "/test-slack",
            "run_cycle": "/run-cycle",
            "slack_channels": "/slack-channels",
            "sources": "/sources",
            "sources_debug": "/sources/debug",
            "campaigns": "/campaigns (GET — all Prosp campaigns from api/v1/campaigns/lists)",
            "prosp_generate_reply": "/prosp/generate-reply (POST — AI LinkedIn reply using thread messages)",
            "inbox_email": "/inbox/email (GET — all email messages from all inboxes)",
            "inbox_linkedin": "/inbox/linkedin (GET — LinkedIn messages only)",
            "leads": "/leads (GET, JSON; ?format=csv for CSV)",
            "leads_export": "/leads/export (GET, CSV download; ?send_to_slack=1 to also upload to Slack)",
            "leads_export_to_slack": "/leads/export-to-slack (POST or GET, upload CSV to Slack)",
            "test_email": "/test-email (POST, run cycle + return counts for email/LinkedIn test)",
            "test_prosp_pull": "/test-prosp-pull (GET, ?campaign_id=xxx — pull leads + conversations for a Prosp campaign)",
            "test_prosp_to_slack": "/test-prosp-to-slack (POST or GET — send first Prosp reply + suggested reply to Slack)",
            "linkedin_engager": "/linkedin-engager (POST — generate custom email for LinkedIn engager: liked_post, viewed_profile, connected)",
            "uno_reverse": "/uno-reverse (POST — generate content-driven outreach for list of engagers; optional add_to_instantly)",
        },
    }), 200


@app.route("/slack-channels", methods=["GET"])
def slack_channels() -> tuple[dict, int]:
    """List public channels the bot can see. Add scope channels:read if list is empty."""
    channels, list_error = slack_list_channels()
    body = {
        "current_slack_channel_id": SLACK_CHANNEL_ID,
        "channels": channels,
        "hint": "Use one of the channel 'id' values as SLACK_CHANNEL_ID. For channel_not_found: add scope chat:write.public and reinstall.",
    }
    if list_error:
        body["channels_error"] = list_error
    return jsonify(body), 200


@app.route("/sources", methods=["GET"])
def sources() -> tuple[dict, int]:
    """Fetch from Instantly and LinkedIn (Prosp); return counts (no classify/notify). Use to verify connections."""
    try:
        from config import PROSP_API_KEY
        from poll.instantly import get_unread_signals as get_instantly
        from poll.prosp import get_unread_signals as get_prosp
        instantly = get_instantly(limit=50)
        if PROSP_API_KEY:
            linkedin = get_prosp()
            linkedin_label = "prosp"
        else:
            linkedin = []
            linkedin_label = "prosp"
        return jsonify({
            "instantly": {"count": len(instantly), "signals": [{"id": s.get("id"), "leadName": s.get("leadName")} for s in instantly[:5]]},
            linkedin_label: {"count": len(linkedin), "signals": [{"id": s.get("id"), "leadName": s.get("leadName")} for s in linkedin[:5]]},
            "total": len(instantly) + len(linkedin),
        }), 200
    except Exception as e:
        logger.exception("sources fetch failed: %s", e)
        return jsonify({"error": "SOURCES_FAILED", "message": str(e)}), 500


@app.route("/campaigns", methods=["GET"])
def campaigns() -> tuple[dict, int]:
    """Return all Prosp campaigns from api/v1/campaigns/lists. Requires PROSP_API_KEY."""
    try:
        from config import PROSP_API_KEY
        from poll.prosp import fetch_campaigns
        if not PROSP_API_KEY:
            return jsonify({"campaigns": [], "error": "PROSP_API_KEY not set"}), 200
        raw = fetch_campaigns()
        # Normalize to stable keys (Prosp may return campaign_id/campaign_name or camelCase)
        campaigns_list = [
            {
                "campaign_id": c.get("campaign_id") or c.get("campaignId") or "",
                "campaign_name": c.get("campaign_name") or c.get("campaignName") or c.get("name") or "—",
            }
            for c in (raw or [])
        ]
        return jsonify({"campaigns": campaigns_list, "count": len(campaigns_list)}), 200
    except Exception as e:
        logger.exception("campaigns fetch failed: %s", e)
        return jsonify({"error": "CAMPAIGNS_FAILED", "message": str(e)}), 500


@app.route("/campaigns/<campaign_id>/leads", methods=["GET", "OPTIONS"])
def campaign_leads(campaign_id: str) -> tuple[dict, int] | tuple[Response, int]:
    """Return leads for a campaign with their conversation messages (Prosp api/v1/campaigns/leads + leads/conversation)."""
    if request.method == "OPTIONS":
        return _cors_response(Response(status=204)), 204
    try:
        from poll.prosp import get_campaign_leads_with_messages
        max_leads = min(int(request.args.get("max_leads", "25") or "25"), 100)
        out = get_campaign_leads_with_messages(campaign_id, max_leads=max_leads)
        if out.get("error"):
            err = str(out.get("error", ""))
            out["message"] = err
            status = 400 if "not set" in err or "not found" in err else 200
            return jsonify(out), status
        return jsonify(out), 200
    except Exception as e:
        logger.exception("campaign_leads failed: %s", e)
        return jsonify({"error": "CAMPAIGN_LEADS_FAILED", "message": str(e)}), 500


@app.route("/linkedin/threads", methods=["GET", "OPTIONS"])
def linkedin_threads() -> tuple[dict, int] | tuple[Response, int]:
    """Return a flattened list of leads + full conversation messages across active Prosp campaigns."""
    if request.method == "OPTIONS":
        return _cors_response(Response(status=204)), 204
    try:
        logger.info(
            "linkedin_threads GET args: max_campaigns=%s max_leads_per_campaign=%s include_no_messages=%s",
            request.args.get("max_campaigns", ""),
            request.args.get("max_leads_per_campaign", ""),
            request.args.get("include_no_messages", ""),
        )
        from poll.prosp import get_active_campaign_threads_with_messages

        max_campaigns = request.args.get("max_campaigns", "").strip()
        max_leads_per_campaign = request.args.get("max_leads_per_campaign", "").strip()
        include_no_messages = request.args.get("include_no_messages", "").strip().lower() in ("1", "true", "yes")

        max_campaigns_val = int(max_campaigns) if max_campaigns else None
        max_leads_val = int(max_leads_per_campaign) if max_leads_per_campaign else None

        out = get_active_campaign_threads_with_messages(
            max_campaigns=max_campaigns_val,
            max_leads_per_campaign=max_leads_val,
            include_no_messages=include_no_messages,
        )
        if out.get("error"):
            logger.warning("linkedin_threads error: %s", out.get("error"))
            return jsonify(out), 400
        logger.info("linkedin_threads success: campaigns_loaded=%s count=%s", out.get("campaigns_loaded"), out.get("count"))
        return jsonify(out), 200
    except Exception as e:
        logger.exception("linkedin_threads failed: %s", e)
        return jsonify({"error": "LINKEDIN_THREADS_FAILED", "message": str(e)}), 500


@app.route("/prosp/generate-message", methods=["POST"])
def prosp_generate_message() -> tuple[dict, int]:
    """Generate a LinkedIn message for one lead. Body: { \"name\": \"...\", \"context\": \"\" }. Returns message starting with Hello (name)."""
    try:
        from suggest_reply import generate_linkedin_message
        data = request.get_json() or {}
        name = (data.get("name") or "").strip() or "there"
        context = (data.get("context") or "").strip()
        message = generate_linkedin_message(name, context)
        return jsonify({"message": message}), 200
    except Exception as e:
        logger.exception("prosp_generate_message failed: %s", e)
        return jsonify({"error": "GENERATE_FAILED", "message": str(e)}), 500


@app.route("/prosp/generate-reply", methods=["POST"])
def prosp_generate_reply() -> tuple[dict, int]:
    """
    Generate a LinkedIn follow-up using thread context (like email suggested reply).
    Body: { \"name\", \"campaign_name\"?, \"messages\": [{ \"content\", \"from_me\" }], \"thread_context\"? }.
    """
    try:
        from suggest_reply import format_prosp_thread_for_prompt, generate_linkedin_message
        data = request.get_json() or {}
        name = (data.get("name") or "").strip() or "there"
        campaign = (data.get("campaign_name") or data.get("context") or "").strip()
        thread_raw = (data.get("thread_context") or "").strip()
        messages = data.get("messages")
        if not thread_raw and isinstance(messages, list):
            thread_raw = format_prosp_thread_for_prompt(messages)
        message = generate_linkedin_message(name, campaign, thread_context=thread_raw)
        return jsonify({"message": message}), 200
    except Exception as e:
        logger.exception("prosp_generate_reply failed: %s", e)
        return jsonify({"error": "GENERATE_FAILED", "message": str(e)}), 500


@app.route("/prosp/send-message", methods=["POST"])
def prosp_send_message() -> tuple[dict, int]:
    """Send a LinkedIn message via Prosp. Body: { \"linkedin_url\": \"...\", \"message\": \"...\" }."""
    try:
        from actions.prosp_reply import send_prosp_message
        data = request.get_json() or {}
        linkedin_url = (data.get("linkedin_url") or "").strip()
        message = (data.get("message") or "").strip()
        if not linkedin_url or not message:
            return jsonify({"error": "MISSING_FIELDS", "message": "linkedin_url and message required"}), 400
        ok, err_msg = send_prosp_message(linkedin_url, message)
        if ok:
            return jsonify({"status": "ok", "message": "Message sent"}), 200
        return jsonify({
            "error": "SEND_FAILED",
            "message": err_msg or "Prosp API returned failure",
        }), 502
    except Exception as e:
        logger.exception("prosp_send_message failed: %s", e)
        return jsonify({"error": "SEND_FAILED", "message": str(e)}), 500


@app.route("/campaigns/<campaign_id>/generate-bulk-message", methods=["POST"])
def campaign_generate_bulk_message(campaign_id: str) -> tuple[dict, int]:
    """Generate a bulk LinkedIn message template. Body: { \"campaign_description\": \"\" }. Returns template with {name} placeholder."""
    try:
        from poll.prosp import fetch_campaigns, fetch_leads_for_campaign
        from suggest_reply import generate_linkedin_bulk_template
        campaigns = fetch_campaigns()
        campaign = next((c for c in campaigns if (c.get("campaign_id") or c.get("campaignId")) == campaign_id), None)
        if not campaign:
            return jsonify({"error": "Campaign not found", "campaign_id": campaign_id}), 404
        cname = campaign.get("campaign_name") or campaign.get("campaignName") or campaign.get("name") or ""
        data = request.get_json() or {}
        campaign_description = (data.get("campaign_description") or "").strip()
        message_template = generate_linkedin_bulk_template(cname, campaign_description)
        return jsonify({"message_template": message_template, "campaign_name": cname}), 200
    except Exception as e:
        logger.exception("campaign_generate_bulk_message failed: %s", e)
        return jsonify({"error": "GENERATE_FAILED", "message": str(e)}), 500


def _lead_first_name(lead: dict) -> str:
    """First name for greeting from lead dict."""
    name = lead.get("name") or lead.get("full_name") or ""
    if not name or not str(name).strip():
        return "there"
    return str(name).strip().split()[0]


@app.route("/campaigns/<campaign_id>/send-bulk", methods=["POST"])
def campaign_send_bulk(campaign_id: str) -> tuple[dict, int]:
    """Send a message to all leads in a campaign. Body: { \"message_template\": \"Hello {name}, ...\" }. Replaces {name} with each lead's first name."""
    try:
        from actions.prosp_reply import send_prosp_message
        from poll.prosp import fetch_leads_for_campaign
        data = request.get_json() or {}
        message_template = (data.get("message_template") or data.get("message") or "").strip()
        if not message_template:
            return jsonify({"error": "MISSING_TEMPLATE", "message": "message_template required (use {name} for first name)"}), 400
        leads = fetch_leads_for_campaign(campaign_id)
        sent, failed, results = 0, 0, []
        for lead in leads:
            linkedin_url = lead.get("linkedinUrl") or lead.get("linkedin_url") or lead.get("url") or ""
            if not linkedin_url:
                failed += 1
                results.append({"name": lead.get("name"), "status": "skipped", "reason": "no linkedin_url"})
                continue
            first = _lead_first_name(lead)
            body = message_template.replace("{name}", first).replace("{ name }", first)
            ok, _ = send_prosp_message(linkedin_url, body)
            if ok:
                sent += 1
                results.append({"name": lead.get("name"), "status": "sent"})
            else:
                failed += 1
                results.append({"name": lead.get("name"), "status": "failed"})
        return jsonify({"sent": sent, "failed": failed, "total": len(leads), "results": results}), 200
    except Exception as e:
        logger.exception("campaign_send_bulk failed: %s", e)
        return jsonify({"error": "SEND_BULK_FAILED", "message": str(e)}), 500


@app.route("/sources/debug", methods=["GET"])
def sources_debug() -> tuple[dict, int]:
    """Raw API probe: Instantly and Prosp status + response peek (for path/parsing fixes)."""
    import requests
    from config import (
        INSTANTLY_API_KEY,
        INSTANTLY_BASE_URL,
        PROSP_API_KEY,
        PROSP_API_BASE,
    )
    out = {}
    if INSTANTLY_API_KEY:
        try:
            r = requests.get(
                f"{INSTANTLY_BASE_URL}/emails",
                params={"is_read": "false", "limit": 5},
                headers={"Authorization": f"Bearer {INSTANTLY_API_KEY}", "Content-Type": "application/json"},
                timeout=15,
            )
            data = r.json() if r.ok else None
            out["instantly"] = {
                "status_code": r.status_code,
                "response_type": type(data).__name__ if data is not None else None,
                "top_level_keys": list(data.keys())[:15] if isinstance(data, dict) else None,
                "list_length": len(data) if isinstance(data, list) else None,
                "first_item_keys": list(data[0].keys())[:20] if isinstance(data, list) and len(data) else None,
            }
        except Exception as e:
            out["instantly"] = {"error": str(e)}
    else:
        out["instantly"] = {"error": "INSTANTLY_API_KEY not set"}
    if PROSP_API_KEY:
        # Prosp API probe (doc: https://prosp.apidocumentation.com/combined-api)
        base = PROSP_API_BASE.rstrip("/")
        prosp_attempts = []
        prosp_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": PROSP_API_KEY,
        }
        for method, path, kw in [
            ("GET", "api/v1/campaigns/lists", {"params": {"api_key": PROSP_API_KEY}}),
            ("POST", "api/v1/campaigns/lists", {"json": {"api_key": PROSP_API_KEY}}),
            ("GET", "api/v1/conversations", {"params": {"api_key": PROSP_API_KEY}}),
            ("GET", "api/v1/campaigns/conversations", {"params": {"api_key": PROSP_API_KEY}}),
            ("GET", "api/v1/inbox", {"params": {"api_key": PROSP_API_KEY}}),
            ("POST", "api/v1/conversations", {"json": {"api_key": PROSP_API_KEY}}),
        ]:
            try:
                url = f"{base}/{path}"
                if method == "GET":
                    r = requests.get(url, headers=prosp_headers, timeout=15, **kw)
                else:
                    r = requests.post(url, headers=prosp_headers, timeout=15, **kw)
                is_json = (r.headers.get("content-type") or "").split(";")[0].strip().lower() == "application/json"
                looks_like_html = (r.text or "").strip().upper().startswith("<!DOCTYPE") or (r.text or "").strip().startswith("<html")
                prosp_attempts.append({"path": path, "method": method, "status_code": r.status_code, "is_json": is_json, "is_html": looks_like_html})
                if r.status_code == 200 and is_json and not looks_like_html:
                    try:
                        data = r.json()
                        out["prosp"] = {
                            "status_code": 200,
                            "url": url,
                            "top_level_keys": list(data.keys())[:15] if isinstance(data, dict) else None,
                            "body_preview": r.text[:600],
                        }
                        break
                    except Exception:
                        pass
                elif r.status_code == 200 and looks_like_html:
                    prosp_attempts[-1]["note"] = "200 but HTML (SPA page), not API JSON"
            except Exception as e:
                prosp_attempts.append({"path": path, "method": method, "error": str(e)})
        if "prosp" not in out:
            out["prosp"] = {"attempts": prosp_attempts, "message": "Set PROSP_CONVERSATIONS_PATH if your API uses a different path."}
    else:
        out["prosp"] = {"error": "PROSP_API_KEY not set"}
    return jsonify(out), 200


@app.route("/inbox/email", methods=["GET", "OPTIONS"])
def inbox_email() -> tuple[dict, int] | tuple[Response, int]:
    """Return all email messages from Instantly (all inboxes, read + unread). Excludes sending mailboxes."""
    if request.method == "OPTIONS":
        return _cors_response(Response(status=204)), 204
    try:
        from poll.instantly import get_all_email_signals
        limit = min(int(request.args.get("limit", "100") or "100"), 200)
        signals = get_all_email_signals(limit=limit)
    except Exception as e:
        logger.exception("inbox_email failed: %s", e)
        return jsonify({"error": "INBOX_EMAIL_FAILED", "message": str(e)}), 500
    emails = []
    for s in signals:
        raw = s.get("raw") or {}
        respondent = raw.get("respondent_email") or raw.get("to_email") or s.get("leadName", "")
        emails.append({
            "id": s.get("id", ""),
            "channel": "email",
            "lead_name": respondent,
            "email": respondent,
            "company": s.get("company", ""),
            "campaign": s.get("campaignOrSequence", ""),
            "reply_text": s.get("replyText", ""),
            "timestamp": s.get("timestamp", ""),
            "reply_to_uuid": raw.get("reply_to_uuid", ""),
            "from_email": raw.get("from_email", ""),
            "our_mailbox": raw.get("our_mailbox", ""),
        })
    return jsonify({"count": len(emails), "emails": emails}), 200


@app.route("/inbox/linkedin", methods=["GET", "OPTIONS"])
def inbox_linkedin() -> tuple[dict, int] | tuple[Response, int]:
    """Return all LinkedIn leads (from store). Same as /leads but filtered to channel=linkedin; excludes sending mailboxes."""
    if request.method == "OPTIONS":
        return _cors_response(Response(status=204)), 204
    from store import get_all
    try:
        records = _filter_excluded_senders(get_all())
    except Exception as e:
        logger.exception("inbox_linkedin get_all failed: %s", e)
        return jsonify({"error": "INBOX_LOAD_FAILED", "message": str(e)}), 500
    linkedin_only = [r for r in records if (r.get("channel") or "").lower() == "linkedin"]
    return jsonify({"count": len(linkedin_only), "leads": linkedin_only}), 200


@app.route("/leads", methods=["GET"])
def leads() -> tuple[dict, int] | Response:
    """Return all processed leads from store (excluding sending mailboxes). Use ?format=csv for CSV."""
    from store import get_all
    try:
        records = _filter_excluded_senders(get_all())
    except Exception as e:
        logger.exception("leads get_all failed: %s", e)
        return jsonify({"error": "LEADS_LOAD_FAILED", "message": str(e)}), 500
    enriched = [_enrich_email_lead_for_reply(r) for r in records]
    if request.args.get("format") == "csv":
        return _leads_csv_response(enriched)
    return jsonify({"count": len(enriched), "leads": enriched}), 200


@app.route("/leads/<lead_id>", methods=["GET"])
def lead_by_id(lead_id: str) -> tuple[dict, int]:
    """Return a single lead by id. Used by dashboard for lead detail view. Excludes sending mailboxes."""
    from store import get_all
    try:
        records = _filter_excluded_senders(get_all())
    except Exception as e:
        logger.exception("leads get_all failed: %s", e)
        return jsonify({"error": "LEADS_LOAD_FAILED", "message": str(e)}), 500
    lead = next((r for r in records if str(r.get("id", "")) == str(lead_id)), None)
    if not lead:
        return jsonify({"error": "NOT_FOUND", "message": "Lead not found"}), 404
    return jsonify(_enrich_email_lead_for_reply(lead)), 200


@app.route("/leads/<lead_id>/send-reply", methods=["POST"])
def lead_send_reply(lead_id: str) -> tuple[dict, int]:
    """Send reply for a lead (email via Instantly or LinkedIn via Prosp). Body: optional { \"body\": \"...\" } or use stored suggested_response."""
    from store import get_all, mark_replied
    from actions.instantly_reply import send_email_reply
    from actions.prosp_reply import send_linkedin_reply
    from run_cycle import _suggested_to_linkedin_message
    try:
        records = _filter_excluded_senders(get_all())
    except Exception as e:
        logger.exception("leads get_all failed: %s", e)
        return jsonify({"error": "LEADS_LOAD_FAILED", "message": str(e)}), 500
    lead = next((r for r in records if str(r.get("id", "")) == str(lead_id)), None)
    if not lead:
        return jsonify({"error": "NOT_FOUND", "message": "Lead not found"}), 404
    lead = _enrich_email_lead_for_reply(lead)
    data = request.get_json() or {}
    body = (data.get("body") or "").strip() or (lead.get("suggested_response") or "").strip()
    if not body:
        return jsonify({"error": "NO_BODY", "message": "No reply body and no stored suggested_response"}), 400
    channel = lead.get("channel") or ""
    if channel == "email":
        reply_to_uuid = (lead.get("reply_to_uuid") or "").strip()
        to_email = (lead.get("email") or lead.get("lead_name") or "").strip()
        from_email = (lead.get("from_email") or "").strip()
        if not reply_to_uuid or not to_email:
            return jsonify({
                "error": "REPLY_NOT_AVAILABLE",
                "message": "Email reply metadata missing (reply_to_uuid or recipient email). Re-run a cycle or set INSTANTLY_REPLY_FROM_EMAIL.",
            }), 400
        signal = {
            "leadName": lead.get("lead_name"),
            "replyText": lead.get("reply_text") or "",
            "raw": {
                "reply_to_uuid": reply_to_uuid,
                "to_email": to_email,
                "from_email": from_email,
                "subject": (lead.get("subject") or "").strip(),
            },
        }
        subject = (data.get("subject") or "").strip() or (lead.get("subject") or "").strip()
        ok = send_email_reply(signal, body, subject=subject)
    elif channel == "linkedin":
        linkedin_url = lead.get("linkedin_url") or ""
        if not linkedin_url:
            return jsonify({
                "error": "REPLY_NOT_AVAILABLE",
                "message": "LinkedIn reply metadata missing. Lead may have been stored before this was saved.",
            }), 400
        message = _suggested_to_linkedin_message(body)
        signal = {"raw": {"linkedin_url": linkedin_url}}
        ok = send_linkedin_reply(signal, message)
    else:
        return jsonify({"error": "UNSUPPORTED_CHANNEL", "message": f"Channel {channel} has no send-reply implementation"}), 400
    if ok:
        replied_at = mark_replied(lead_id)
        return jsonify(
            {
                "status": "ok",
                "message": "Reply sent",
                "channel": channel,
                "replied_at": replied_at or "",
            }
        ), 200
    return jsonify({"error": "SEND_FAILED", "message": "See server logs"}), 502


@app.route("/leads/export", methods=["GET"])
def leads_export() -> Response | tuple[dict, int]:
    """Download processed leads as CSV (excluding sending mailboxes). Add ?send_to_slack=1 to also upload to Slack."""
    from store import get_all
    try:
        records = _filter_excluded_senders(get_all())
    except Exception as e:
        logger.exception("leads_export get_all failed: %s", e)
        return Response("Error loading leads", status=500, mimetype="text/plain")
    if request.args.get("send_to_slack", "").lower() in ("1", "true", "yes"):
        csv_body = _leads_csv_string(records)
        if send_csv_to_slack(csv_body, "leads_export.csv"):
            logger.info("Leads CSV sent to Slack (%d rows) via ?send_to_slack=1", len(records))
        else:
            logger.warning("Leads export: send to Slack failed (see logs)")
    return _leads_csv_response(records)


@app.route("/leads/export-to-slack", methods=["POST", "GET"])
def leads_export_to_slack() -> tuple[dict, int]:
    """Build CSV from stored leads (excluding sending mailboxes) and upload to Slack."""
    from store import get_all
    try:
        records = _filter_excluded_senders(get_all())
    except Exception as e:
        logger.exception("leads_export_to_slack get_all failed: %s", e)
        return jsonify({"error": "LEADS_LOAD_FAILED", "message": str(e)}), 500
    csv_body = _leads_csv_string(records)
    ok = send_csv_to_slack(csv_body, "leads_export.csv")
    if ok:
        return jsonify({"status": "ok", "message": "CSV uploaded to Slack", "count": len(records)}), 200
    return jsonify({"error": "SLACK_UPLOAD_FAILED", "message": "See server logs"}), 502


def _leads_csv_string(records: list[dict]) -> str:
    """Build CSV string from store records (UTF-8 with BOM for Excel). Same as _leads_csv_response but returns str."""
    out = io.StringIO()
    out.write("\ufeff")
    writer = csv.writer(out)
    writer.writerow([
        "id", "channel", "lead_name", "company", "campaign", "classification",
        "reply_text", "suggested_response", "notified_at", "replied_at",
    ])
    for r in records:
        writer.writerow([
            r.get("id", ""),
            r.get("channel", ""),
            r.get("lead_name", ""),
            r.get("company", ""),
            r.get("campaign", ""),
            r.get("classification", ""),
            (r.get("reply_text") or "").replace("\r", " ").replace("\n", " "),
            (r.get("suggested_response") or "").replace("\r", " ").replace("\n", " "),
            r.get("notified_at", ""),
            r.get("replied_at", ""),
        ])
    return out.getvalue()


def _leads_csv_response(records: list[dict]) -> Response:
    """Build CSV response from store records (UTF-8 with BOM for Excel)."""
    body = _leads_csv_string(records)
    resp = Response(body, mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = "attachment; filename=leads_export.csv"
    resp.status_code = 200
    return resp


@app.route("/health", methods=["GET"])
def health() -> tuple[dict, int]:
    """Health check for load balancer or cron."""
    return jsonify({"status": "ok"}), 200


# Fake signal used only for /test-slack (not stored)
_TEST_SLACK_SIGNAL = {
    "id": "test-slack-demo",
    "channel": "linkedin",
    "leadName": "Dr. Jane Smith (test)",
    "company": "NHS Trust",
    "campaignOrSequence": "Medical Directors UK",
    "replyText": "Hi, this would be really useful for our team. Can we schedule a short demo next week?",
    "timestamp": "",
}


@app.route("/test-slack", methods=["GET", "POST"])
@app.route("/test-slack/", methods=["GET", "POST"])
def test_slack() -> tuple[dict, int]:
    """
    Send one test lead alert to Slack (fake LinkedIn reply). Use this to verify
    Slack posting without real Instantly/Prosp data. Does not write to processed.json.
    """
    try:
        suggested = suggest_reply(_TEST_SLACK_SIGNAL)
        ok = send_slack_alert(_TEST_SLACK_SIGNAL, suggested)
        if ok:
            return (
                jsonify(
                    {
                        "status": "ok",
                        "message": "Test alert sent to Slack. Check your channel.",
                        "channel_id": SLACK_CHANNEL_ID,
                    }
                ),
                200,
            )
        return (
            jsonify(
                {
                    "error": "SLACK_FAILED",
                    "message": "Slack post failed. Check logs and SLACK_ACCESS_TOKEN / SLACK_CHANNEL_ID.",
                }
            ),
            502,
        )
    except Exception as e:
        logger.exception("test_slack failed: %s", e)
        return (
            jsonify({"error": "TEST_FAILED", "message": str(e)}),
            500,
        )


@app.route("/test-prosp-pull", methods=["GET"])
def test_prosp_pull() -> tuple[dict, int]:
    """
    Test Prosp: pull campaigns → leads → conversation per lead. Use after replying in LinkedIn
    to see if we get the conversation back. Query: ?campaign_id=<id> (optional; else first campaign).
    """
    try:
        from poll.prosp import pull_campaign_conversations
        campaign_id = request.args.get("campaign_id", "").strip() or None
        out = pull_campaign_conversations(campaign_id=campaign_id, max_leads=10)
        return jsonify(out), 200
    except Exception as e:
        logger.exception("test_prosp_pull failed: %s", e)
        return jsonify({"error": "TEST_PROSP_PULL_FAILED", "message": str(e)}), 500


@app.route("/test-prosp-to-slack", methods=["POST", "GET"])
def test_prosp_to_slack() -> tuple[dict, int]:
    """
    Pull one Prosp conversation (campaign → leads → conversation), build suggested reply,
    and send to Slack. Use to verify Prosp → Slack flow without waiting for classification.
    """
    try:
        from config import PROSP_API_KEY
        from poll.prosp import get_prosp_signals_via_campaigns
        if not PROSP_API_KEY:
            return jsonify({"error": "PROSP_API_KEY not set", "message": "Set PROSP_SENDER in .env for conversation API."}), 400
        signals = get_prosp_signals_via_campaigns(max_campaigns=1, max_leads_per_campaign=10)
        signal = next((s for s in signals if (s.get("replyText") or "").strip()), None)
        if not signal:
            return jsonify({
                "status": "no_signal",
                "message": "No Prosp conversation with a reply found. Ensure PROSP_SENDER is set and leads have replied.",
                "signals_checked": len(signals),
            }), 200
        suggested = suggest_reply(signal)
        if send_slack_alert(signal, suggested):
            return jsonify({
                "status": "ok",
                "message": "Prosp reply and suggested response sent to Slack",
                "lead": signal.get("leadName"),
                "campaign": signal.get("campaignOrSequence"),
                "reply_preview": (signal.get("replyText") or "")[:200],
            }), 200
        return jsonify({"error": "SLACK_SEND_FAILED", "message": "See server logs"}), 502
    except Exception as e:
        logger.exception("test_prosp_to_slack failed: %s", e)
        return jsonify({"error": "TEST_PROSP_TO_SLACK_FAILED", "message": str(e)}), 500


@app.route("/linkedin-engager", methods=["POST"])
def linkedin_engager() -> tuple[dict, int]:
    """
    Generate a custom, content-driven email for someone who engaged on LinkedIn
    (liked post, viewed profile, connected but no reply). Body: { name, email?, linkedin_url?, engagement_type? }.
    engagement_type: liked_post | viewed_profile | connected.
    """
    try:
        from actions.engagement import generate_linkedin_engager_email
        data = request.get_json() or {}
        name = (data.get("name") or "").strip() or "there"
        email = (data.get("email") or "").strip()
        linkedin_url = (data.get("linkedin_url") or "").strip()
        engagement_type = (data.get("engagement_type") or "connected").strip()
        result = generate_linkedin_engager_email(
            name=name, email=email, linkedin_url=linkedin_url, engagement_type=engagement_type
        )
        return jsonify({"status": "ok", "subject": result["subject"], "body": result["body"]}), 200
    except Exception as e:
        logger.exception("linkedin_engager failed: %s", e)
        return jsonify({"error": "LINKEDIN_ENGAGER_FAILED", "message": str(e)}), 500


@app.route("/uno-reverse", methods=["POST"])
def uno_reverse() -> tuple[dict, int]:
    """
    Generate content-driven outreach for a list of Eolas LinkedIn engagers (uno reverse).
    Body: { engagers: [ { name, email?, linkedin_url?, engagement_type? } ], add_to_instantly?: false, campaign_id?: "" }.
    Returns list of { name, email, subject, body }. If add_to_instantly and campaign_id set, bulk-adds leads to Instantly.
    """
    try:
        from actions.engagement import generate_uno_reverse_outreach
        from config import INSTANTLY_API_KEY, INSTANTLY_BASE_URL
        data = request.get_json() or {}
        engagers = data.get("engagers") or []
        if not isinstance(engagers, list):
            return jsonify({"error": "BAD_REQUEST", "message": "engagers must be a list"}), 400
        outreach = generate_uno_reverse_outreach(engagers[:50])
        add_to_instantly = data.get("add_to_instantly") is True
        campaign_id = (data.get("campaign_id") or "").strip()
        if add_to_instantly and campaign_id and INSTANTLY_API_KEY:
            leads_payload = []
            for item in outreach:
                if not item.get("email"):
                    continue
                parts = (item.get("name") or "Engager").strip().split(None, 1)
                first_name = parts[0] if parts else "Engager"
                last_name = parts[1] if len(parts) > 1 else ""
                leads_payload.append({
                    "email": item["email"],
                    "first_name": first_name,
                    "last_name": last_name,
                    "company_name": "",
                })
            if leads_payload:
                import requests as req
                r = req.post(
                    f"{INSTANTLY_BASE_URL.rstrip('/')}/leads/bulk",
                    json={"campaign_id": campaign_id, "leads": leads_payload},
                    headers={
                        "Authorization": f"Bearer {INSTANTLY_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    timeout=60,
                )
                if r.status_code in (200, 201, 204):
                    return jsonify({
                        "status": "ok",
                        "outreach": outreach,
                        "instantly_added": len(leads_payload),
                        "campaign_id": campaign_id,
                    }), 200
                return jsonify({
                    "status": "ok",
                    "outreach": outreach,
                    "instantly_error": r.text[:300],
                }), 200
        return jsonify({"status": "ok", "outreach": outreach}), 200
    except Exception as e:
        logger.exception("uno_reverse failed: %s", e)
        return jsonify({"error": "UNO_REVERSE_FAILED", "message": str(e)}), 500


@app.route("/test-email", methods=["POST", "GET"])
def test_email() -> tuple[dict, int]:
    """
    Run one full cycle and return what was fetched and processed. Use after replying to an
    Instantly email or Prosp LinkedIn message to confirm it was picked up and sent to Slack.
    """
    try:
        from config import PROSP_API_KEY
        from poll.instantly import get_unread_signals as get_instantly
        from poll.prosp import get_unread_signals as get_prosp
        from store import get_all
        instantly_count = len(get_instantly(limit=50))
        linkedin_count = len(get_prosp()) if PROSP_API_KEY else 0
        counts = run_cycle()
        records = get_all()
        return jsonify({
            "status": "ok",
            "sources_before_run": {"instantly": instantly_count, "linkedin": linkedin_count},
            "counts": counts,
            "total_leads_stored": len(records),
            "last_5_leads": records[-5:] if len(records) >= 5 else records,
            "next": "Check Slack for interested alerts; GET /leads or /leads/export for full list.",
        }), 200
    except Exception as e:
        logger.exception("test_email failed: %s", e)
        return jsonify({"error": "TEST_EMAIL_FAILED", "message": str(e)}), 500


@app.route("/run-cycle", methods=["POST", "GET"])
def trigger_cycle() -> tuple[dict, int]:
    """
    Run one poll → classify → notify cycle. Safe for cron (e.g. POST from Vercel Cron).
    """
    try:
        counts = run_cycle()
        return jsonify({"status": "ok", "counts": counts}), 200
    except Exception as e:
        logger.exception("run_cycle failed: %s", e)
        return (
            jsonify(
                {
                    "error": "CYCLE_FAILED",
                    "message": "Cycle failed",
                    "context": {},
                }
            ),
            500,
        )


def start_scheduler() -> None:
    """Start background scheduler to run cycle every N minutes."""
    global scheduler
    from config import POLL_INTERVAL_MINUTES

    if scheduler is not None:
        return
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_cycle,
        "interval",
        minutes=POLL_INTERVAL_MINUTES,
        id="speed_to_response_cycle",
    )
    scheduler.start()
    logger.info("Scheduler started: run_cycle every %s min", POLL_INTERVAL_MINUTES)


@app.route("/<path:path>", methods=["OPTIONS"])
def _cors_preflight_catchall(path: str = "") -> tuple[dict, int]:
    """Respond to CORS preflight for any path (registered last so specific routes match first)."""
    return {}, 204


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print("=" * 60)
    print("speed-to-response — Flask app")
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        print(f"  {list(rule.methods - {'HEAD', 'OPTIONS'})} {rule.rule}")
    print("=" * 60)
    if os.getenv("RUN_SCHEDULER", "1") == "1":
        start_scheduler()
    app.run(host="0.0.0.0", port=port, debug=False)
