"""
Load and validate config from .env. Uses repo root .env when run from speed-to-response/.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Repo root is parent of speed-to-response; then speed-to-response .env overrides
_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _REPO_ROOT / ".env"
_APP_ENV = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH)
load_dotenv(_APP_ENV, override=True)  # speed-to-response/.env overrides repo root
load_dotenv(override=True)  # cwd .env overrides if present


def _get(key: str, default: str = "") -> str:
    val = os.getenv(key, default)
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val or ""


# Required for core flow
INSTANTLY_API_KEY = _get("INSTANTLY_API_KEY")
# LinkedIn: Prosp
PROSP_API_KEY = _get("PROSP_API_KEY")
PROSP_API_BASE = _get("PROSP_API_BASE", "https://prosp.ai").rstrip("/")
PROSP_CONVERSATIONS_PATH = _get("PROSP_CONVERSATIONS_PATH", "").strip()
PROSP_SENDER = _get("PROSP_SENDER", "").strip()  # Sender for leads/conversation (e.g. your LinkedIn URL or Prosp sender id)
# Prosp campaign pull: 0 = all campaigns; 0 for leads = all leads per campaign (can be slow)
PROSP_MAX_CAMPAIGNS = int(_get("PROSP_MAX_CAMPAIGNS", "0") or "0")
PROSP_MAX_LEADS_PER_CAMPAIGN = int(_get("PROSP_MAX_LEADS_PER_CAMPAIGN", "200") or "200")
SLACK_ACCESS_TOKEN = _get("SLACK_ACCESS_TOKEN")
SLACK_BOT_TOKEN = _get("SLACK_BOT_TOKEN")  # prefer this for chat.postMessage (has chat:write)
SLACK_CHANNEL_ID = _get("SLACK_CHANNEL_ID").strip()  # channel or user ID to post to
OPENAI_API_KEY = _get("OPENAI_API_KEY")

# Azure OpenAI (optional; used for classify + suggest_reply when set)
AZURE_OPENAI_ENDPOINT = _get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = _get("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT = _get("AZURE_OPENAI_DEPLOYMENT", "TherabotAgent")
AZURE_OPENAI_API_VERSION = _get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

# Optional
SLACK_REFRESH_TOKEN = _get("SLACK_REFRESH_TOKEN")
WAHA_BASE_URL = _get("WAHA_BASE_URL")
WAHA_SESSION = _get("WAHA_SESSION")

# App
POLL_INTERVAL_MINUTES = int(_get("POLL_INTERVAL_MINUTES", "5"))
INSTANTLY_BASE_URL = "https://api.instantly.ai/api/v2"
# Auto-reply: set to "1" or "true" to send replies when interested
AUTO_REPLY_EMAIL = _get("AUTO_REPLY_EMAIL", "").strip().lower() in ("1", "true", "yes")
AUTO_REPLY_LINKEDIN = _get("AUTO_REPLY_LINKEDIN", "1").strip().lower() in ("1", "true", "yes")
# Default sending mailbox when replying (Instantly); overridden by email.to_email if present
INSTANTLY_REPLY_FROM_EMAIL = _get("INSTANTLY_REPLY_FROM_EMAIL", "").strip()
# Content-driven: optional URLs for NHS case study and Ask Eolas demo (included in suggested replies when relevant)
EOLAS_NHS_CASE_STUDY_URL = _get("EOLAS_NHS_CASE_STUDY_URL", "").strip()
EOLAS_DEMO_VIDEO_URL = _get("EOLAS_DEMO_VIDEO_URL", "").strip()
DATA_DIR = Path(__file__).resolve().parent / "data"
PROCESSED_JSON = DATA_DIR / "processed.json"

# Exclude these sender addresses from ever appearing as leads (our sending mailboxes).
# Comma-separated; case-insensitive. Example: declan@mail.teameolasmedical.com,richard@hci.digital
_EXCLUDE_SENDER_RAW = _get("EXCLUDE_SENDER_EMAILS", "").strip()
EXCLUDE_SENDER_EMAILS: frozenset[str] = frozenset(
    e.strip().lower() for e in _EXCLUDE_SENDER_RAW.split(",") if e.strip()
)
# Optional: treat any address ending with these domains as “our” mailboxes (e.g. @mail.teameolasmedical.com)
_EXCLUDE_DOM_RAW = _get("EXCLUDE_SENDER_DOMAINS", "").strip()
EXCLUDE_SENDER_DOMAINS: frozenset[str] = frozenset(
    d.strip().lower().lstrip("@") for d in _EXCLUDE_DOM_RAW.split(",") if d.strip()
)


def is_our_sending_address(addr: str) -> bool:
    """True if this email is one of our mailboxes (exact list and/or domain list).

    Domain list matches subdomains: e.g. teameolasmedical.com matches
    outreach.tryeolasmedical.com and connect.teameolasmedical.com (not only @teameolasmedical.com).
    """
    a = (addr or "").strip().lower()
    if not a:
        return False
    if EXCLUDE_SENDER_EMAILS and a in EXCLUDE_SENDER_EMAILS:
        return True
    if "@" not in a:
        return False
    _, _, domain = a.partition("@")
    if not domain:
        return False
    if not EXCLUDE_SENDER_DOMAINS:
        return False
    for d in EXCLUDE_SENDER_DOMAINS:
        dom = d.lower().lstrip("@")
        if domain == dom or domain.endswith("." + dom):
            return True
    return False


def validate_config() -> list[str]:
    """Return list of missing required config keys."""
    missing = []
    if not INSTANTLY_API_KEY:
        missing.append("INSTANTLY_API_KEY")
    if not SLACK_ACCESS_TOKEN and not SLACK_BOT_TOKEN:
        missing.append("SLACK_ACCESS_TOKEN or SLACK_BOT_TOKEN")
    if not SLACK_CHANNEL_ID:
        missing.append("SLACK_CHANNEL_ID")
    # LLM: need at least one of OpenAI or Azure OpenAI for classify + suggest_reply
    if not OPENAI_API_KEY and not AZURE_OPENAI_KEY:
        missing.append("OPENAI_API_KEY or AZURE_OPENAI_KEY")
    return missing
