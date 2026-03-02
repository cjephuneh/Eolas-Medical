"""Tests for suggest_reply: fallback when no API key, AMD segment, content-driven."""
import pytest

from suggest_reply import (
    _fallback_draft,
    _is_academic_medical_director,
    suggest_reply,
)


def test_fallback_draft():
    draft = _fallback_draft("Jane")
    assert "demo" in draft.lower() or "Eolas" in draft
    assert "Jane" in draft or "thanks" in draft.lower()


def test_is_academic_medical_director_true():
    assert _is_academic_medical_director({"leadName": "Dr. Jane", "company": "University Hospital", "campaignOrSequence": ""}) is True
    assert _is_academic_medical_director({"leadName": "Medical Director Smith", "company": "", "campaignOrSequence": ""}) is True
    assert _is_academic_medical_director({"leadName": "X", "company": "NHS Trust", "campaignOrSequence": ""}) is True


def test_is_academic_medical_director_false():
    assert _is_academic_medical_director({"leadName": "John", "company": "Acme Corp", "campaignOrSequence": ""}) is False


def test_suggest_reply_without_openai_returns_fallback(monkeypatch):
    import suggest_reply as suggest_reply_mod
    monkeypatch.setattr(suggest_reply_mod, "get_client", lambda: None)
    signal = {
        "leadName": "Dr. Smith",
        "company": "NHS Trust",
        "campaignOrSequence": "Medical Directors",
        "replyText": "Would like to learn more.",
        "channel": "email",
    }
    draft = suggest_reply(signal)
    assert len(draft) > 0
    assert "demo" in draft.lower() or "Eolas" in draft
