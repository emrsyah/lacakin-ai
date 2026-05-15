"""Hash-keyed fixture cache for the staged demo CCTV image.

Pre-register the staged image + its expected Sonnet response. At demo time
the gateway hits the fixture instead of the real Sonnet API, so the T+0:35
moment fires deterministically and fast.

Real candidates (other CCTVs, real Tokopedia listings) bypass the cache and
hit Sonnet for real."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def hash_image(image_path: str) -> str:
    h = hashlib.sha256()
    with open(image_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _fixture_path(image_hash: str) -> Path:
    return FIXTURES_DIR / f"{image_hash}.json"


def register_fixture(image_path: str, response: dict) -> str:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    h = hash_image(image_path)
    _fixture_path(h).write_text(json.dumps(response, indent=2))
    return h


def lookup(image_path: str) -> dict | None:
    h = hash_image(image_path)
    p = _fixture_path(h)
    if not p.exists():
        return None
    return json.loads(p.read_text())
