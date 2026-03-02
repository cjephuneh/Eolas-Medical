"""Tests for Prosp LinkedIn reply action."""
def test_send_linkedin_reply_returns_false_when_missing_linkedin_url():
    from actions.prosp_reply import send_linkedin_reply
    signal = {"channel": "linkedin", "raw": {}, "leadName": "Jane"}
    assert send_linkedin_reply(signal, "Hi Jane, would you like a demo?") is False


def test_send_linkedin_reply_success_when_mocked(monkeypatch):
    import requests
    from actions import prosp_reply
    monkeypatch.setattr(prosp_reply, "PROSP_API_KEY", "test-key")
    monkeypatch.setattr(prosp_reply, "PROSP_SENDER", "https://www.linkedin.com/in/test")
    def mock_post(*args, **kwargs):
        m = type("Response", (), {"status_code": 200, "text": ""})()
        return m
    monkeypatch.setattr(requests, "post", mock_post)
    signal = {
        "channel": "linkedin",
        "raw": {"linkedin_url": "https://www.linkedin.com/in/lead"},
        "leadName": "Lead",
    }
    assert prosp_reply.send_linkedin_reply(signal, "Hi, demo?") is True
