"""Tests for Instantly email reply action."""
import pytest
import requests


def test_send_email_reply_returns_false_when_missing_reply_to_uuid():
    from actions.instantly_reply import send_email_reply
    signal = {"raw": {"to_email": "lead@example.com"}, "leadName": "Lead"}
    assert send_email_reply(signal, "Body") is False


def test_send_email_reply_returns_false_when_missing_to_email():
    from actions.instantly_reply import send_email_reply
    signal = {"raw": {"reply_to_uuid": "uuid-123"}, "leadName": "Lead"}
    # to_email missing; we use leadName but it's not an email, so to_email may be empty
    result = send_email_reply(signal, "Body")
    assert result is False


def test_send_email_reply_success_when_mocked(monkeypatch):
    from actions import instantly_reply
    monkeypatch.setattr(instantly_reply, "INSTANTLY_API_KEY", "test-key")
    captured = {}

    def mock_post(url, json=None, **kwargs):
        captured["json"] = json
        m = type("Response", (), {"status_code": 200, "text": ""})()
        return m

    monkeypatch.setattr(requests, "post", mock_post)
    signal = {
        "raw": {
            "reply_to_uuid": "u1",
            "to_email": "lead@example.com",
            "from_email": "us@mail.com",
        },
        "leadName": "Lead",
    }
    result = instantly_reply.send_email_reply(signal, "Hi there")
    assert result is True
    assert captured["json"]["eaccount"] == "us@mail.com"
    assert captured["json"]["body"]["text"] == "Hi there"
    assert captured["json"]["reply_to_uuid"] == "u1"
    assert "subject" in captured["json"]
