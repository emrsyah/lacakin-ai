"""
db-mcp: tiny SQLite-backed shared memory for orchestrator + workers.

Tools:
  - write_context(case_id, context_md)
  - get_context(case_id)
  - close_case(case_id)
  - write_finding(case_id, agent_id, severity, score, source_url, image_path, note)
  - list_findings(case_id, since_iso=None, severity=None, limit=50)
  - mark_delivered(finding_ids)
  - undelivered(case_id)
"""
from __future__ import annotations

import os
import sqlite3
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

mcp = FastMCP("db-mcp")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@mcp.tool()
def write_context(case_id: str, context_md: str) -> dict[str, Any]:
    """Create or update the case context (the source of truth for workers)."""
    now = _now()
    _conn.execute(
        """
        INSERT INTO cases(id, status, created_at, updated_at, context_md)
             VALUES(?, 'ACTIVE', ?, ?, ?)
        ON CONFLICT(id) DO UPDATE
             SET context_md = excluded.context_md,
                 updated_at = excluded.updated_at
        """,
        (case_id, now, now, context_md),
    )
    return {"case_id": case_id, "updated_at": now}


@mcp.tool()
def get_context(case_id: str) -> dict[str, Any]:
    row = _conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    return dict(row) if row else {"error": f"no such case {case_id}"}


@mcp.tool()
def close_case(case_id: str) -> dict[str, Any]:
    _conn.execute("UPDATE cases SET status='CLOSED', updated_at=? WHERE id=?", (_now(), case_id))
    return {"case_id": case_id, "status": "CLOSED"}


@mcp.tool()
def write_finding(case_id: str, agent_id: str, severity: str, note: str,
                  score: float | None = None, source_url: str | None = None,
                  image_path: str | None = None) -> dict[str, Any]:
    """Record a finding. Severity: HIGH | MEDIUM | LOW."""
    if severity not in ("HIGH", "MEDIUM", "LOW"):
        return {"error": "severity must be HIGH | MEDIUM | LOW"}
    cur = _conn.execute(
        """INSERT INTO findings(case_id, agent_id, severity, score, source_url,
                                image_path, note, created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (case_id, agent_id, severity, score, source_url, image_path, note, _now()),
    )
    return {"id": cur.lastrowid}


@mcp.tool()
def list_findings(case_id: str, since_iso: str | None = None,
                  severity: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    q = "SELECT * FROM findings WHERE case_id = ?"
    args: list[Any] = [case_id]
    if since_iso:
        q += " AND created_at >= ?"
        args.append(since_iso)
    if severity:
        q += " AND severity = ?"
        args.append(severity)
    q += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in _conn.execute(q, args).fetchall()]


@mcp.tool()
def undelivered(case_id: str) -> list[dict[str, Any]]:
    """Findings the orchestrator hasn't yet forwarded to the user."""
    rows = _conn.execute(
        "SELECT * FROM findings WHERE case_id = ? AND delivered = 0 ORDER BY created_at",
        (case_id,),
    ).fetchall()
    return [dict(r) for r in rows]


@mcp.tool()
def mark_delivered(finding_ids: list[int]) -> dict[str, Any]:
    if not finding_ids:
        return {"updated": 0}
    placeholders = ",".join("?" * len(finding_ids))
    cur = _conn.execute(
        f"UPDATE findings SET delivered = 1 WHERE id IN ({placeholders})",
        finding_ids,
    )
    return {"updated": cur.rowcount}


if __name__ == "__main__":
    mcp.run()
