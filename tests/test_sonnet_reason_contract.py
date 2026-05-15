import json
import pytest

from mcp.vision_mcp import fixture_cache, sonnet_reason


def test_fixture_hit_returns_cached_response(tmp_path, monkeypatch):
    monkeypatch.setattr(fixture_cache, "FIXTURES_DIR", tmp_path)
    img = tmp_path / "img.jpg"
    img.write_bytes(b"fakejpeg")
    cached = {
        "match_confidence": 0.86,
        "matches": ["warna cocok"],
        "mismatches": [],
        "suspicious_signals": ["plat dikaburkan"],
        "narrative": "Match tinggi karena warna.",
        "route_to": [{"agent": "cadang", "reason": "selatan"}],
    }
    fixture_cache.register_fixture(str(img), cached)

    out = sonnet_reason.reason_about_candidate(
        image_path=str(img), context_md="any", source_type="cctv"
    )
    assert out == cached


def test_missing_image_returns_error(tmp_path):
    out = sonnet_reason.reason_about_candidate(
        image_path=str(tmp_path / "nope.jpg"),
        context_md="x", source_type="cctv",
    )
    assert "error" in out


def test_response_shape_keys():
    """The contract every consumer relies on."""
    expected = {"match_confidence", "matches", "mismatches",
                "suspicious_signals", "narrative", "route_to"}
    assert sonnet_reason.RESPONSE_KEYS == expected


@pytest.mark.needs_api
def test_real_sonnet_call_smoke(tmp_path, has_openrouter_key):
    if not has_openrouter_key:
        pytest.skip("OPENROUTER_API_KEY not set")
    img = tmp_path / "smoke.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF...")
    out = sonnet_reason.reason_about_candidate(
        image_path=str(img), context_md="motor merah", source_type="cctv"
    )
    assert isinstance(out, dict)
