"""Shared fixtures. We keep tests offline-friendly — anything that hits
Anthropic or Telegram is gated behind a marker."""
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def tmp_lacakin(tmp_path, monkeypatch):
    """A fake ~/lacakin/shared workspace for tests that touch files."""
    shared = tmp_path / "shared"
    (shared / "photos").mkdir(parents=True)
    (shared / "findings").mkdir(parents=True)
    monkeypatch.setenv("LACAKIN_SHARED", str(shared))
    monkeypatch.setenv("LACAKIN_DB", str(tmp_path / "lacakin.db"))
    return shared


@pytest.fixture
def has_anthropic_key():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
