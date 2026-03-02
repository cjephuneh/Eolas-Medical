"""Tests for LinkedIn engager and uno-reverse outreach generation."""
import pytest

from actions.engagement import generate_linkedin_engager_email, generate_uno_reverse_outreach


def test_generate_linkedin_engager_email_returns_subject_and_body():
    out = generate_linkedin_engager_email(name="Jane", engagement_type="connected")
    assert "subject" in out
    assert "body" in out
    assert len(out["subject"]) > 0
    assert len(out["body"]) > 0
    assert "Jane" in out["body"] or "there" in out["body"]


def test_generate_linkedin_engager_email_engagement_types():
    for eng_type in ("liked_post", "viewed_profile", "connected"):
        out = generate_linkedin_engager_email(name="Test", engagement_type=eng_type)
        assert out["subject"]
        assert out["body"]


def test_generate_uno_reverse_outreach_returns_one_per_engager():
    engagers = [
        {"name": "Alice", "email": "alice@example.com"},
        {"name": "Bob", "email": "bob@example.com", "engagement_type": "liked_post"},
    ]
    out = generate_uno_reverse_outreach(engagers)
    assert len(out) == 2
    assert out[0]["name"] == "Alice"
    assert out[0]["email"] == "alice@example.com"
    assert "subject" in out[0]
    assert "body" in out[0]
    assert out[1]["name"] == "Bob"


def test_generate_uno_reverse_outreach_empty_list():
    assert generate_uno_reverse_outreach([]) == []
