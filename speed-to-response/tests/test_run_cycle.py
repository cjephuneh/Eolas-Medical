"""Tests for run_cycle helpers: lead display name, personalization, LinkedIn message."""
from run_cycle import _lead_display_name, _personalize_suggested, _suggested_to_linkedin_message


def test_lead_display_name_email():
    assert _lead_display_name("declan@mail.tryeolasmedical.com") == "Declan"
    assert _lead_display_name("Jane@example.com") == "Jane"


def test_lead_display_name_plain():
    assert _lead_display_name("Dr. Smith") == "Dr. Smith"
    assert _lead_display_name("") == "there"
    assert _lead_display_name("   ") == "there"


def test_personalize_suggested_replaces_name():
    text = "Hi [Name],\n\nThanks for your reply."
    out = _personalize_suggested(text, "declan@mail.example.com")
    assert "[Name]" not in out
    assert "Declan" in out
    assert out == "Hi Declan,\n\nThanks for your reply."


def test_personalize_suggested_lead_name():
    text = "Hi [Lead's Name], would you like a demo?"
    out = _personalize_suggested(text, "jane@nhs.uk")
    assert "[Lead's Name]" not in out
    assert "Jane" in out


def test_suggested_to_linkedin_message_strips_subject():
    text = "Subject: Re: Demo\n\nHi Declan, would you like a short demo?"
    out = _suggested_to_linkedin_message(text)
    assert out == "Hi Declan, would you like a short demo?"
    assert not out.upper().startswith("SUBJECT:")


def test_suggested_to_linkedin_message_no_subject():
    text = "Hi there, when can we schedule a demo?"
    assert _suggested_to_linkedin_message(text) == text
