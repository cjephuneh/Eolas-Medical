"""Tests for is_our_sending_address (domain suffix + exact emails)."""
import pytest

import config as cfg


def test_exact_match_excluded_emails(monkeypatch):
    monkeypatch.setattr(cfg, "EXCLUDE_SENDER_EMAILS", frozenset({"declan@mail.example.com"}))
    monkeypatch.setattr(cfg, "EXCLUDE_SENDER_DOMAINS", frozenset())
    assert cfg.is_our_sending_address("declan@mail.example.com") is True
    assert cfg.is_our_sending_address("other@mail.example.com") is False


def test_subdomain_teameolas_matches_parent_domain(monkeypatch):
    monkeypatch.setattr(cfg, "EXCLUDE_SENDER_EMAILS", frozenset())
    monkeypatch.setattr(cfg, "EXCLUDE_SENDER_DOMAINS", frozenset({"teameolasmedical.com"}))
    assert cfg.is_our_sending_address("declan@outreach.tryeolasmedical.com") is True
    assert cfg.is_our_sending_address("declan@connect.teameolasmedical.com") is True
    assert cfg.is_our_sending_address("declan@mail.teameolasmedical.com") is True


def test_external_prospect_not_excluded(monkeypatch):
    monkeypatch.setattr(cfg, "EXCLUDE_SENDER_EMAILS", frozenset())
    monkeypatch.setattr(cfg, "EXCLUDE_SENDER_DOMAINS", frozenset({"teameolasmedical.com"}))
    assert cfg.is_our_sending_address("declan@nhs.uk") is False
    assert cfg.is_our_sending_address("prospect@hospital.nhs.uk") is False


def test_empty_and_invalid(monkeypatch):
    monkeypatch.setattr(cfg, "EXCLUDE_SENDER_EMAILS", frozenset())
    monkeypatch.setattr(cfg, "EXCLUDE_SENDER_DOMAINS", frozenset({"teameolasmedical.com"}))
    assert cfg.is_our_sending_address("") is False
    assert cfg.is_our_sending_address("not-an-email") is False
