"""Tests for classify: keyword and label parsing."""
import pytest

from classify import _keyword_classify, classify


def test_keyword_classify_empty():
    label, reason = _keyword_classify("")
    assert label == "not_interested"
    assert "empty" in reason.lower() or "missing" in reason.lower()


def test_keyword_classify_bounce():
    label, _ = _keyword_classify("Delivery Status Notification (Failure) mailer-daemon")
    assert label == "bounce"


def test_keyword_classify_ooo():
    label, _ = _keyword_classify("I am out of the office until next week.")
    assert label == "out_of_office"


def test_keyword_classify_not_interested():
    label, _ = _keyword_classify("Not interested, please unsubscribe me.")
    assert label == "not_interested"


def test_keyword_classify_interested():
    label, _ = _keyword_classify("Yes, would love to learn more. Can we book a demo?")
    assert label == "interested"


def test_keyword_classify_short_not_interested():
    label, _ = _keyword_classify("No")
    assert label == "not_interested"
