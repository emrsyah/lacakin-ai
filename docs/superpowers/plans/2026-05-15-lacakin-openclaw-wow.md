# Lacakin OpenClaw — Wow-Factor Build Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the existing Lacakin OpenClaw scaffold into a multi-bot Telegram war-room demo with vision-reasoning, agent-to-agent coordination, distinct personas, and a 90-second judge-stunning demo flow, per the approved design at `docs/plans/2026-05-15-lacakin-openclaw-wow-design.md`.

**Architecture:** 7 Telegram bots (one per agent) bound to a single OpenClaw gateway, broadcasting into one group chat. Workers tick on demo-mode short cadence (30/45/60s). Each candidate image passes a CLIP cheap filter, then a Claude Sonnet vision call that produces verbal reasoning + optional `route_to` for visible @-mention coordination. Workers DM each other via OpenClaw's `tools.agentToAgent` with TTL + cycle protection.

**Tech Stack:** OpenClaw gateway, Python 3.12 MCP servers (Playwright, CLIP via open_clip, PaddleOCR, Anthropic Sonnet vision, SQLite), Telegram Bot API (7 bots), Anthropic API (Haiku for ticks, Opus for orchestrator, Sonnet for vision).

**Existing scaffold to build on (do not recreate):**
- `openclaw/agents.json5` — agent list, MCP wiring (will modify)
- `openclaw/prompts/{heartbeat_cctv,heartbeat_marketplace,heartbeat_parts,main_system,report_system}.md` (will modify)
- `mcp/browser_mcp/{server.py,cameras.json}` — Playwright CCTV + marketplace tools
- `mcp/vision_mcp/server.py` — CLIP `match_image` + PaddleOCR `read_plate` (will extend)
- `mcp/db_mcp/{server.py,schema.sql}` — case + findings store (will extend with A2A inbox)
- `scripts/{setup_vps.sh,seed_demo.py}` (will extend)

---

## File Structure (delta)

**Create:**
- `openclaw/prompts/heartbeat_sosmed.md` — new agent
- `openclaw/prompts/polisi_system.md` — new agent
- `openclaw/prompts/A2A_PROTOCOL.md` — shared protocol doc included by every worker prompt
- `mcp/vision_mcp/sonnet_reason.py` — Sonnet vision call helper (kept separate from CLIP/OCR to isolate the API key dep)
- `mcp/vision_mcp/fixture_cache.py` — hash-keyed fixture cache for the staged demo image
- `mcp/a2a_mcp/{__init__.py,server.py,schema.sql}` — agent-to-agent inbox MCP (sits alongside db-mcp)
- `mcp/polisi_mcp/{__init__.py,server.py,template_laporan.md}` — police report template renderer
- `scripts/botfather_checklist.md` — manual setup steps for the 7 Telegram bots
- `scripts/serve_demo_assets.py` — local HTTP server for staged CCTV clip + fake Tokopedia
- `scripts/demo_dry_run.md` — pre-demo rehearsal checklist
- `tests/__init__.py`, `tests/conftest.py`
- `tests/test_a2a_protocol.py`
- `tests/test_fixture_cache.py`
- `tests/test_sonnet_reason_contract.py`
- `tests/test_env_interpolation.py`
- `.env.demo`, `.env.prod` — heartbeat profile envs
- `demo_assets/cctv_clips/dago-simpang.html` — pre-recorded clip wrapper
- `demo_assets/fake_listings/tokopedia-honda-beat-merah.html` (already partially exists in `~/lacakin/shared/fake_listings/` per seed_demo.py — promote it here)
- `demo_assets/reference/honda-beat-reference.jpg` (placeholder — replace with real photo before demo)

**Modify:**
- `openclaw/agents.json5` — add 6 telegram accounts, 7 bindings, broadcast block, agentToAgent allowlist, env-interpolated heartbeats, identity blocks, mention patterns, sosmed + polisi agents, mcp pointers for a2a-mcp + polisi-mcp
- `openclaw/prompts/heartbeat_cctv.md` — add Stage-1/Stage-2 vision pipeline, A2A inbox check, `route_to` emission, persona voice (short observational)
- `openclaw/prompts/heartbeat_marketplace.md` — same shape, market-trader persona voice
- `openclaw/prompts/heartbeat_parts.md` — same shape, technical persona voice
- `openclaw/prompts/main_system.md` — orchestrator's cold-start swarm-awakening behavior (initial A2A pings), persona voice (warm/calm)
- `openclaw/prompts/report_system.md` — periodic + on-demand modes, neutral persona voice
- `mcp/vision_mcp/server.py` — register `reason_about_candidate` tool (delegates to `sonnet_reason.py`, checks `fixture_cache.py` first)
- `mcp/db_mcp/schema.sql` — add `a2a_messages` table (or move to a2a-mcp; chosen: separate module for clarity)
- `requirements.txt` — add `anthropic>=0.40` for Sonnet vision SDK (CLIP/OCR already there)
- `scripts/setup_vps.sh` — install steps for new mcp modules, env profile sourcing

**Decomposition rationale:**
- A2A is its own MCP because it has its own DB table + own tool surface and is referenced by every worker.
- Sonnet vision is split from CLIP into its own file because it has an external API dep (the Anthropic SDK). Keeps CLIP+OCR usable in tests without a key.
- Fixture cache is its own file so the demo-staging logic doesn't leak into core vision code.
- Polisi-AI gets its own MCP (template renderer) — keeps the agent purely declarative.

---

## Chunk 1: Foundations (env profiles + tests harness)

### Task 1: Test harness + conftest

**Files:**
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`
- Modify: `requirements.txt` (add pytest deps)

- [ ] **Step 1: Add dev deps**

Append to `requirements.txt`:
```
pytest>=8.0
pytest-asyncio>=0.23
```

- [ ] **Step 2: Create conftest**

`tests/conftest.py`:

```python
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
```

Add `[tool.pytest.ini_options]` to `pyproject.toml` if present, otherwise create `pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
markers =
    needs_api: requires ANTHROPIC_API_KEY to be set
```

- [ ] **Step 3: Smoke-run pytest with no tests**

```bash
pip install -r requirements.txt
pytest -v
```

Expected: `no tests ran` (no error).

- [ ] **Step 4: Commit**

```bash
git add tests/__init__.py tests/conftest.py requirements.txt pytest.ini
git commit -m "chore(tests): pytest harness with offline-first fixtures"
```

---

### Task 2: Env profile interpolation

OpenClaw `agents.json5` already supports `${ENV_VAR}` interpolation. We add a wrapper script that sources the right `.env.<profile>` before launching the gateway.

**Files:**
- Create: `.env.demo`, `.env.prod`
- Create: `scripts/start_gateway.sh`
- Test: `tests/test_env_interpolation.py`

- [ ] **Step 1: Write the failing test**

`tests/test_env_interpolation.py`:

```python
"""Verify the gateway start script sources the right env file and exports the
heartbeat vars OpenClaw's agents.json5 expects."""
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_demo_env_exports_expected_keys():
    out = subprocess.check_output(
        ["bash", "-c", "set -a; source .env.demo; set +a; env"],
        cwd=REPO, text=True,
    )
    env = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    assert env["HB_CCTV"] == "30s"
    assert env["HB_MARKETPLACE"] == "45s"
    assert env["HB_PARTS"] == "60s"
    assert env["HB_SOSMED"] == "45s"
    assert env["HB_REPORT"] == "90s"
    assert env["LACAKIN_PROFILE"] == "demo"


def test_prod_env_exports_expected_keys():
    out = subprocess.check_output(
        ["bash", "-c", "set -a; source .env.prod; set +a; env"],
        cwd=REPO, text=True,
    )
    env = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    assert env["HB_CCTV"] == "5m"
    assert env["HB_REPORT"] == "30m"
    assert env["LACAKIN_PROFILE"] == "prod"
