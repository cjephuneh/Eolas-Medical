"""Pytest fixtures: temp store path so tests don't touch real data."""
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def temp_store(monkeypatch):
    """Use a temp file for processed.json in tests; reset in-memory cache."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "processed.json"
        monkeypatch.setattr("config.PROCESSED_JSON", path)
        monkeypatch.setattr("store.PROCESSED_JSON", path)
        import store as store_mod
        store_mod._RECORDS = None
        yield path
