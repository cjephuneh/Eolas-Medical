"""Tests for store: idempotency and append."""
import pytest

from store import append, get_all, is_processed


def test_is_processed_empty():
    assert is_processed("instantly:123") is False


def test_append_and_is_processed():
    append(
        signal_id="instantly:abc",
        channel="email",
        lead_name="Jane",
        company="NHS Trust",
        campaign="Medical Directors",
        reply_text="Would like a demo.",
        classification="interested",
        suggested_response="Thanks! When works?",
        notified_at="2026-02-27T12:00:00Z",
    )
    assert is_processed("instantly:abc") is True
    assert is_processed("instantly:xyz") is False


def test_get_all():
    append(
        signal_id="instantly:1",
        channel="email",
        lead_name="A",
        company="C",
        campaign="X",
        reply_text="Hi",
        classification="interested",
        suggested_response="Ok",
        notified_at="2026-02-27T12:00:00Z",
    )
    records = get_all()
    assert len(records) >= 1
    assert any(r["id"] == "instantly:1" for r in records)
