"""Tests for Instantly poll: normalize email to signal."""
from unittest.mock import patch

from poll.instantly import fetch_unread_emails, normalize_email_to_signal


def test_normalize_email_to_signal():
    email = {
        "id": "uuid-123",
        "uuid": "uuid-123",
        "from_email": "lead@nhs.uk",
        "to_email": "us@eolas.com",
        "subject": "Re: Eolas",
        "body": "Would like to book a demo.",
        "thread_id": "thread-1",
        "campaign_name": "Medical Directors",
    }
    signal = normalize_email_to_signal(email)
    assert signal["id"] == "instantly:uuid-123"
    assert signal["channel"] == "email"
    assert signal["leadName"] == "lead@nhs.uk"
    assert signal["campaignOrSequence"] == "Medical Directors"
    assert "demo" in signal["replyText"]
    raw = signal.get("raw") or {}
    assert raw.get("reply_to_uuid") == "uuid-123"
    assert raw.get("to_email") == "lead@nhs.uk"
    assert raw.get("from_email") == "us@eolas.com"


def test_normalize_skips_when_sender_is_our_mailbox():
    """Outbound from our mailbox (From=Declan) is not a prospect response."""
    email = {
        "id": "out-1",
        "from_email": "declan@mail.teameolasmedical.com",
        "to_email": "prospect@hospital.nhs.uk",
        "subject": "Follow up",
        "body": "Our pitch",
        "direction": "outbound",
    }
    with patch("poll.instantly.is_our_sending_address", lambda a: a.lower().startswith("declan@")):
        assert normalize_email_to_signal(email) is None


def test_normalize_inverted_from_uses_external_as_respondent():
    """When Instantly lists From=mailbox and To=prospect, respondent is the prospect (To)."""
    email = {
        "id": "inv-1",
        "from_email": "declan@mail.teameolasmedical.com",
        "to_email": "doctor@nhs.uk",
        "subject": "Re: hello",
        "body": "Interested",
    }
    with patch("poll.instantly.is_our_sending_address", lambda a: "declan@" in a.lower()):
        signal = normalize_email_to_signal(email)
    assert signal is not None
    assert signal["leadName"] == "doctor@nhs.uk"
    raw = signal.get("raw") or {}
    assert raw.get("to_email") == "doctor@nhs.uk"
    assert raw.get("from_email") == "declan@mail.teameolasmedical.com"


@patch("poll.instantly.requests.get")
def test_fetch_unread_emails_empty(mock_get):
    mock_get.return_value.json.return_value = []
    mock_get.return_value.raise_for_status = lambda: None
    with patch("poll.instantly.INSTANTLY_API_KEY", "test-key"):
        result = fetch_unread_emails(limit=10)
    assert result == []