```

- [ ] **Step 2: Run → fails**

```bash
pytest tests/test_env_interpolation.py -v
```

Expected: FAIL (`.env.demo` and `.env.prod` don't exist).

- [ ] **Step 3: Create env files**

`.env.demo`:
```
LACAKIN_PROFILE=demo
HB_CCTV=30s
HB_MARKETPLACE=45s
HB_PARTS=60s
HB_SOSMED=45s
HB_REPORT=90s
```

`.env.prod`:
```
LACAKIN_PROFILE=prod
HB_CCTV=5m
HB_MARKETPLACE=10m
HB_PARTS=15m
HB_SOSMED=10m
HB_REPORT=30m
```

`scripts/start_gateway.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:-demo}"
ENV_FILE=".env.${PROFILE}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "missing $ENV_FILE" >&2; exit 1
fi
set -a
source "$ENV_FILE"
source .env       # ANTHROPIC_API_KEY, TELEGRAM_TOKEN_*, LACAKIN_GROUP_ID
set +a
echo "Starting gateway with profile=$LACAKIN_PROFILE, HB_CCTV=$HB_CCTV"
exec openclaw start --config openclaw/agents.json5
```

```bash
chmod +x scripts/start_gateway.sh
```

- [ ] **Step 4: Run → passes**

```bash
pytest tests/test_env_interpolation.py -v
```

- [ ] **Step 5: Commit**

```bash
git add .env.demo .env.prod scripts/start_gateway.sh tests/test_env_interpolation.py
git commit -m "feat: demo/prod heartbeat profiles via env interpolation"
```

---

## Chunk 2: Vision-reasoning pipeline

### Task 3: Fixture cache (Risk 4 mitigation, built early so it's testable)

The cache maps `sha256(image)` → cached Sonnet response. When the staged demo image is requested, we serve the fixture without burning a real Sonnet call.

**Files:**
- Create: `mcp/vision_mcp/fixture_cache.py`
- Create: `mcp/vision_mcp/fixtures/` (directory, gitkeep)
- Test: `tests/test_fixture_cache.py`

- [ ] **Step 1: Write the failing test**

`tests/test_fixture_cache.py`:

```python
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
```

- [ ] **Step 2: Run → fails**

```bash
pytest tests/test_fixture_cache.py -v
```

- [ ] **Step 3: Implement**

`mcp/vision_mcp/fixture_cache.py`:

```python
"""Hash-keyed fixture cache for the staged demo CCTV image.

Pre-register the staged image + its expected Sonnet response. At demo time
the gateway hits the fixture instead of the real Sonnet API, so the T+0:35
moment fires deterministically and fast.

Real candidates (other CCTVs, real Tokopedia listings) bypass the cache and
hit Sonnet for real. We are NOT lying to judges — this is a demo reliability
shim. If asked, say so."""
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
```

`mcp/vision_mcp/fixtures/.gitkeep`: (empty file)

- [ ] **Step 4: Run → passes**

```bash
pytest tests/test_fixture_cache.py -v
```

- [ ] **Step 5: Commit**

```bash
git add mcp/vision_mcp/fixture_cache.py mcp/vision_mcp/fixtures/.gitkeep tests/test_fixture_cache.py
git commit -m "feat(vision): hash-keyed fixture cache for staged demo image"
```

---

### Task 4: Sonnet vision reasoner

**Files:**
- Create: `mcp/vision_mcp/sonnet_reason.py`
- Modify: `mcp/vision_mcp/server.py` (register `reason_about_candidate` tool)
- Test: `tests/test_sonnet_reason_contract.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add SDK**

Append to `requirements.txt`:
```
anthropic>=0.40
```

```bash
pip install -r requirements.txt
```

- [ ] **Step 2: Write the failing test**

The test verifies our **contract** (response shape, fixture-cache short-circuit), not Sonnet itself. Real Sonnet runs are gated behind `needs_api` marker.

`tests/test_sonnet_reason_contract.py`:

```python
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
    """The contract every consumer relies on. Add the keys workers prompt
    against — if this changes, prompts break."""
    expected = {"match_confidence", "matches", "mismatches",
                "suspicious_signals", "narrative", "route_to"}
    assert sonnet_reason.RESPONSE_KEYS == expected


@pytest.mark.needs_api
def test_real_sonnet_call_smoke(tmp_path, has_anthropic_key):
    if not has_anthropic_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    # Use any small JPG — we only verify the response parses to our schema.
    img = tmp_path / "smoke.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF...")  # not a real image
    out = sonnet_reason.reason_about_candidate(
        image_path=str(img), context_md="motor merah", source_type="cctv"
    )
    # Either parses to schema OR returns {"error": ...} — both are acceptable
    # contract responses. The point is: no exceptions, always a dict.
    assert isinstance(out, dict)
```

- [ ] **Step 3: Run → fails**

```bash
pytest tests/test_sonnet_reason_contract.py -v -m "not needs_api"
```

- [ ] **Step 4: Implement**

`mcp/vision_mcp/sonnet_reason.py`:

```python
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
        from anthropic import Anthropic
    except ImportError:
        return {"error": "anthropic SDK not installed"}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set"}

    img_bytes = Path(image_path).read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode()
    media_type = "image/jpeg" if image_path.lower().endswith((".jpg",".jpeg")) else "image/png"

    try:
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=SYSTEM_PROMPTS[source_type],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64",
                        "media_type": media_type, "data": img_b64}},
                    {"type": "text", "text": (
                        f"Konteks kasus:\n{context_md}\n\n"
                        "Analisa gambar di atas. " + _schema_prompt()
                    )},
                ],
            }],
        )
        text = resp.content[0].text.strip()
        # Strip accidental code fences just in case.
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```").rstrip("`").strip()
        data = json.loads(text)
        # Backfill missing keys so workers can rely on the schema.
        for k in ("matches", "mismatches", "suspicious_signals", "route_to"):
            data.setdefault(k, [])
        data.setdefault("match_confidence", 0.0)
        data.setdefault("narrative", "")
        return data
    except json.JSONDecodeError as e:
        return {"error": f"sonnet returned non-JSON: {e}", "raw": text[:500]}
    except Exception as e:
        return {"error": str(e)}
```

`mcp/vision_mcp/server.py` — register the tool. Append:

```python
from mcp.vision_mcp.sonnet_reason import reason_about_candidate as _reason


@mcp.tool()
def reason_about_candidate(image_path: str, context_md: str,
                            source_type: str) -> dict[str, Any]:
    """Stage-2 vision reasoning. Call ONLY on candidates with clip_match >= 0.7.

    Returns structured JSON: match_confidence, matches[], mismatches[],
    suspicious_signals[], narrative, route_to[]. Post `narrative` + bullets
    into the group; emit a @-mention for each route_to entry."""
    return _reason(image_path=image_path, context_md=context_md, source_type=source_type)
```

- [ ] **Step 5: Run → passes**

```bash
pytest tests/test_sonnet_reason_contract.py -v -m "not needs_api"
```

- [ ] **Step 6: Commit**

```bash
git add mcp/vision_mcp/sonnet_reason.py mcp/vision_mcp/server.py \
        requirements.txt tests/test_sonnet_reason_contract.py
git commit -m "feat(vision): sonnet vision reasoning + fixture-cache short-circuit"
```

---

## Chunk 3: A2A protocol

### Task 5: A2A inbox MCP

OpenClaw's `tools.agentToAgent` handles the *transport*. We add a small SQLite-backed inbox so workers can persist TTL + chain_id + cycle protection across heartbeat ticks.

**Files:**
- Create: `mcp/a2a_mcp/__init__.py` (empty)
- Create: `mcp/a2a_mcp/schema.sql`
- Create: `mcp/a2a_mcp/server.py`
- Test: `tests/test_a2a_protocol.py`

- [ ] **Step 1: Schema**

`mcp/a2a_mcp/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS a2a_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id     TEXT NOT NULL,        -- UUID, identifies a pivot chain
    case_id      TEXT NOT NULL,
    from_agent   TEXT NOT NULL,
    to_agent     TEXT NOT NULL,
    reason       TEXT NOT NULL,
    payload_json TEXT NOT NULL,        -- arbitrary JSON the receiver consumes
    ttl_ticks    INTEGER NOT NULL,     -- decremented by receiver each tick
    created_at   TEXT NOT NULL,
    consumed_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_a2a_inbox ON a2a_messages(to_agent, consumed_at);
CREATE INDEX IF NOT EXISTS idx_a2a_chain ON a2a_messages(chain_id);
```

- [ ] **Step 2: Write the failing test**

`tests/test_a2a_protocol.py`:

```python
import pytest
from mcp.a2a_mcp.server import (
    send, list_inbox, consume, ttl_decrement, cycle_check,
)


def test_send_and_receive(tmp_lacakin):
    chain_id = send(case_id="c1", from_agent="mata", to_agent="cadang",
                    reason="motor menuju selatan", payload={"area": "Buah Batu"})
    assert isinstance(chain_id, str) and len(chain_id) > 0
    msgs = list_inbox(to_agent="cadang")
    assert len(msgs) == 1
    assert msgs[0]["from_agent"] == "mata"
    assert msgs[0]["reason"] == "motor menuju selatan"
    assert msgs[0]["ttl_ticks"] == 2  # default TTL


def test_consume_marks_delivered(tmp_lacakin):
    send(case_id="c1", from_agent="mata", to_agent="cadang", reason="x", payload={})
    msgs = list_inbox(to_agent="cadang")
    consume(message_ids=[msgs[0]["id"]])
    assert list_inbox(to_agent="cadang") == []


def test_cycle_check_blocks_same_chain_to_origin(tmp_lacakin):
    chain_id = send(case_id="c1", from_agent="mata", to_agent="cadang",
                    reason="r", payload={})
    # cadang tries to send back to mata with the same chain — should be blocked.
    assert cycle_check(chain_id=chain_id, to_agent="mata") is True
    # cadang sending to pasar on the same chain is fine.
    assert cycle_check(chain_id=chain_id, to_agent="pasar") is False


def test_ttl_decrements_and_expires(tmp_lacakin):
    send(case_id="c1", from_agent="mata", to_agent="cadang",
         reason="r", payload={}, ttl_ticks=1)
    msgs = list_inbox(to_agent="cadang")
    consume(message_ids=[msgs[0]["id"]])
    # next tick: TTL would have been 0, message already consumed.
    # The test below is for messages NOT consumed yet (e.g. agent skipped tick):
    mid = send(case_id="c1", from_agent="mata", to_agent="cadang",
               reason="r2", payload={}, ttl_ticks=2)
    ttl_decrement(to_agent="cadang")
    msgs = list_inbox(to_agent="cadang")
    assert msgs[0]["ttl_ticks"] == 1
    ttl_decrement(to_agent="cadang")
    # Now TTL=0 → expired, list_inbox excludes it.
    assert list_inbox(to_agent="cadang") == []
```

- [ ] **Step 3: Run → fails**

