"""
vision-mcp: image similarity (CLIP) + license plate OCR (PaddleOCR).

Tools:
  - match_image(reference_path, candidate_path) -> {score: 0..1, reasoning}
  - read_plate(image_path)                      -> {plate: str|null, raw: [str], confidence}

Models load lazily on first call so the gateway boots fast.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("vision-mcp")


@lru_cache(maxsize=1)
def _clip():
    import open_clip
    import torch
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="laion2b_s34b_b79k"
    )
    model.eval()
    return model, preprocess, torch


@lru_cache(maxsize=1)
def _ocr():
    from paddleocr import PaddleOCR
    return PaddleOCR(use_angle_cls=True, lang="en", show_log=False)


def _embed(path: str):
    from PIL import Image
    model, preprocess, torch = _clip()
    img = Image.open(path).convert("RGB")
    with torch.no_grad():
        v = model.encode_image(preprocess(img).unsqueeze(0))
        v = v / v.norm(dim=-1, keepdim=True)
    return v


@mcp.tool()
def match_image(reference_path: str, candidate_path: str) -> dict[str, Any]:
    """Cosine similarity between two images via CLIP. 1.0 = identical."""
    if not Path(reference_path).exists():
        return {"error": f"reference not found: {reference_path}"}
    if not Path(candidate_path).exists():
        return {"error": f"candidate not found: {candidate_path}"}
    try:
        a = _embed(reference_path)
        b = _embed(candidate_path)
        score = float((a @ b.T).item())
        # CLIP cosine of distinct images sits ~0.2-0.4; same scene ~0.7+.
        # Normalize to a friendlier 0..1 by clamping the bottom.
        adj = max(0.0, min(1.0, (score - 0.2) / 0.7))
        return {
            "score": round(adj, 3),
            "raw_cosine": round(score, 3),
            "reasoning": (
                "high visual similarity" if adj >= 0.75
                else "moderate similarity" if adj >= 0.5
                else "low similarity"
            ),
        }
    except Exception as e:
        return {"error": str(e)}


# Indonesian plate: 1-2 letters + 1-4 digits + 1-3 letters, e.g. "D 1234 ABC".
_PLATE_RE = re.compile(r"\b([A-Z]{1,2})\s?([0-9]{1,4})\s?([A-Z]{1,3})\b")


@mcp.tool()
def read_plate(image_path: str) -> dict[str, Any]:
    """Run OCR and try to extract an Indonesian license plate."""
    if not Path(image_path).exists():
        return {"error": f"not found: {image_path}"}
    try:
        result = _ocr().ocr(image_path, cls=True)
        raw_lines: list[str] = []
        confidences: list[float] = []
        for page in result or []:
            for _bbox, (txt, conf) in (page or []):
                raw_lines.append(txt)
                confidences.append(float(conf))

        joined = " ".join(raw_lines).upper()
        m = _PLATE_RE.search(joined)
        plate = f"{m.group(1)} {m.group(2)} {m.group(3)}" if m else None
        return {
            "plate": plate,
            "raw": raw_lines,
            "confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
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
