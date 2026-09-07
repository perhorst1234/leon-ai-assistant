"""Durable execution records for existing tasks; not a second task manager.

Only the fixed, read-only Python check is enabled. Lease recovery is at-least-once:
an interrupted read may repeat, but a fenced checkpoint can be committed once.
Do not register side-effecting tools here without a separate approval/idempotency contract.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
import json
import time
import uuid

from leon_control_plane.secret_scanner import assert_no_secrets
from leon_control_plane.store import ControlPlaneStore

KIND = "python_syntax_check"
STEPS = ("snapshot", "syntax", "report")
MAX_ATTEMPTS = 3
LEASE_SECONDS = 30


class WorkQueue:
    def __init__(self, store: ControlPlaneStore, *, clock=time.time):
        self.store, self.clock = store, clock
        store.initialize()
        with closing(store.connect()) as conn, conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS work_jobs (
                    id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL REFERENCES tasks(id), kind TEXT NOT NULL,
                    status TEXT NOT NULL, next_step INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0, lease_token TEXT,
                    lease_until REAL, error TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL, updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS work_jobs_claim ON work_jobs(status, lease_until);
                CREATE TABLE IF NOT EXISTS work_checkpoints (
                    job_id TEXT NOT NULL REFERENCES work_jobs(id), step INTEGER NOT NULL,
                    result_json TEXT NOT NULL, recorded_at REAL NOT NULL,
                    PRIMARY KEY(job_id, step)
                );
            """)

    @contextmanager
    def _transaction(self):
        with closing(self.store.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            yield conn

    @staticmethod
    def _job(conn, job_id):
        row = conn.execute("SELECT * FROM work_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown work job")
        return row

    @staticmethod
    def _task_eligible(conn, task_id):
        row = conn.execute("SELECT status, approval_required FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return row is not None and row["status"] in {"new", "planned", "active"} and not row["approval_required"]

    def _event(self, conn, job, event, detail=None):
        self.store.append_audit_event(
            conn, actor_type="system", actor_id="local-work-queue", event_type=f"work_{event}",
            task_id=job["task_id"], summary=f"Local Python check: {event}",
            redacted_payload={"job_id": job["id"], **(detail or {})},
        )

    @staticmethod
    def _results(conn, job_id):
        return [json.loads(row[0]) for row in conn.execute(
            "SELECT result_json FROM work_checkpoints WHERE job_id = ? ORDER BY step", (job_id,),
        )]

    def _view(self, conn, row):
        return {key: row[key] for key in (
            "id", "task_id", "kind", "status", "attempts", "error", "created_at", "updated_at",
        )} | {
            "completed_steps": row["next_step"], "total_steps": len(STEPS),
            "results": self._results(conn, row["id"]), "execution_kind": "local_read_only",
            "provider_calls_made": False,
        }

    def get(self, job_id):
        with closing(self.store.connect()) as conn:
            return self._view(conn, self._job(conn, job_id))

    def list(self):
        with closing(self.store.connect()) as conn:
            return [self._view(conn, row) for row in conn.execute(
                "SELECT * FROM work_jobs ORDER BY created_at DESC, id DESC LIMIT 100",
            )]

    def enqueue(self, *, task_id: str, request_id: str, kind: str = KIND):
        if kind != KIND:
            raise ValueError("Only python_syntax_check is enabled")
        try:
            request_id = str(uuid.UUID(request_id))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("request_id must be a UUID") from None
        with self._transaction() as conn:
            existing = conn.execute("SELECT * FROM work_jobs WHERE request_id = ?", (request_id,)).fetchone()
            if existing:
                if existing["task_id"] != task_id or existing["kind"] != kind:
                    raise ValueError("request_id is already bound to different work")
                return self._view(conn, existing)
            if not self._task_eligible(conn, task_id):
                raise ValueError("Task must be new/planned/active without a pending approval requirement")
            if conn.execute("SELECT COUNT(*) FROM work_jobs WHERE status IN ('queued','running','paused')").fetchone()[0] >= 100:
                raise ValueError("Local work queue is full")
            job_id, now = f"work-{uuid.uuid4().hex}", self.clock()
            conn.execute(
                "INSERT INTO work_jobs(id,request_id,task_id,kind,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (job_id, request_id, task_id, kind, "queued", now, now),
            )
            row = self._job(conn, job_id)
            self._event(conn, row, "queued")
            return self._view(conn, row)

    def control(self, job_id: str, action: str):
        if action not in {"pause", "resume", "cancel"}:
            raise ValueError("Expected pause, resume or cancel")
        with self._transaction() as conn:
            row = self._job(conn, job_id)
            target = {"pause": "paused", "resume": "queued", "cancel": "cancelled"}[action]
            if row["status"] == target:
                return self._view(conn, row)
            allowed = {"pause": {"queued", "running"}, "resume": {"paused"}, "cancel": {"queued", "running", "paused"}}
            if row["status"] not in allowed[action]:
                raise ValueError("Work is not in a state that permits this action")
            if action == "resume" and not self._task_eligible(conn, row["task_id"]):
                raise ValueError("Parent task is not eligible for execution")
            conn.execute(
                "UPDATE work_jobs SET status=?,lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=?",
                (target, self.clock(), job_id),
            )
            self._event(conn, row, target)
            return self._view(conn, self._job(conn, job_id))

    def claim(self):
        with self._transaction() as conn:
            now = self.clock()
            row = conn.execute(
                "SELECT * FROM work_jobs WHERE status='queued' OR (status='running' AND lease_until<=?) "
                "ORDER BY created_at,id LIMIT 1", (now,),
            ).fetchone()
            if row is None:
                return None
            if not self._task_eligible(conn, row["task_id"]):
                conn.execute("UPDATE work_jobs SET status='paused',error='parent_task_ineligible',lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=?", (now, row["id"]))
                self._event(conn, row, "paused", {"reason": "parent_task_ineligible"})
                return None
            if row["attempts"] >= MAX_ATTEMPTS:
                conn.execute("UPDATE work_jobs SET status='failed',error='recovery_limit',lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=?", (now, row["id"]))
                self._event(conn, row, "failed", {"reason": "recovery_limit"})
                return None
            token = uuid.uuid4().hex
            conn.execute(
                "UPDATE work_jobs SET status='running',attempts=attempts+1,lease_token=?,lease_until=?,error='',updated_at=? WHERE id=?",
                (token, now + LEASE_SECONDS, now, row["id"]),
            )
            self._event(conn, row, "claimed", {"step": row["next_step"], "attempt": row["attempts"] + 1})
            return {"id": row["id"], "task_id": row["task_id"], "step": row["next_step"],
                    "token": token, "results": self._results(conn, row["id"])}

    def checkpoint(self, claim: dict, result: dict) -> bool:
        """Commit measured output only while this worker still owns the lease."""
        assert_no_secrets("Worker result", result)
        encoded = json.dumps(result, sort_keys=True)
        if len(encoded.encode("utf-8")) > 262144 or type(result.get("ok")) is not bool:
            raise ValueError("Invalid or oversized worker result")
        with self._transaction() as conn:
            row, now = self._job(conn, claim["id"]), self.clock()
            if (row["status"] != "running" or row["lease_token"] != claim["token"]
                    or row["next_step"] != claim["step"] or row["lease_until"] <= now):
                return False
            if not self._task_eligible(conn, row["task_id"]):
                conn.execute("UPDATE work_jobs SET status='paused',error='parent_task_ineligible',lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=?", (now, row["id"]))
                self._event(conn, row, "paused", {"reason": "parent_task_ineligible"})
                return False
            conn.execute("INSERT INTO work_checkpoints VALUES(?,?,?,?)", (row["id"], row["next_step"], encoded, now))
            next_step = row["next_step"] + int(result["ok"])
            status = ("succeeded" if next_step == len(STEPS) else "queued") if result["ok"] else "failed"
            conn.execute(
                "UPDATE work_jobs SET status=?,next_step=?,attempts=0,lease_token=NULL,lease_until=NULL,error=?,updated_at=? WHERE id=?",
                (status, next_step, "" if result["ok"] else "check_failed", now, row["id"]),
            )
            self._event(conn, row, "checkpoint", {"step": row["next_step"], "status": status, "ok": result["ok"]})
            return True