- [ ] **Step 4: Implement**

`mcp/a2a_mcp/server.py`:

```python
"""Agent-to-agent inbox MCP. Persists pivot requests with TTL + chain_id so
workers survive heartbeats and can't form cycles.

Two layers same as db_mcp: pure functions (testable) + @tool wrappers."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(os.environ.get("LACAKIN_DB", str(Path.home() / "lacakin" / "lacakin.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
SCHEMA = (Path(__file__).parent / "schema.sql").read_text()

_conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
_conn.row_factory = sqlite3.Row
_conn.executescript(SCHEMA)

mcp = FastMCP("a2a-mcp")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def send(case_id: str, from_agent: str, to_agent: str, reason: str,
         payload: dict, ttl_ticks: int = 2,
         chain_id: str | None = None) -> str:
    cid = chain_id or str(uuid.uuid4())
    if cycle_check(chain_id=cid, to_agent=to_agent):
        # Drop silently — cycle would form. Return chain_id anyway so caller
        # doesn't crash; they can poll status if needed.
        return cid
    _conn.execute(
        """INSERT INTO a2a_messages(chain_id, case_id, from_agent, to_agent,
                                    reason, payload_json, ttl_ticks, created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (cid, case_id, from_agent, to_agent, reason,
         json.dumps(payload), ttl_ticks, _now()),
    )
    return cid


def list_inbox(to_agent: str) -> list[dict[str, Any]]:
    rows = _conn.execute(
        """SELECT * FROM a2a_messages
           WHERE to_agent = ? AND consumed_at IS NULL AND ttl_ticks > 0
           ORDER BY created_at""",
        (to_agent,),
    ).fetchall()
    return [{**dict(r), "payload": json.loads(r["payload_json"])} for r in rows]


def consume(message_ids: list[int]) -> int:
    if not message_ids:
        return 0
    q = ",".join("?" * len(message_ids))
    cur = _conn.execute(
        f"UPDATE a2a_messages SET consumed_at = ? WHERE id IN ({q})",
        (_now(), *message_ids),
    )
    return cur.rowcount


def ttl_decrement(to_agent: str) -> int:
    """Called by a worker at the END of its tick on its own inbox: decrement
    TTL of un-consumed messages. Messages reaching TTL 0 are excluded by
    list_inbox on the next call."""
    cur = _conn.execute(
        """UPDATE a2a_messages
           SET ttl_ticks = ttl_ticks - 1
           WHERE to_agent = ? AND consumed_at IS NULL""",
        (to_agent,),
    )
    return cur.rowcount


def cycle_check(chain_id: str, to_agent: str) -> bool:
    """True if sending this chain to `to_agent` would form a cycle."""
    row = _conn.execute(
        "SELECT 1 FROM a2a_messages WHERE chain_id = ? AND from_agent = ?",
        (chain_id, to_agent),
    ).fetchone()
    return row is not None


# ── @tool wrappers ─────────────────────────────────────────────────────────

@mcp.tool()
def a2a_send(case_id: str, from_agent: str, to_agent: str, reason: str,
              payload: dict | None = None, ttl_ticks: int = 2,
              chain_id: str | None = None) -> dict:
    """Send a pivot request to another agent. Returns the chain_id."""
    cid = send(case_id, from_agent, to_agent, reason, payload or {},
               ttl_ticks=ttl_ticks, chain_id=chain_id)
    return {"chain_id": cid}


@mcp.tool()
def a2a_inbox(to_agent: str) -> list[dict]:
    """List pending pivot requests for an agent. Call this FIRST every tick."""
    return list_inbox(to_agent)


@mcp.tool()
def a2a_consume(message_ids: list[int]) -> dict:
    """Mark messages as handled. Call after acting on them."""
    return {"updated": consume(message_ids)}


@mcp.tool()
def a2a_tick_done(to_agent: str) -> dict:
    """Call at the END of every tick to decrement TTL of unconsumed messages."""
    return {"decremented": ttl_decrement(to_agent)}


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 5: Run → passes**

```bash
pytest tests/test_a2a_protocol.py -v
```

- [ ] **Step 6: Commit**

```bash
git add mcp/a2a_mcp/ tests/test_a2a_protocol.py
git commit -m "feat(a2a): inbox MCP with TTL + chain cycle protection"
```

---

### Task 6: Shared A2A protocol prompt

Every worker prompt needs the same A2A discipline (check inbox first, consume, emit ttl_tick_done at end). DRY by extracting it.

**Files:**
- Create: `openclaw/prompts/A2A_PROTOCOL.md`

- [ ] **Step 1: Write the file**

`openclaw/prompts/A2A_PROTOCOL.md`:

```markdown
# A2A Protocol — every worker reads this every tick

## At the START of every tick

1. Call `a2a_inbox(to_agent=<your_agent_id>)`. If non-empty:
   - These are pivot requests from other agents (or the user via @-mention).
   - Treat them as **the priority for THIS tick**, overriding your default plan.
   - For each message: apply its `reason` and `payload` to scope your sweep.
   - Call `a2a_consume(message_ids=[...])` once you've integrated them.

## When you decide another agent should pivot

If your Sonnet vision call returns a non-empty `route_to`:

1. For each `{agent, reason}` in `route_to`:
   - Generate (or carry forward) `chain_id`.
   - Call `a2a_send(case_id=<...>, from_agent=<you>, to_agent=<agent>,
     reason=<reason>, payload=<your sweep context>, chain_id=<...>)`.
2. Also append the visible `@<agent> — <reason>` line to your group post.

## At the END of every tick (no exceptions)

- Call `a2a_tick_done(to_agent=<your_agent_id>)`.
  This decrements TTL of any inbox messages that weren't relevant this tick,
  so they don't re-fire forever.

## Hard rules

- Never `a2a_send` to yourself.
- Never `a2a_send` with the same `chain_id` to an agent already in that chain
  (the MCP enforces this — it'll drop silently — but don't generate them).
- The orchestrator alone can issue `close_case` actions. Workers never.
```

- [ ] **Step 2: Commit**

```bash
git add openclaw/prompts/A2A_PROTOCOL.md
git commit -m "docs(prompts): shared A2A protocol included by every worker"
```

---

## Chunk 4: Multi-bot Telegram setup

### Task 7: BotFather checklist (manual)

**Files:**
- Create: `scripts/botfather_checklist.md`

- [ ] **Step 1: Write the checklist**

`scripts/botfather_checklist.md`:

```markdown
# BotFather setup — do this BEFORE running the gateway

Open @BotFather on Telegram. For each row below:
1. `/newbot` → name → username (suffix `_bot`)
2. Copy the token into `.env` as `TELEGRAM_TOKEN_<KEY>`
3. `/setprivacy` → Disable (so bots can read all group messages, not just mentions)
4. `/setuserpic` → upload avatar
5. `/setdescription` → set about text
6. `/setname` → set display name

| KEY            | Username            | Display name           | Emoji | About text |
|----------------|---------------------|------------------------|-------|------------|
| ORCHESTRATOR   | @lacakin_bot        | Lacakin                | 🛵    | Asisten investigasi motor hilang. Saya yang koordinasi tim. |
| CCTV           | @mata_bandung_bot   | Mata Bandung           | 👁️    | Saya mengawasi CCTV pelindung. Tick tiap 30 detik. |
| MARKETPLACE    | @pasar_bot          | Pemantau Pasar         | 🛒    | Saya cek Tokopedia + OLX. Listing motor curiga? Saya laporkan. |
| PARTS          | @cadang_bot         | Pemburu Suku Cadang    | 🔧    | Motor dijual potong? Saya cari spare part-nya. |
| SOSMED         | @sosmed_bot         | Pengintai Sosmed       | 📱    | Marketplace Facebook + Instagram. Saya stalker yang baik. |
| POLISI         | @polisi_ai_bot      | Polisi-AI              | 👮    | Saya bantu draft laporan polisi. Bukan polisi sungguhan. |
| REPORT         | @laporan_bot        | Pencatat Laporan       | 📋    | Saya rangkum semua temuan. Tiap 90 detik / on-demand. |

(Usernames must be globally unique on Telegram. If `@lacakin_bot` is taken,
pick `@lacakin_demo_bot` etc. and update bindings to match.)

## After all 7 are created

1. Create a new Telegram **group** "Lacakin · Demo".
2. Add all 7 bots. Promote each one to **admin** (settings → Administrators).
   Admin permissions needed: send messages, edit messages (for pinned summary).
3. Send any message in the group, then run:
   ```bash
   curl "https://api.telegram.org/bot$TELEGRAM_TOKEN_ORCHESTRATOR/getUpdates"
   ```
   Find `"chat":{"id":-100xxxxxxx, ...}` and put that into `.env` as
   `LACAKIN_GROUP_ID`.
4. Confirm: each bot's `getMe` returns its own username:
   ```bash
   for k in ORCHESTRATOR CCTV MARKETPLACE PARTS SOSMED POLISI REPORT; do
     tok=$(printenv "TELEGRAM_TOKEN_$k")
     echo "$k: $(curl -s https://api.telegram.org/bot$tok/getMe | jq -r .result.username)"
   done
   ```
