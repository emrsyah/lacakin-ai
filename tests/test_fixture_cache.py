import json
from pathlib import Path

import pytest

from mcp.vision_mcp.fixture_cache import lookup, register_fixture, hash_image

FIXTURES = Path(__file__).resolve().parent.parent / "mcp" / "vision_mcp" / "fixtures"


def test_hash_image_is_deterministic(tmp_path):
    img = tmp_path / "a.bin"
    img.write_bytes(b"abc")
    assert hash_image(str(img)) == hash_image(str(img))


def test_register_and_lookup(tmp_path, monkeypatch):
    monkeypatch.setattr("mcp.vision_mcp.fixture_cache.FIXTURES_DIR", tmp_path)
    img = tmp_path / "demo.jpg"
    img.write_bytes(b"fakejpegbytes")
    response = {"match_confidence": 0.9, "narrative": "ok", "matches": ["a"],
                "mismatches": [], "suspicious_signals": [], "route_to": []}
    register_fixture(str(img), response)
    assert lookup(str(img)) == response


def test_lookup_returns_none_for_unregistered(tmp_path, monkeypatch):
    monkeypatch.setattr("mcp.vision_mcp.fixture_cache.FIXTURES_DIR", tmp_path)
    img = tmp_path / "unregistered.jpg"
    img.write_bytes(b"x")
    assert lookup(str(img)) is None
