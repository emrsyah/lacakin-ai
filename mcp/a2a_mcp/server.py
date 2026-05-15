"""Agent-to-agent inbox MCP. Persists pivot requests with TTL + chain_id so
workers survive heartbeats and can't form cycles."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    # When run as an MCP server, the installed `mcp` package provides FastMCP.
    # In tests the local mcp/ directory shadows it, so we guard here.
    import sys as _sys
    import importlib as _il
    _real_mcp = _il.import_module("mcp.server.fastmcp")
    FastMCP = _real_mcp.FastMCP
    del _real_mcp, _sys, _il
except (ModuleNotFoundError, ImportError):
    class FastMCP:  # type: ignore[no-redef]
        def __init__(self, name): self.name = name
        def tool(self): return lambda f: f
        def run(self): pass

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()
mcp = FastMCP("a2a-mcp")

_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        db_path = Path(os.environ.get("LACAKIN_DB", str(Path.home() / "lacakin" / "lacakin.db")))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(db_path), check_same_thread=False, isolation_level=None)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
    return _conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def send(case_id: str, from_agent: str, to_agent: str, reason: str,
         payload: dict, ttl_ticks: int = 2,
         chain_id: str | None = None) -> str:
    cid = chain_id or str(uuid.uuid4())
    if cycle_check(chain_id=cid, to_agent=to_agent):
        return cid
    _get_conn().execute(
        """INSERT INTO a2a_messages(chain_id, case_id, from_agent, to_agent,
                                    reason, payload_json, ttl_ticks, created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (cid, case_id, from_agent, to_agent, reason,
         json.dumps(payload), ttl_ticks, _now()),
    )
    return cid


def list_inbox(to_agent: str) -> list[dict[str, Any]]:
    rows = _get_conn().execute(
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
    cur = _get_conn().execute(
        f"UPDATE a2a_messages SET consumed_at = ? WHERE id IN ({q})",
        (_now(), *message_ids),
    )
    return cur.rowcount


def ttl_decrement(to_agent: str) -> int:
    """Decrement TTL of un-consumed messages at the end of a tick."""
    cur = _get_conn().execute(
        """UPDATE a2a_messages
           SET ttl_ticks = ttl_ticks - 1
           WHERE to_agent = ? AND consumed_at IS NULL""",
        (to_agent,),
    )
    return cur.rowcount


def cycle_check(chain_id: str, to_agent: str) -> bool:
    """True if sending this chain to `to_agent` would form a cycle."""
    row = _get_conn().execute(
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