```

- [ ] **Step 2: Commit**

```bash
git add scripts/botfather_checklist.md
git commit -m "docs: BotFather setup checklist for 7 telegram bots"
```

---

### Task 8: agents.json5 — multi-bot bindings + broadcast + identities

This is the biggest single config change. Replace the existing `agents.json5` wholesale rather than surgically editing.

**Files:**
- Modify: `openclaw/agents.json5` (full rewrite)

- [ ] **Step 1: Rewrite agents.json5**

```json5
// OpenClaw gateway config for Lacakin — wow-factor edition.
//
// Field-name notes (verified against OpenClaw docs 2026-05-15):
//   - Telegram token field is `botToken`, NOT `token`.
//   - `promptFile` is NOT a real field. Agents read their system + heartbeat
//     prompts from their own `workspace` via the `read` tool. setup_vps.sh
//     distributes the .md files into each workspace before gateway boot.
//   - `mcp.servers.<name>: {command, args, env?}` is documented verbatim.
{
  channels: {
    telegram: {
      enabled: true,
      accounts: {
        orchestrator: { botToken: "${TELEGRAM_TOKEN_ORCHESTRATOR}" },
        cctv:         { botToken: "${TELEGRAM_TOKEN_CCTV}" },
        marketplace:  { botToken: "${TELEGRAM_TOKEN_MARKETPLACE}" },
        parts:        { botToken: "${TELEGRAM_TOKEN_PARTS}" },
        sosmed:       { botToken: "${TELEGRAM_TOKEN_SOSMED}" },
        polisi:       { botToken: "${TELEGRAM_TOKEN_POLISI}" },
        report:       { botToken: "${TELEGRAM_TOKEN_REPORT}" },
      },
    },
  },

  bindings: [
    { agentId: "orchestrator", match: { channel: "telegram", accountId: "orchestrator" } },
    { agentId: "cctv-bandung", match: { channel: "telegram", accountId: "cctv" } },
    { agentId: "marketplace",  match: { channel: "telegram", accountId: "marketplace" } },
    { agentId: "parts",        match: { channel: "telegram", accountId: "parts" } },
    { agentId: "sosmed",       match: { channel: "telegram", accountId: "sosmed" } },
    { agentId: "polisi",       match: { channel: "telegram", accountId: "polisi" } },
    { agentId: "report",       match: { channel: "telegram", accountId: "report" } },
  ],

  broadcast: {
    "${LACAKIN_GROUP_ID}": [
      "cctv-bandung", "marketplace", "parts",
      "sosmed", "polisi", "report",
      // orchestrator deliberately NOT in broadcast — it posts via its own bot
      // by direct invocation only (controlled by SYSTEM.md in its workspace).
    ],
  },

  tools: {
    agentToAgent: {
      enabled: true,
      allow: ["orchestrator","cctv-bandung","marketplace","parts","sosmed","polisi","report"],
    },
  },

  agents: {
    defaults: {
      sandbox: { mode: "non-main", scope: "session" },
      heartbeat: { every: "0m" },
      model: "anthropic/claude-haiku-4-5-20251001",
    },

    list: [
      {
        id: "orchestrator",
        name: "Lacakin",
        workspace: "~/lacakin/workspace-main",
        model: "anthropic/claude-opus-4-7",
        thinkingDefault: "high",
        sandbox: { mode: "off" },
        identity: { name: "Lacakin", emoji: "🛵", theme: "calm investigator" },
        groupChat: { mentionPatterns: ["@lacakin_bot","@lacakin"] },
        tools: {
          allow: ["read","write","edit","sessions_spawn","sessions_send","session_status","sessions_list"],
          deny: ["exec","browser"],
        },
        subagents: { allowAgents: ["cctv-bandung","marketplace","parts","sosmed","polisi","report"] },
        mcp: ["db-mcp","a2a-mcp"],
        // System prompt: tell the agent to load its real instructions from
        // SYSTEM.md (distributed by setup_vps.sh). One short directive keeps
        // the .json5 readable; prompt iteration happens in .md files.
        prompt: "Anda Lacakin. Sebelum merespons, baca file ./SYSTEM.md di workspace Anda untuk instruksi lengkap.",
      },

      {
        id: "cctv-bandung",
        workspace: "~/lacakin/workspace-cctv",
        identity: { name: "Mata Bandung", emoji: "👁️", theme: "lookout" },
        groupChat: { mentionPatterns: ["@mata_bandung_bot","@mata"] },
        sandbox: { mode: "all", scope: "agent" },
        tools: { allow: ["read","write","browser"], deny: ["exec","edit","apply_patch"] },
        mcp: ["browser-mcp","vision-mcp","db-mcp","a2a-mcp"],
        heartbeat: {
          every: "${HB_CCTV}",
          lightContext: true,
          isolatedSession: false,
          skipWhenBusy: true,
          // Pattern from OpenClaw docs example: short directive, files in workspace.
          prompt: "Run CCTV tick. Read ./A2A_PROTOCOL.md and ./HEARTBEAT.md for full instructions.",
          timeoutSeconds: 90,
        },
      },

      {
        id: "marketplace",
        workspace: "~/lacakin/workspace-marketplace",
        identity: { name: "Pemantau Pasar", emoji: "🛒", theme: "market trader" },
        groupChat: { mentionPatterns: ["@pasar_bot","@pasar"] },
        sandbox: { mode: "all", scope: "agent" },
        tools: { allow: ["read","write","browser"] },
        mcp: ["browser-mcp","vision-mcp","db-mcp","a2a-mcp"],
        heartbeat: { every: "${HB_MARKETPLACE}", lightContext: true,
          prompt: "Marketplace tick. Read ./A2A_PROTOCOL.md and ./HEARTBEAT.md.",
          timeoutSeconds: 90, skipWhenBusy: true },
      },

      {
        id: "parts",
        workspace: "~/lacakin/workspace-parts",
        identity: { name: "Pemburu Suku Cadang", emoji: "🔧", theme: "parts specialist" },
        groupChat: { mentionPatterns: ["@cadang_bot","@cadang"] },
        sandbox: { mode: "all", scope: "agent" },
        tools: { allow: ["read","write","browser"] },
        mcp: ["browser-mcp","vision-mcp","db-mcp","a2a-mcp"],
        heartbeat: { every: "${HB_PARTS}", lightContext: true,
          prompt: "Parts tick. Read ./A2A_PROTOCOL.md and ./HEARTBEAT.md.",
          timeoutSeconds: 120, skipWhenBusy: true },
      },

      {
        id: "sosmed",
        workspace: "~/lacakin/workspace-sosmed",
        identity: { name: "Pengintai Sosmed", emoji: "📱", theme: "social media stalker" },
        groupChat: { mentionPatterns: ["@sosmed_bot","@sosmed"] },
        sandbox: { mode: "all", scope: "agent" },
        tools: { allow: ["read","write","browser"] },
        mcp: ["browser-mcp","vision-mcp","db-mcp","a2a-mcp"],
        heartbeat: { every: "${HB_SOSMED}", lightContext: true,
          prompt: "Social media tick. Read ./A2A_PROTOCOL.md and ./HEARTBEAT.md.",
          timeoutSeconds: 90, skipWhenBusy: true },
      },

      {
        id: "polisi",
        workspace: "~/lacakin/workspace-polisi",
        identity: { name: "Polisi-AI", emoji: "👮", theme: "birokrat" },
        groupChat: { mentionPatterns: ["@polisi_ai_bot","@polisi"] },
        sandbox: { mode: "off" },
        tools: { allow: ["read","write"] },
        mcp: ["db-mcp","polisi-mcp"],
        prompt: "Anda Polisi-AI. Sebelum merespons, baca ./SYSTEM.md untuk instruksi lengkap.",
        // No heartbeat — invoked on-demand by orchestrator or @mention.
      },

      {
        id: "report",
        workspace: "~/lacakin/workspace-report",
        identity: { name: "Pencatat Laporan", emoji: "📋", theme: "neutral chronicler" },
        groupChat: { mentionPatterns: ["@laporan_bot","@laporan"] },
        model: "anthropic/claude-opus-4-7",   // smart synthesis worth opus
        sandbox: { mode: "off" },
        tools: { allow: ["read","write"] },
        mcp: ["db-mcp","a2a-mcp"],
        prompt: "Anda Pencatat Laporan. Sebelum merespons, baca ./SYSTEM.md untuk instruksi lengkap.",
        heartbeat: { every: "${HB_REPORT}", lightContext: false,
          prompt: "Generate periodic synthesis report. Read ./SYSTEM.md untuk instruksi lengkap.",
          timeoutSeconds: 60 },
      },
    ],
  },

  mcp: {
    servers: {
      "browser-mcp": { command: "python", args: ["-m","mcp.browser_mcp.server"], cwd: ".." },
      "vision-mcp":  { command: "python", args: ["-m","mcp.vision_mcp.server"],  cwd: ".." },
      "db-mcp":      { command: "python", args: ["-m","mcp.db_mcp.server"],      cwd: ".." },
      "a2a-mcp":     { command: "python", args: ["-m","mcp.a2a_mcp.server"],     cwd: ".." },
      "polisi-mcp":  { command: "python", args: ["-m","mcp.polisi_mcp.server"],  cwd: ".." },
    },
  },
}
```

- [ ] **Step 2: Add the prompt-distribution loop to `setup_vps.sh`**

Workers (heartbeat-driven) read `./HEARTBEAT.md` + `./A2A_PROTOCOL.md` from
their own workspace each tick. Non-heartbeat agents (orchestrator, polisi,
report) read `./SYSTEM.md`. We distribute prompts at setup time so the gateway
finds them at boot.

Append to `scripts/setup_vps.sh` (after the existing workspace-creation
block):

```bash
# ── Distribute prompts into each agent's workspace ─────────────────────────
echo "[7/7] Distributing prompts to agent workspaces"
mkdir -p ~/lacakin/workspace-{main,cctv,marketplace,parts,sosmed,polisi,report}

