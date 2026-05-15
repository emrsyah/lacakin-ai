"""Stage-2 vision reasoning: send candidate image + case context to Claude
Sonnet, return structured JSON the worker posts into the group."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from mcp.vision_mcp import fixture_cache

RESPONSE_KEYS = {
    "match_confidence", "matches", "mismatches",
    "suspicious_signals", "narrative", "route_to",
}

SYSTEM_PROMPTS = {
    "cctv": (
        "Anda adalah analis CCTV untuk kasus motor hilang di Bandung. "
        "Analisa gambar dengan teliti. Cari motor yang cocok dengan konteks. "
        "Jelaskan apa yang Anda lihat dengan SPESIFIK (warna, plat, ciri unik, "
        "pengendara). Output JSON ketat sesuai schema. Bahasa Indonesia."
    ),
    "marketplace": (
        "Anda adalah analis listing marketplace untuk kasus motor hilang. "
        "Cari sinyal mencurigakan: plat dikaburkan, harga di bawah pasar, "
        "akun baru, foto reupload. Output JSON ketat. Bahasa Indonesia."
    ),
    "social": (
        "Anda adalah analis sosial media untuk motor hilang. Periksa foto, "
        "deskripsi, dan profil penjual. Output JSON ketat. Bahasa Indonesia."
    ),
}


def _schema_prompt() -> str:
    return (
        "Balas HANYA JSON valid dengan format:\n"
        '{"match_confidence": 0.0..1.0,\n'
        ' "matches": ["bullet apa yang cocok"],\n'
        ' "mismatches": ["bullet apa yang tidak cocok"],\n'
        ' "suspicious_signals": ["sinyal mencurigakan"],\n'
        ' "narrative": "1-2 kalimat utama untuk dibaca user",\n'
        ' "route_to": [{"agent": "cadang|pasar|mata|sosmed", '
        '"reason": "kenapa agent itu harus pivot"}]}\n'
        "Jangan ada teks lain di luar JSON."
    )


def reason_about_candidate(
    image_path: str, context_md: str, source_type: str
) -> dict[str, Any]:
    """Returns the structured response. Hits fixture cache first."""
    if not Path(image_path).exists():
        return {"error": f"not found: {image_path}"}

    cached = fixture_cache.lookup(image_path)
    if cached is not None:
        return cached

    if source_type not in SYSTEM_PROMPTS:
        return {"error": f"unknown source_type {source_type}"}

    try:
        from openai import OpenAI
    except ImportError:
        return {"error": "openai SDK not installed"}

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"error": "OPENROUTER_API_KEY not set"}

    img_bytes = Path(image_path).read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode()
    media_type = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"

    try:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        resp = client.chat.completions.create(
            model="anthropic/claude-sonnet-4-6",
            max_tokens=600,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPTS[source_type]},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {
                            "url": f"data:{media_type};base64,{img_b64}"}},
                        {"type": "text", "text": (
                            f"Konteks kasus:\n{context_md}\n\n"
                            "Analisa gambar di atas. " + _schema_prompt()
                        )},
                    ],
                },
            ],
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```").rstrip("`").strip()
        data = json.loads(text)
        for k in ("matches", "mismatches", "suspicious_signals", "route_to"):
            data.setdefault(k, [])
        data.setdefault("match_confidence", 0.0)
        data.setdefault("narrative", "")
        return data
    except json.JSONDecodeError as e:
        return {"error": f"sonnet returned non-JSON: {e}", "raw": text[:500]}
    except Exception as e:
        return {"error": str(e)}
