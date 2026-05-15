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
    # Reset lazy DB connections so each test gets a fresh DB at the tmp path.
    import mcp.a2a_mcp.server as _a2a
    old_a2a = _a2a._conn
    _a2a._conn = None
    yield shared
    if _a2a._conn is not None:
        _a2a._conn.close()
    _a2a._conn = old_a2a


@pytest.fixture
def has_openai_key():
    return bool(os.environ.get("OPENAI_API_KEY"))