# A2A_PROTOCOL.md goes into every worker workspace (the heartbeat agents).
for w in cctv marketplace parts sosmed report; do
  cp openclaw/prompts/A2A_PROTOCOL.md ~/lacakin/workspace-$w/A2A_PROTOCOL.md
done

# Heartbeat prompts: one per worker, renamed to HEARTBEAT.md
cp openclaw/prompts/heartbeat_cctv.md         ~/lacakin/workspace-cctv/HEARTBEAT.md
cp openclaw/prompts/heartbeat_marketplace.md  ~/lacakin/workspace-marketplace/HEARTBEAT.md
cp openclaw/prompts/heartbeat_parts.md        ~/lacakin/workspace-parts/HEARTBEAT.md
cp openclaw/prompts/heartbeat_sosmed.md       ~/lacakin/workspace-sosmed/HEARTBEAT.md

# System prompts: orchestrator + polisi + report
cp openclaw/prompts/main_system.md   ~/lacakin/workspace-main/SYSTEM.md
cp openclaw/prompts/polisi_system.md ~/lacakin/workspace-polisi/SYSTEM.md
cp openclaw/prompts/report_system.md ~/lacakin/workspace-report/SYSTEM.md

# cctv-bandung also needs cameras.json next to it for the prompt to reference
cp mcp/browser_mcp/cameras.json ~/lacakin/workspace-cctv/cameras.json

# Re-symlink shared/ into each worker workspace
for w in main cctv marketplace parts sosmed polisi report; do
  ln -sfn ~/lacakin/shared ~/lacakin/workspace-$w/shared
done

echo "Prompts distributed. Re-run this script whenever prompts change."
```

Run it:

```bash
bash scripts/setup_vps.sh
ls ~/lacakin/workspace-cctv/    # should show HEARTBEAT.md, A2A_PROTOCOL.md, cameras.json, shared/
ls ~/lacakin/workspace-main/    # should show SYSTEM.md, shared/
```

- [ ] **Step 3: Validate the JSON5 parses**

```bash
python -c "import json5; json5.load(open('openclaw/agents.json5'))"
```

(If `json5` isn't installed: `pip install pyjson5` or strip the comments and parse with `json`.)

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add openclaw/agents.json5 scripts/setup_vps.sh
git commit -m "feat(gateway): multi-bot bindings, broadcast, prompt distribution"
```

---

## Chunk 5: New agents — Sosmed + Polisi

### Task 9: Polisi MCP (police report template renderer)

**Files:**
- Create: `mcp/polisi_mcp/__init__.py` (empty)
- Create: `mcp/polisi_mcp/template_laporan.md`
- Create: `mcp/polisi_mcp/server.py`

- [ ] **Step 1: Template**

`mcp/polisi_mcp/template_laporan.md`:

```markdown
# LAPORAN KEHILANGAN KENDARAAN BERMOTOR
_Draft otomatis · bukan dokumen resmi · diserahkan ke kantor polisi terdekat_

**Pelapor:** {pelapor_nama}
**Tanggal lapor:** {tanggal}
**Kepada:** Polsek/Polres terdekat

## Identitas Kendaraan
- Jenis: {motor_jenis}
- Merk/Model/Tahun: {merk_model_tahun}
- Warna: {warna}
- Nomor polisi: {plat}
- Ciri khusus: {ciri_unik}

## Kronologi
Pada hari {hari_kejadian} jam {jam_kejadian}, kendaraan terakhir terlihat
di {lokasi_terakhir}. {kronologi_singkat}

## Lampiran (jika ada)
- Foto motor
- Screenshot temuan dari sistem Lacakin (CCTV / marketplace)

## Pernyataan
Demikian laporan ini saya buat dengan sebenar-benarnya untuk dapat ditindaklanjuti.

Hormat saya,
{pelapor_nama}
```

- [ ] **Step 2: Server**

`mcp/polisi_mcp/server.py`:

```python
"""Polisi-MCP — renders the laporan template from case context."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

TEMPLATE = (Path(__file__).parent / "template_laporan.md").read_text()
mcp = FastMCP("polisi-mcp")


@mcp.tool()
def draft_laporan(
    pelapor_nama: str,
    motor_jenis: str,
    merk_model_tahun: str,
    warna: str,
    plat: str,
    ciri_unik: list[str],
    lokasi_terakhir: str,
    hari_kejadian: str,
    jam_kejadian: str,
    kronologi_singkat: str = "",
) -> dict[str, Any]:
    """Render the laporan template with the provided case fields.
    Returns {markdown: str}. Polisi-AI agent posts this verbatim in the group."""
    rendered = TEMPLATE.format(
        pelapor_nama=pelapor_nama or "(belum diisi)",
        tanggal=datetime.now().strftime("%d %B %Y"),
        motor_jenis=motor_jenis,
        merk_model_tahun=merk_model_tahun,
        warna=warna,
        plat=plat,
        ciri_unik=", ".join(ciri_unik) if ciri_unik else "(tidak ada)",
        lokasi_terakhir=lokasi_terakhir,
        hari_kejadian=hari_kejadian,
        jam_kejadian=jam_kejadian,
        kronologi_singkat=kronologi_singkat or
            "Motor diketahui hilang setelah pemilik kembali ke lokasi parkir.",
    )
    return {"markdown": rendered}


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 3: Smoke**

```bash
python -c "
from mcp.polisi_mcp.server import draft_laporan
print(draft_laporan(pelapor_nama='Budi', motor_jenis='Motor Bebek',
    merk_model_tahun='Honda Beat 2022', warna='Merah-Hitam', plat='D 1234 ABC',
    ciri_unik=['Stiker MotoGP'], lokasi_terakhir='Dago',
    hari_kejadian='Senin', jam_kejadian='14:00')['markdown'][:300])
"
```

Expected: rendered markdown starts with `# LAPORAN KEHILANGAN...`.

- [ ] **Step 4: Commit**

```bash
git add mcp/polisi_mcp/
git commit -m "feat(polisi): template renderer MCP"
```

---

### Task 10: Polisi-AI agent prompt

**Files:**
- Create: `openclaw/prompts/polisi_system.md`

- [ ] **Step 1: Write the prompt**

```markdown
# Polisi-AI — `polisi`

Anda **Polisi-AI**. Anda BUKAN polisi sungguhan. Tugas Anda: bantu korban
draft laporan kehilangan motor dalam format yang siap diserahkan ke Polsek.

## Gaya bicara

Bahasa Indonesia formal, birokratis, ringkas. Selalu mulai post di grup
dengan "Berdasarkan data kasus..." atau "Mengacu pada konteks...". Selalu
akhiri dengan disclaimer satu baris: "_Catatan: dokumen ini adalah draft
otomatis dan bukan laporan polisi resmi._"

## Kapan Anda bertindak

Anda **tidak punya heartbeat**. Anda hanya bertindak ketika:
1. Orchestrator (Lacakin) memanggil Anda via `a2a_inbox`.
2. User mengetik `@polisi` di grup.

## Apa yang Anda lakukan

1. Baca `./shared/CONTEXT.md` untuk semua field kasus.
2. Panggil `polisi-mcp.draft_laporan(...)` dengan field dari CONTEXT.
3. Post `markdown` yang dikembalikan tool, plus disclaimer.
4. Jika ada field yang kosong (misal pelapor_nama belum dikumpulkan
   orchestrator), gunakan "(belum diisi — mohon dilengkapi)" dan jangan
   block — tetap render laporan.

## Hard rules

- Jangan pernah klaim Anda adalah polisi.
- Jangan pernah memberi nasihat hukum spesifik di luar template laporan.
- Jangan minta data sensitif lain dari user — Anda hanya merangkum.
```

- [ ] **Step 2: Commit**

```bash
git add openclaw/prompts/polisi_system.md
git commit -m "feat(prompts): polisi-ai system prompt"
```

---

### Task 11: Sosmed agent prompt

**Files:**
- Create: `openclaw/prompts/heartbeat_sosmed.md`

- [ ] **Step 1: Write the prompt**

```markdown
# HEARTBEAT — Pengintai Sosmed (`sosmed`)

Anda **Pengintai Sosmed**. Anda memantau Facebook Marketplace + Instagram
untuk listing motor curiga. Anda tick setiap 45 detik (demo) / 10 menit (prod).

## Gaya bicara di grup

Informal Bahasa Indonesia, agak "stalker-friendly". Contoh:
"Akun baru, foto motor sama persis di feed, nego di DM — klasik tanda hot motor.
Saya bookmark."

## Each tick

1. **Ikuti A2A_PROTOCOL.md** — baca inbox dulu, terapkan pivot.
2. Re-read `./shared/CONTEXT.md`. Jika `Status: CLOSED`, langsung exit.
3. Re-read `./findings.md` untuk dedup.
4. Build queries:
   - `"<merk> <model> <warna> bandung"` di FB Marketplace
   - Instagram hashtag search: `#motorbekasbandung`, `#hondabeatbandung`
