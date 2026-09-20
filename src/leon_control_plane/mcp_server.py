"""Local stdio MCP server exposing bounded read-only Leon context."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import stat
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from leon_control_plane.agent_skills import load_agent_skills
from leon_control_plane.secret_scanner import redact_value
OPEN_STATUSES = {"new", "planned", "active", "review", "waiting_for_approval", "waiting_for_secret", "waiting_for_user", "blocked"}
TASK_STATUSES = OPEN_STATUSES | {"done", "rejected"}
VISIBLE_TASK_FIELDS = ("id", "title", "status", "priority", "risk_level", "value_score", "owner", "blocked_reason")
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
ROOT = Path(__file__).resolve().parents[2]


def _clip(value: Any, maximum: int = 512) -> Any:
    return value[:maximum] if isinstance(value, str) else value


def _visible_task(task: dict[str, Any]) -> dict[str, Any]:
    return redact_value({key: _clip(task.get(key)) for key in VISIBLE_TASK_FIELDS})


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def build_mcp_server(db_path: Path, *, skills_path: Path) -> MCPServer:
    server = MCPServer(
        "leon-readonly",
        version="1.0.0",
        instructions="Read-only local Leon status, tasks and installed agent skill metadata. No write tools.",
    )

    @server.tool(annotations=READ_ONLY, structured_output=True)
    def leon_status() -> dict[str, Any]:
        """Return bounded local Leon health and workload counts."""
        with _connect_readonly(db_path) as connection:
            metadata = {row["key"]: json.loads(row["value"]) for row in connection.execute(
                "SELECT key, value FROM metadata WHERE key IN ('current_phase', 'progress_percent')"
            )}
            counts = {
                str(row["status"])[:64]: int(row["count"])
                for row in connection.execute("SELECT status, COUNT(*) AS count FROM tasks GROUP BY status LIMIT 16")
            }
            pending = connection.execute("SELECT COUNT(*) FROM approvals WHERE status = 'pending'").fetchone()[0]
            active = connection.execute("SELECT COUNT(*) FROM agent_runs WHERE status = 'running'").fetchone()[0]
        try:
            progress = max(0, min(100, int(metadata.get("progress_percent") or 0)))
        except (TypeError, ValueError):
            progress = 0
        return {
            "phase": redact_value(str(metadata.get("current_phase") or "Leon")[:120]),
            "progress_percent": progress,
            "task_status_counts": counts,
            "pending_approvals": int(pending),
            "active_agent_runs": int(active),
        }

    @server.tool(annotations=READ_ONLY, structured_output=True)
    def list_tasks(status: str = "open", limit: int = 10) -> dict[str, Any]:
        """List bounded task summaries; status may be open or exact known status."""
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        if status != "open" and status not in TASK_STATUSES:
            raise ValueError("unknown task status")
        placeholders = ",".join("?" for _ in OPEN_STATUSES)
        query = f"SELECT {','.join(VISIBLE_TASK_FIELDS)} FROM tasks"
        if status == "open":
            query += f" WHERE status IN ({placeholders})"
            parameters: tuple[Any, ...] = (*sorted(OPEN_STATUSES), limit)
        else:
            query += " WHERE status = ?"
            parameters = (status, limit)
        query += " ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END, created_at, id LIMIT ?"
        with _connect_readonly(db_path) as connection:
            selected = [dict(row) for row in connection.execute(query, parameters)]
        return {"status_filter": status, "count": len(selected), "tasks": [_visible_task(item) for item in selected]}

    @server.tool(annotations=READ_ONLY, structured_output=True)
    def list_agent_skills() -> dict[str, Any]:
        """List validated Leon agent roles and capabilities without prompt secrets."""
        skills = load_agent_skills(skills_path)
        return {
            "count": len(skills),
            "skills": [
                {
                    "id": item["id"],
                    "role": item["role"],
                    "task_types": list(item["task_types"]),
                    "allowed_actions": list(item["allowed_actions"]),
                    "output_kind": item["output_kind"],
                }
                for item in skills
            ],
        }

    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="Leon read-only MCP stdio server")
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("LEON_DB_PATH", ROOT / ".runtime" / "control-plane.sqlite")))
    args = parser.parse_args()
    root = ROOT
    db = args.db.expanduser().resolve()
    if not db.is_file() or db.is_symlink():
        raise SystemExit("Leon database must be existing regular file")
    mode = stat.S_IMODE(db.stat().st_mode)
    if mode & 0o077:
        raise SystemExit("Leon database must not be group/world accessible")
    skills = root / "config" / "agent-skills.json"
    build_mcp_server(db, skills_path=skills).run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
