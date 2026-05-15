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
SCORES_DIR = FIXTURES_DIR / "scores"


def hash_image(image_path: str) -> str:
    h = hashlib.sha256()
    with open(image_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _fixture_path(image_hash: str) -> Path:
    return FIXTURES_DIR / f"{image_hash}.json"


def _score_path(image_hash: str) -> Path:
    return SCORES_DIR / f"{image_hash}.json"


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


def register_score(image_path: str, *, text_image: float | None = None,
                   image_image: float | None = None) -> str:
    """Record verified-similarity scores for a known image. Merges into any
    existing record for the same hash. Returns the image hash."""
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    h = hash_image(image_path)
    p = _score_path(h)
    current: dict[str, float] = {}
    if p.exists():
        try:
            current = json.loads(p.read_text())
        except json.JSONDecodeError:
            current = {}
    if text_image is not None:
        current["text_image"] = float(text_image)
    if image_image is not None:
        current["image_image"] = float(image_image)
    p.write_text(json.dumps(current, indent=2))
    return h


def lookup_score(image_path: str, kind: str) -> float | None:
    """Return a previously recorded similarity score for this image, if any.

    `kind` is "text_image" (Jina CLIP text↔image cosine) or "image_image"
    (image↔image cosine). Callers fall back to a live embeddings call when
    this returns None. Used to keep downstream rules deterministic when an
    operator has already verified the imagery in a prior review.
    """
    p = _score_path(hash_image(image_path))
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text()).get(kind)
    except json.JSONDecodeError:
        return None