5. Untuk tiap kandidat (max 3/tick):
   - `browser-mcp.marketplace_search(platform="facebook"|"instagram", query)`
   - `browser-mcp.marketplace_get_listing(url)` untuk detail + foto
   - Skip jika listing > 7 hari.
   - **Stage 1**: `vision-mcp.match_image_tool(reference, candidate_image)`.
     Skip jika score < 0.55. Log jika 0.55-0.70 (tidak post).
   - **Stage 2**: jika ≥ 0.70 → `vision-mcp.reason_about_candidate(image, context_md, source_type="social")`.
6. Jika `match_confidence >= 0.75 AND len(matches) >= 2`:
   - Post ke grup dengan format:
     ```
     🚨 Listing curiga · <platform> · <score>
     [image]
     🔗 <url>
     
     <narrative>
     
     ✓ Cocok:
       • <matches>
     ⚠ Sinyal:
       • <suspicious_signals>
     
     <@-mention dari route_to jika ada>
     ```
   - `db-mcp.write_finding(case_id, agent_id="sosmed", severity="HIGH", ...)`
   - Untuk tiap `route_to[i]`: `a2a_send(...)` ke agent itu.
7. Append ke `./findings.md` semua kandidat yang diperiksa.
8. **Akhiri tick** dengan `a2a_tick_done(to_agent="sosmed")`.

## Hard rules

- Max 3 listing per tick. Token budget ketat.
- Jika 2 query berturut-turut return 0 hasil, sleep tick ini dan log `BLOCKED`.
- Tidak pernah follow / interact di akun — read-only saja.
```

- [ ] **Step 2: Commit**

```bash
git add openclaw/prompts/heartbeat_sosmed.md
git commit -m "feat(prompts): pengintai sosmed heartbeat"
```

---

### Task 12: Update existing 4 prompts for vision pipeline + A2A + personas

The existing `heartbeat_cctv.md`, `heartbeat_marketplace.md`, `heartbeat_parts.md`, `main_system.md`, `report_system.md` need to be revised to:
1. Reference `A2A_PROTOCOL.md` at the top.
2. Use the Stage-1 / Stage-2 vision pipeline (call `reason_about_candidate`).
3. Emit `route_to` @-mentions.
4. Express the persona voice per section 2 of the design.
5. Orchestrator: cold-start swarm-awakening A2A pings.

We do this as **one task** because the files share structure — easier to edit consistently.

**Files:**
- Modify: `openclaw/prompts/heartbeat_cctv.md` (full rewrite)
- Modify: `openclaw/prompts/heartbeat_marketplace.md` (full rewrite)
- Modify: `openclaw/prompts/heartbeat_parts.md` (full rewrite)
- Modify: `openclaw/prompts/main_system.md` (additions only)
- Modify: `openclaw/prompts/report_system.md` (additions only)

- [ ] **Step 1: Rewrite `heartbeat_cctv.md`**

```markdown
# HEARTBEAT — Mata Bandung (`cctv-bandung`)

Anda **Mata Bandung**, mata Bandung di kasus motor hilang. Anda mengawasi
CCTV pelindung. Anda tick setiap 30s (demo) / 5m (prod).

## Gaya bicara di grup

Pendek, observasional, seperti pengintai radio:
- "14:07 — kandidat di Simpang Dago. Lihat tangki."
- Tidak banyak basa-basi. Lihat → laporkan.

## Each tick

1. **Ikuti A2A_PROTOCOL.md** — `a2a_inbox(to_agent="cctv-bandung")` DULU.
   Jika ada pivot (misal "fokus area selatan"), itu prioritas tick ini.
2. Re-read `./shared/CONTEXT.md`. Jika `Status: CLOSED`, exit.
3. Re-read `./findings.md` untuk hindari double-check kamera yang sama
   dalam 5 menit terakhir.
4. Dari `./cameras.json`, pilih **3 kamera** dalam 5km dari last-seen
   (atau area yang dipivot dari A2A) yang belum dicek baru-baru ini.
5. Untuk tiap kamera:
   a. `browser-mcp.cctv_snapshot(camera_id)` → `image_path`.
   b. **Stage 1**: `vision-mcp.match_image_tool(reference=context.photo, candidate=image_path)`.
      Skip jika score < 0.55. Log saja jika 0.55–0.70.
   c. **Stage 2** (hanya jika score ≥ 0.70):
      `vision-mcp.reason_about_candidate(image_path, context_md, source_type="cctv")`.
   d. Optional: `vision-mcp.read_plate_tool(image_path)` untuk cross-check plat.
6. Jika `match_confidence >= 0.75 AND len(matches) >= 2`:
   - Post ke grup:
     ```
     🚨 CCTV <area> · <HH:MM>
     [snapshot]
     
     Match: <score> — <narrative>
     
     ✓ Cocok:
       • <matches>
     ⚠ Sinyal:
       • <suspicious_signals>
     
     <@-mention dari route_to jika ada>
     ```
   - `db-mcp.write_finding(case_id, agent_id="cctv-bandung", severity="HIGH",
     score=match_confidence, image_path=..., note=narrative)`.
   - Untuk tiap `route_to[i]`: `a2a_send(case_id, from_agent="cctv-bandung",
     to_agent=route_to[i].agent, reason=route_to[i].reason, ...)`.
7. Append ke `./findings.md` semua kamera yang dicek (termasuk yang skip).
8. `a2a_tick_done(to_agent="cctv-bandung")`. STOP.

## Hard rules

- Max 3 kamera per tick. Tidak loop. Tick berikutnya 30s lagi.
- Jika `cctv_snapshot` gagal 2x untuk kamera yang sama, log dan move on.
- Tidak pernah analyze trends — tugas itu untuk `report` agent.
- Tidak boleh kirim A2A balik ke agent yang punya chain_id sama (MCP cycle-protect, tapi tetap hindari).
```

- [ ] **Step 2: Rewrite `heartbeat_marketplace.md`** (same structure, market-trader voice)

```markdown
# HEARTBEAT — Pemantau Pasar (`marketplace`)

Anda **Pemantau Pasar**, watcher Tokopedia + OLX. Tick 45s (demo) / 10m (prod).

## Gaya bicara

Seperti pedagang yang menemukan deal mencurigakan:
- "Eh, ini listing posted 30 menit lalu, harga turun Rp 3jt — mencurigakan."
- "Akun baru, plat dikaburkan, lokasi Bandung — pola lama."

## Each tick

1. **A2A inbox dulu** (per A2A_PROTOCOL.md).
2. CONTEXT.md → status check.
3. findings.md → dedup by URL.
4. Build 2-3 query: `"<merk> <model> <warna> bandung"`, `"<merk> <model> <tahun> bandung"`.
5. Untuk tiap query, untuk tiap platform `["tokopedia","olx"]`:
   - `browser-mcp.marketplace_search(platform, query, limit=5)`.
   - Filter ke listing posted < 24h DAN lokasi mengandung "bandung"/"jabar"/"jawa barat".
6. Untuk tiap kandidat (max 5/tick total):
   - `browser-mcp.marketplace_get_listing(url)` untuk detail + foto.
   - **Stage 1**: `match_image_tool(reference, candidate_image)`.
   - **Stage 2** (jika ≥ 0.70): `reason_about_candidate(image_path, context_md, "marketplace")`.
7. Post + write_finding + a2a_send sama pattern dengan CCTV worker.
8. `a2a_tick_done(to_agent="marketplace")`. STOP.

## Hard rules

- Max 5 listing diperiksa dalam per tick.
- Dedup berdasar URL.
- Jika CAPTCHA atau 0 hasil 2x berturut-turut → log `BLOCKED`, sleep tick.
```

- [ ] **Step 3: Rewrite `heartbeat_parts.md`** (technical voice)

```markdown
# HEARTBEAT — Pemburu Suku Cadang (`parts`)

Anda **Pemburu Suku Cadang**. Anda cari motor yang dijual potong-potong.
Tick 60s (demo) / 15m (prod).

## Gaya bicara

Teknis, fokus part-name. Contoh:
- "Velg racing emas RCB ukuran 17 inch — match. Penjual: Kiaracondong."
- "Knalpot R9 aftermarket, model 2022. 3 listing baru hari ini."

## Each tick

1. A2A inbox (per A2A_PROTOCOL.md) — pivot dari `cctv-bandung` biasanya
   berbentuk "fokus area X" atau "cari part Y".
2. CONTEXT.md status check.
3. Dari `Ciri unik:` di CONTEXT.md, ekstrak part-part yang biasa dijual:
   velg, knalpot, lampu, jok, tangki, aftermarket apa pun yang disebut.
4. Build query per part: `"<merk> <model> <part> bandung"`, `"<part> bekas bandung"`.
5. Per query × 2 platform = max 8 sweeps. Top 3 kandidat per query.
6. Skip listing > 14 hari.
7. Stage 1 → Stage 2 sama pattern, tapi threshold lebih rendah karena cuma part:
   post jika `match_confidence >= 0.65 AND len(matches) >= 2` (parts = sinyal lemah).
8. write_finding severity="MEDIUM" untuk parts (kecuali jelas match motor utuh, baru HIGH).
9. `a2a_tick_done(to_agent="parts")`. STOP.

## Hard rules

- Max 4 part × 2 platform = 8 sweep per tick. Tidak lebih.
- Dedup URL.
```

- [ ] **Step 4: Append to `main_system.md`** (cold-start swarm-awakening + persona reminder)

Append at the **end** of the existing prompt:

```markdown

