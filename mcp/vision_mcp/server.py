"""
vision-mcp: image similarity (Jina CLIP v2 API) + license plate OCR (Claude Haiku vision).

Tools:
  - match_image(reference_path, candidate_path) -> {score: 0..1, reasoning}
  - read_plate(image_path)                      -> {plate: str|null, raw: [str], confidence}
  - reason_about_candidate(image_path, context_md, source_type) -> structured JSON
"""
from __future__ import annotations

import base64
import math
import os
import re
from pathlib import Path
from typing import Any

try:
    import sys as _sys, importlib as _il
    _real_mcp = _il.import_module("mcp.server.fastmcp")
    FastMCP = _real_mcp.FastMCP
    del _real_mcp, _sys, _il
except (ModuleNotFoundError, ImportError):
    class FastMCP:  # type: ignore[no-redef]
        def __init__(self, name): self.name = name
        def tool(self): return lambda f: f
        def run(self): pass

mcp = FastMCP("vision-mcp")

JINA_API_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-clip-v2"


def _jina_headers() -> dict:
    key = os.environ.get("JINA_API_KEY", "")
    if not key:
        raise RuntimeError("JINA_API_KEY env var not set")
    return {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}


def _img_to_b64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode()


def _embed_images(paths: list[str]) -> list[list[float]]:
    """Call Jina API and return one embedding per image path."""
    import requests
    payload = {
        "model": JINA_MODEL,
        "input": [{"image": _img_to_b64(p)} for p in paths],
    }
    resp = requests.post(JINA_API_URL, headers=_jina_headers(), json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return [item["embedding"] for item in data["data"]]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@mcp.tool()
def match_image(reference_path: str, candidate_path: str) -> dict[str, Any]:
    """Cosine similarity between two images via Jina CLIP v2. Returns score 0..1.

    Thresholds used by worker prompts:
      < 0.55  → drop silently
      0.55–0.70 → log only
      ≥ 0.70  → advance to Stage-2 Sonnet reasoning
    """
    if not Path(reference_path).exists():
        return {"error": f"reference not found: {reference_path}"}
    if not Path(candidate_path).exists():
        return {"error": f"candidate not found: {candidate_path}"}
    try:
        embs = _embed_images([reference_path, candidate_path])
        raw = _cosine(embs[0], embs[1])
        # Jina CLIP embeddings are L2-normalised; same-image cosine ≈ 1.0,
        # unrelated images sit ~0.1–0.4. Clamp to [0, 1].
        score = round(max(0.0, min(1.0, raw)), 3)
        return {
            "score": score,
            "raw_cosine": round(raw, 3),
            "reasoning": (
                "high visual similarity" if score >= 0.75
                else "moderate similarity" if score >= 0.55
                else "low similarity"
            ),
        }
    except Exception as e:
        return {"error": str(e)}


# Indonesian plate: 1-2 letters + 1-4 digits + 1-3 letters, e.g. "D 1234 ABC".
_PLATE_RE = re.compile(r"\b([A-Z]{1,2})\s?([0-9]{1,4})\s?([A-Z]{1,3})\b")


@mcp.tool()
def read_plate(image_path: str) -> dict[str, Any]:
    """Extract an Indonesian license plate from an image using Claude Haiku vision.

    Returns {plate: str|null, raw: str, confidence: 0..1}.
    Costs ~$0.001/call — only call when CLIP score >= 0.60."""
    if not Path(image_path).exists():
        return {"error": f"not found: {image_path}"}

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set"}

    try:
        from anthropic import Anthropic
        img_b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
        media_type = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"

        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64",
                        "media_type": media_type, "data": img_b64}},
                    {"type": "text", "text": (
                        "Baca plat nomor kendaraan bermotor Indonesia di gambar ini. "
                        "Format plat Indonesia: 1-2 huruf, 1-4 angka, 1-3 huruf. "
                        "Contoh: 'D 1234 ABC'. "
                        "Jika ada plat, balas HANYA teks plat saja tanpa penjelasan. "
                        "Jika tidak terlihat / dikaburkan, balas: TIDAK_TERLIHAT"
                    )},
                ],
            }],
        )
        raw = resp.content[0].text.strip().upper()
        m = _PLATE_RE.search(raw)
        plate = f"{m.group(1)} {m.group(2)} {m.group(3)}" if m else None
        return {
            "plate": plate,
            "raw": raw,
            "confidence": 0.85 if plate else 0.0,
        }
    except Exception as e:
        return {"error": str(e)}


from mcp.vision_mcp.sonnet_reason import reason_about_candidate as _reason


@mcp.tool()
def reason_about_candidate(image_path: str, context_md: str,
                            source_type: str) -> dict[str, Any]:
    """Stage-2 vision reasoning. Call ONLY on candidates with match_image >= 0.7.

    Returns structured JSON: match_confidence, matches[], mismatches[],
    suspicious_signals[], narrative, route_to[]. Post `narrative` + bullets
    into the group; emit a @-mention for each route_to entry."""
    return _reason(image_path=image_path, context_md=context_md, source_type=source_type)


if __name__ == "__main__":
    mcp.run()
