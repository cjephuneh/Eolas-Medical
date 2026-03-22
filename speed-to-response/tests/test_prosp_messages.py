"""Tests for Prosp conversation message extraction (nested API shapes)."""
from poll.prosp import _extract_messages_from_conversation, _normalize_message_for_display


def test_extract_nested_data_thread_messages():
    raw = {
        "success": True,
        "data": {
            "thread": {
                "messages": [
                    {"text": "Hello from lead", "from_me": False},
                    {"content": "Our reply", "from_me": True},
                ]
            }
        },
    }
    msgs = _extract_messages_from_conversation(raw)
    assert len(msgs) == 2
    assert msgs[0].get("text") == "Hello from lead"


def test_extract_top_level_messages_key():
    raw = {
        "messages": [
            {"snippet": "Quick question", "direction": "inbound"},
            {"body": "Thanks — here is info", "direction": "outbound"},
        ]
    }
    out = _extract_messages_from_conversation(raw)
    assert len(out) == 2
    n0 = _normalize_message_for_display(out[0])
    assert "Quick question" in n0["content"]


def test_extract_empty():
    assert _extract_messages_from_conversation(None) == []
    assert _extract_messages_from_conversation({}) == []