---

## Cold-start swarm awakening (CRITICAL for demo)

Tepat setelah Anda berhasil `write_case_context`, lakukan SEKALI urutan ini
**dengan jeda 1-2 detik antar pesan**, supaya grup melihat tim "bangun"
secara teatrikal (Mata pertama, lalu Pasar, Sosmed, Cadang):

```python
a2a_send(case_id=cid, from_agent="orchestrator", to_agent="cctv-bandung",
         reason="initial_sweep", payload={"priority":"first"}, ttl_ticks=1)
# wait 1.5s
a2a_send(case_id=cid, from_agent="orchestrator", to_agent="marketplace",
         reason="initial_sweep", payload={"priority":"first"}, ttl_ticks=1)
# wait 1.5s
a2a_send(case_id=cid, from_agent="orchestrator", to_agent="sosmed",
         reason="initial_sweep", payload={"priority":"first"}, ttl_ticks=1)
# wait 1.5s
a2a_send(case_id=cid, from_agent="orchestrator", to_agent="parts",
         reason="initial_sweep", payload={"priority":"first"}, ttl_ticks=1)
```

Setiap worker yang menerima `reason="initial_sweep"` HARUS post di grup
satu baris pembukaan, lalu langsung jalankan tick pertamanya. Contoh:
- Mata Bandung: "Saya mulai sapu CCTV di area Dago. 3 kamera per 30 detik."
- Pemantau Pasar: "Saya buka Tokopedia + OLX. Filter Bandung 24 jam."
- Pengintai Sosmed: "FB Marketplace + IG hashtag, on the case."
- Pemburu Suku Cadang: "Saya cari part-part: velg emas, stiker, knalpot."

Setelah swarm awakening, Anda kembali ke peran pasif: monitor findings,
forward HIGH ke user jika perlu, terima context update dari user, broadcast
ke workers via update CONTEXT.md (workers re-read tiap tick).

## Persona reminder

Anda Lacakin — hangat, tenang, empati. User sedang panik. Pendek di Telegram,
tidak lebay. Selalu pakai Bahasa Indonesia.
```

- [ ] **Step 5: Append to `report_system.md`** (persona + cron mode)

Append at the **end**:

```markdown

---

## Mode

Anda dipanggil dalam dua mode:
1. **Heartbeat cron** (tiap 90s demo / 30m prod) — tanpa input user. Cek
   apakah ada finding baru ≥ HIGH severity sejak laporan terakhir. Jika ya,
   post laporan terbaru di grup. Jika tidak, **diam** (tidak post).
2. **On-demand** — user mengetik `@laporan` di grup. Selalu post laporan
   lengkap (tidak peduli ada finding baru atau tidak).

## Persona

Anda Pencatat Laporan — netral, terstruktur. Bahasa Indonesia. Tidak
emosional, tidak hyperbolic. Hanya fakta + bullets + count.
```

- [ ] **Step 6: Smoke (verify prompts load)**

```bash
ls -la openclaw/prompts/
# Should see 6 .md files (5 heartbeats/systems + A2A_PROTOCOL.md)
```

- [ ] **Step 7: Commit**

```bash
git add openclaw/prompts/
git commit -m "feat(prompts): vision pipeline + A2A + personas across all agents"
```

---

## Chunk 6: Demo staging

### Task 13: Local demo asset server

We need pelindung-blocked-or-not, a stable URL the `cctv-bandung` agent can hit and reliably get a matching motor. Solution: serve a local HTML page that contains the staged image.

**Files:**
- Create: `demo_assets/cctv_clips/dago-simpang.html`
- Create: `demo_assets/fake_listings/tokopedia-honda-beat-merah.html`
- Create: `demo_assets/reference/.gitkeep`
- Create: `scripts/serve_demo_assets.py`

- [ ] **Step 1: Create the staged CCTV "clip" wrapper**

`demo_assets/cctv_clips/dago-simpang.html`:

```html
<!doctype html>
<html><head><title>CCTV — Simpang Dago (staged)</title>
<style>body{margin:0;background:#000} img{width:1280px;height:720px;object-fit:cover}</style>
</head><body>
<img src="staged-motor-frame.jpg" alt="staged">
</body></html>
```

- [ ] **Step 2: Copy fake Tokopedia listing**

If `~/lacakin/shared/fake_listings/tokopedia-honda-beat-merah.html` already exists from previous seed, copy it. Otherwise paste the version from `scripts/seed_demo.py` (the HTML literal in that file) into `demo_assets/fake_listings/tokopedia-honda-beat-merah.html`. Add `<img src="staged-motor-frame.jpg">` so the marketplace agent has an image to vision-reason about.

- [ ] **Step 3: Asset server**

`scripts/serve_demo_assets.py`:

```python
"""Serve demo_assets/ on a local port. Use during demo + dev.

Cameras.json point cctv URLs at this server; marketplace agent's fake
Tokopedia link points here too."""
import http.server
import socketserver
from pathlib import Path

PORT = 8765
ROOT = Path(__file__).resolve().parent.parent / "demo_assets"

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

if __name__ == "__main__":
    with socketserver.TCPServer(("0.0.0.0", PORT), H) as httpd:
        print(f"Serving {ROOT} at http://0.0.0.0:{PORT}")
        httpd.serve_forever()
```

- [ ] **Step 4: Update `cameras.json` to swap dago-simpang to staged**

Edit `mcp/browser_mcp/cameras.json` and change `dago-simpang.url` to:
```
"http://localhost:8765/cctv_clips/dago-simpang.html"
```
The other 9 cameras keep their pelindung URLs (they'll either work or harmlessly error).

- [ ] **Step 5: Commit**

```bash
git add demo_assets/ scripts/serve_demo_assets.py mcp/browser_mcp/cameras.json
git commit -m "feat(demo): local asset server + staged CCTV + fake Tokopedia"
```

---

### Task 14: Drop in real reference photo + staged motor frame + register fixture

The reference is the photo the user "uploads"; the staged frame is what the CCTV will "see". These need to be real JPGs the team prepares.

**Files:**
- Modify: `demo_assets/reference/honda-beat-reference.jpg` (manually place)
- Modify: `demo_assets/cctv_clips/staged-motor-frame.jpg` (manually place)
- Modify: `demo_assets/fake_listings/staged-motor-frame.jpg` (same image, copy)
- Create: `scripts/register_demo_fixtures.py`

- [ ] **Step 1: Place real JPGs (manual)**

Take any two photos of any Honda Beat (or motorcycle) — they don't need to be the same motor, the staging will explain itself in the demo. Drop them in:
- `demo_assets/reference/honda-beat-reference.jpg` (the "user's photo")
- `demo_assets/cctv_clips/staged-motor-frame.jpg` (what CCTV captures)
- copy the same frame to `demo_assets/fake_listings/staged-motor-frame.jpg`

- [ ] **Step 2: Fixture registration script**

`scripts/register_demo_fixtures.py`:

```python
"""Pre-register the staged CCTV image + staged listing image in the vision
fixture cache so the Sonnet calls are instant + deterministic during demo."""
from pathlib import Path
from mcp.vision_mcp import fixture_cache

ROOT = Path(__file__).resolve().parent.parent / "demo_assets"

CCTV_RESPONSE = {
    "match_confidence": 0.86,
    "matches": [
        "Warna body merah-hitam — sesuai dengan referensi",
        "Plat samar terbaca 'D 12?? AB?' — cocok parsial",
        "Stiker merah di tangki — konsisten dengan stiker MotoGP",
    ],
    "mismatches": [],
    "suspicious_signals": [
        "Pengendara tidak pakai helm",
        "Motor jalan pelan, sering toleh ke belakang",
    ],
    "narrative": "Honda Beat merah-hitam terlihat melaju ke selatan di Simpang Dago.",
    "route_to": [
        {"agent": "parts", "reason": "motor menuju selatan, cari velg emas di Buah Batu / Kiaracondong"}
    ],
}

LISTING_RESPONSE = {
    "match_confidence": 0.91,
    "matches": [
        "Honda Beat merah-hitam dengan stiker MotoGP di tangki — sangat mirip referensi",
    ],
    "mismatches": [],
    "suspicious_signals": [
        "Plat sengaja dikaburkan di semua foto",
        "Harga Rp 12.500.000 — di bawah pasar Rp 15-16jt",
        "Akun baru, rating 0",
    ],
    "narrative": "Listing curiga di Tokopedia 32 menit lalu — semua sinyal cocok.",
    "route_to": [],
}


def main():
    cctv_img = ROOT / "cctv_clips" / "staged-motor-frame.jpg"
    listing_img = ROOT / "fake_listings" / "staged-motor-frame.jpg"
    assert cctv_img.exists(), f"Place a real JPG at {cctv_img}"
    assert listing_img.exists(), f"Place a real JPG at {listing_img}"
    h1 = fixture_cache.register_fixture(str(cctv_img), CCTV_RESPONSE)
    h2 = fixture_cache.register_fixture(str(listing_img), LISTING_RESPONSE)
    print(f"Registered CCTV fixture: {h1[:12]}...")
    print(f"Registered listing fixture: {h2[:12]}...")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run it**

```bash
python scripts/register_demo_fixtures.py
```

Expected: prints two hash prefixes.

- [ ] **Step 4: Update `scripts/seed_demo.py`** to copy the real reference photo into `~/lacakin/shared/photos/reference.jpg` (currently writes a fake JPEG header). Replace the `if not ref.exists()` block with:

```python
import shutil
real_ref = Path(__file__).resolve().parent.parent / "demo_assets" / "reference" / "honda-beat-reference.jpg"
shutil.copy(real_ref, ref)
```

- [ ] **Step 5: Commit**

```bash
git add scripts/register_demo_fixtures.py scripts/seed_demo.py demo_assets/
git commit -m "feat(demo): real reference + staged frames + fixture registration"
```

---

### Task 15: Dry-run checklist + final wiring smoke

**Files:**
- Create: `scripts/demo_dry_run.md`

- [ ] **Step 1: Write checklist**

`scripts/demo_dry_run.md`:

```markdown
# Demo dry-run checklist (run T-30min before judging)

## Pre-flight (10 min)

- [ ] VPS reachable, time synced
- [ ] `.env` contains all 7 TELEGRAM_TOKEN_* + ANTHROPIC_API_KEY + LACAKIN_GROUP_ID
- [ ] `.env.demo` sourced (`source scripts/start_gateway.sh demo` doesn't actually start, dry-run with `bash -n`)
- [ ] All 7 bots `getMe` returns expected username (run command from `botfather_checklist.md`)
- [ ] Telegram group has all 7 bots as admins
- [ ] **Bot-to-bot mention smoke** — confirms cross-bot @-mentions reach the mentioned bot's `getUpdates`. Critical for the visible-coordination wow layer.
  ```bash
  # Post from one bot, mentioning another:
  curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN_CCTV/sendMessage" \
       -d "chat_id=$LACAKIN_GROUP_ID" \
       -d "text=smoke: @cadang_bot please respond"
  sleep 2
  # Confirm the parts bot received it:
  curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN_PARTS/getUpdates" \
       | jq '.result[-1].message.text'
  ```
  Expected: prints `"smoke: @cadang_bot please respond"`. If empty or missing,
  re-run `@BotFather /setprivacy → Disable` on `@cadang_bot` and try again.
  If still empty, **fall back: drop visible @-mentions from prompts, rely on
  A2A inbox only** (the prompts can stay as-is; nothing else breaks).
- [ ] `python scripts/serve_demo_assets.py &` running; `curl http://localhost:8765/cctv_clips/dago-simpang.html` returns the HTML
- [ ] `python scripts/seed_demo.py` ran without error
- [ ] `python scripts/register_demo_fixtures.py` ran without error
- [ ] Smoke vision: `python -c "from mcp.vision_mcp.sonnet_reason import reason_about_candidate; print(reason_about_candidate('demo_assets/cctv_clips/staged-motor-frame.jpg','test','cctv'))"` returns the fixture response

## Start (5 min)

- [ ] `bash scripts/start_gateway.sh demo` — gateway boots, no error in logs
- [ ] All 7 agents show up in `openclaw status`
- [ ] All 7 bots are online (Telegram shows them as "online")

## Smoke through the flow (10 min)

- [ ] In the group, type a test message; `@lacakin_bot` responds in <5s
- [ ] Provide a full case in one message (motor, plat, lokasi, jam, ciri); orchestrator pins case context
- [ ] Within 5s, see Mata + Pasar + Sosmed + Cadang post opening lines (swarm awakening)
- [ ] Within 30-60s, Mata posts the staged CCTV finding with vision reasoning
- [ ] Pasar posts the staged Tokopedia finding within 45-90s
- [ ] @-mention from Mata to @cadang is visible; Cadang's next tick mentions "mengikuti arahan @mata"
- [ ] Type `@mata cek Pasteur sekarang`; Mata's next tick targets Pasteur (any image is fine, the test is that it tried)
- [ ] Type `@laporan rangkum sekarang`; report posted within 5s
- [ ] Type `@polisi tolong draft laporan`; draft posted within 5s

## Cleanup

- [ ] Stop gateway: Ctrl+C
- [ ] Reset for live demo: `python -c "from mcp.db_mcp.server import _conn; _conn.execute('DELETE FROM findings'); _conn.execute('UPDATE cases SET status=\"CLOSED\"')"`
- [ ] Verify group is clean (delete bot posts manually if you want)

## If anything fails

- See `docs/plans/2026-05-15-lacakin-openclaw-wow-design.md` Section 8 (Risks & cutlines)
- Specific recovery:
  - Bots offline → re-source `.env.demo`, restart gateway
  - No vision reasoning → `register_demo_fixtures.py` again
  - Group not receiving → re-promote bots to admin
  - Sonnet rate limited → demo proceeds on fixtures only, no real Sonnet calls
```

- [ ] **Step 2: Commit**

```bash
git add scripts/demo_dry_run.md
git commit -m "docs: pre-demo dry-run checklist"
```

---

## Final integration

### Task 16: End-to-end smoke from outside the gateway

A single script that exercises the new pieces (A2A inbox, fixture cache, polisi MCP, sonnet reason fallback) without starting the gateway. This catches MCP wiring breakage in <30s.

**Files:**
- Create: `scripts/smoke_e2e.py`

- [ ] **Step 1: Write smoke**

```python
"""Five-second sanity check before each demo. No gateway needed."""
import json
from pathlib import Path

from mcp.a2a_mcp.server import send, list_inbox, consume, ttl_decrement
from mcp.polisi_mcp.server import draft_laporan
from mcp.vision_mcp import fixture_cache, sonnet_reason


def main():
    print("[1/4] A2A inbox roundtrip...")
    cid = send(case_id="smoke", from_agent="mata", to_agent="cadang",
               reason="test", payload={})
    msgs = list_inbox(to_agent="cadang")
    assert msgs, "A2A inbox empty"
    consume([msgs[0]["id"]])
    print("  OK")

    print("[2/4] Polisi laporan render...")
    out = draft_laporan(
        pelapor_nama="Smoke", motor_jenis="Bebek",
        merk_model_tahun="Honda Beat 2022", warna="Merah",
        plat="D 1234 ABC", ciri_unik=["test"], lokasi_terakhir="Dago",
        hari_kejadian="Senin", jam_kejadian="14:00",
    )
    assert "LAPORAN KEHILANGAN" in out["markdown"]
    print("  OK")

    print("[3/4] Vision fixture cache...")
    staged = Path("demo_assets/cctv_clips/staged-motor-frame.jpg")
    if staged.exists():
        cached = fixture_cache.lookup(str(staged))
        assert cached is not None, "Demo fixture not registered — run register_demo_fixtures.py"
        out = sonnet_reason.reason_about_candidate(
            image_path=str(staged), context_md="test", source_type="cctv"
        )
        assert out["match_confidence"] >= 0.7
        print(f"  OK (confidence {out['match_confidence']})")
    else:
        print("  SKIP (staged frame not placed yet)")

    print("[4/4] Schema sanity...")
    assert "match_confidence" in sonnet_reason.RESPONSE_KEYS
    print("  OK")

    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run**

```bash
python scripts/smoke_e2e.py
```

Expected: 4 checks pass (or 3 + 1 SKIP if frames not placed).

- [ ] **Step 3: Commit**

```bash
git add scripts/smoke_e2e.py
git commit -m "feat(smoke): single-script e2e sanity check for demo"
```

---

## Wrap-up

### Final verification

- [ ] Run full test suite: `pytest -v -m "not needs_api"` — all green
- [ ] Run smoke: `python scripts/smoke_e2e.py` — all green
- [ ] Open `scripts/demo_dry_run.md` and walk through every checkbox once T-30min before demo
- [ ] Commit any last polish:
  ```bash
  git add -A
  git commit -m "chore: pre-demo polish"
  ```

### What's in the build, mapped to the design

| Design section | Where it lives |
|---|---|
| Multi-bot Telegram | `openclaw/agents.json5` channels + bindings + broadcast |
| Per-agent personas | `openclaw/agents.json5` identity blocks + persona voice in each prompt |
| Vision pipeline (CLIP→Sonnet) | `mcp/vision_mcp/server.py` + `sonnet_reason.py` + `fixture_cache.py` |
| @-mention coordination | `route_to` field in Sonnet schema + worker prompts post `@<agent>` |
| Real A2A messaging | `mcp/a2a_mcp/server.py` (send/inbox/consume/tick_done) |
| TTL + cycle protection | `a2a_mcp` schema + `cycle_check()` + worker A2A_PROTOCOL.md |
| Cold-start swarm awakening | `main_system.md` end section |
| Demo cadence | `.env.demo` + env interpolation in `agents.json5` heartbeats |
| Fixture-cache reliability | `mcp/vision_mcp/fixture_cache.py` + `scripts/register_demo_fixtures.py` |
| Polisi-AI draft | `mcp/polisi_mcp/` + `polisi_system.md` |
| Demo staging | `demo_assets/` + `scripts/serve_demo_assets.py` |

### Team split (12h, 3 people)

- **Person A (gateway/orchestration):** Task 1, 2, 7, 8, 12 (main_system+report_system parts), 15
- **Person B (MCP servers/vision):** Task 3, 4, 5, 9, 13, 14, 16
- **Person C (prompts/demo):** Task 6, 10, 11, 12 (heartbeat_* parts), 13 (assets), 14 (assets), 15

Person C's role is the most variable — they own the demo recording and pre-staging, which means they should be doing rehearsals in parallel with B's MCP work from H6 onwards.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-15-lacakin-openclaw-wow.md`. Ready to execute?
