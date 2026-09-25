"""Durable execution records for existing tasks; not a second task manager.

Python checks may repeat interrupted reads. Approved text model jobs use a
separate durable sending marker: never automatically repeat a paid request.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
import json
import time
import uuid

from leon_control_plane.secret_scanner import assert_no_secrets
from leon_control_plane.store import ControlPlaneStore
from leon_control_plane import model_work
from leon_control_plane.openai_text import KIND as MODEL_KIND

KIND = "python_syntax_check"
STEPS = ("snapshot", "syntax", "report")
JOB_STEPS = {KIND: STEPS, MODEL_KIND: ("model",)}
MAX_ATTEMPTS = 3
LEASE_SECONDS = 30


class WorkQueue:
    def __init__(self, store: ControlPlaneStore, *, clock=time.time, local_model_config=None):
        self.store, self.clock = store, clock
        self.local_model_config = local_model_config
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
                CREATE TABLE IF NOT EXISTS agent_run_work (
                    job_id TEXT PRIMARY KEY REFERENCES work_jobs(id),
                    agent_run_id TEXT NOT NULL UNIQUE REFERENCES agent_runs(id),
                    assignment_proposal_id TEXT NOT NULL UNIQUE REFERENCES agent_assignment_proposals(id),
                    synced_at REAL
                );
            """)
            model_work.initialize(conn)
        self.recover_agent_run_jobs()
        self.reconcile_agent_runs()

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
            task_id=job["task_id"], summary=f"Work execution: {event}",
            redacted_payload={"job_id": job["id"], **(detail or {})},
        )

    @staticmethod
    def _results(conn, job_id):
        return [json.loads(row[0]) for row in conn.execute(
            "SELECT result_json FROM work_checkpoints WHERE job_id = ? ORDER BY step", (job_id,),
        )]

    def _view(self, conn, row):
        model_details = model_work.view(conn, row["id"]) if row["kind"] == MODEL_KIND else {"provider_calls_made": False}
        return {key: row[key] for key in (
            "id", "request_id", "task_id", "kind", "status", "attempts", "error", "created_at", "updated_at",
        )} | {
            "completed_steps": row["next_step"], "total_steps": len(JOB_STEPS[row["kind"]]),
            "results": self._results(conn, row["id"]),
            "execution_kind": ("local_gpu_text" if model_details.get("provider") == "ollama" else "approved_external_text") if row["kind"] == MODEL_KIND else "local_read_only",
            **model_details,
        }

    def get(self, job_id):
        with closing(self.store.connect()) as conn:
            return self._view(conn, self._job(conn, job_id))

    def list(self):
        with closing(self.store.connect()) as conn:
            return [self._view(conn, row) for row in conn.execute(
                "SELECT * FROM work_jobs ORDER BY created_at DESC, id DESC LIMIT 100",
            )]

    def find_request(self, request_id):
        try:
            normalized = str(uuid.UUID(request_id))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("request_id must be a UUID") from None
        with closing(self.store.connect()) as conn:
            row = conn.execute("SELECT * FROM work_jobs WHERE request_id=?", (normalized,)).fetchone()
            return self._view(conn, row) if row is not None else None

    def enqueue(self, *, task_id: str, request_id: str, kind: str = KIND, model_request=None):
        if kind not in JOB_STEPS or (kind != MODEL_KIND and model_request is not None):
            raise ValueError("Unsupported work kind or model request")
        approved = model_work.prepare(model_request) if kind == MODEL_KIND else None
        try:
            request_id = str(uuid.UUID(request_id))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("request_id must be a UUID") from None
        with self._transaction() as conn:
            existing = conn.execute("SELECT * FROM work_jobs WHERE request_id = ?", (request_id,)).fetchone()
            if existing:
                if existing["task_id"] != task_id or existing["kind"] != kind:
                    raise ValueError("request_id is already bound to different work")
                if approved is not None and not model_work.same_request(conn, existing["id"], approved):
                    raise ValueError("request_id is already bound to different approved text or limits")
                return self._view(conn, existing)
            if not self._task_eligible(conn, task_id):
                raise ValueError("Task must be new/planned/active without a pending approval requirement")
            if approved is not None and not model_work._eligible(self, conn, {"task_id": task_id}):
                raise ValueError("Model jobs require a low-risk task")
            if conn.execute("SELECT COUNT(*) FROM work_jobs WHERE status IN ('queued','running','paused')").fetchone()[0] >= 100:
                raise ValueError("Local work queue is full")
            job_id, now = f"work-{uuid.uuid4().hex}", self.clock()
            conn.execute(
                "INSERT INTO work_jobs(id,request_id,task_id,kind,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (job_id, request_id, task_id, kind, "queued", now, now),
            )
            row = self._job(conn, job_id)
            if approved is not None:
                model_work.insert(conn, job_id, approved)
            self._event(conn, row, "queued")
            return self._view(conn, row)

    def enqueue_agent_run(
        self,
        *,
        task_id: str,
        agent_run_id: str,
        assignment_proposal_id: str,
        prompt: str,
        max_output_tokens: int = 768,
    ):
        """Queue one idempotent, loopback-only model call for an approved agent run."""

        model_request = {
            "prompt": prompt,
            "max_output_tokens": max_output_tokens,
            "max_cost_microusd": 1,
            "approve_external_text": True,
        }
        approved = model_work.prepare(model_request, local_config=self.local_model_config)
        if json.loads(approved)["payload"].get("provider") != "ollama":
            raise ValueError("Local agent runs require the loopback Ollama provider")
        request_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"leon-agent-assignment:{assignment_proposal_id}"))
        with self._transaction() as conn:
            binding = conn.execute(
                "SELECT job_id, agent_run_id FROM agent_run_work WHERE assignment_proposal_id = ?",
                (assignment_proposal_id,),
            ).fetchone()
            if binding is not None:
                if binding["agent_run_id"] != agent_run_id:
                    raise ValueError("Assignment proposal is already bound to a different agent run")
                return self._view(conn, self._job(conn, binding["job_id"]))
            run = conn.execute(
                "SELECT task_id, status, risk FROM agent_runs WHERE id = ?",
                (agent_run_id,),
            ).fetchone()
            assignment = conn.execute(
                "SELECT task_id, status, runner_kind, applied_agent_run_id FROM agent_assignment_proposals WHERE id = ?",
                (assignment_proposal_id,),
            ).fetchone()
            if run is None or run["task_id"] != task_id or run["status"] != "running":
                raise ValueError("Agent run is not eligible for local model work")
            if str(run["risk"]).lower() in {"high", "r4", "r5"}:
                raise ValueError("High-risk agent runs cannot use the local model queue")
            if (
                assignment is None
                or assignment["task_id"] != task_id
                or assignment["status"] != "applied"
                or assignment["runner_kind"] != "local_ollama"
                or assignment["applied_agent_run_id"] != agent_run_id
            ):
                raise ValueError("Agent assignment has not authorized this local model run")
            if not self._task_eligible(conn, task_id):
                raise ValueError("Task must remain eligible for local agent execution")
            if conn.execute("SELECT COUNT(*) FROM work_jobs WHERE status IN ('queued','running','paused')").fetchone()[0] >= 100:
                raise ValueError("Local work queue is full")
            job_id, now = f"work-{uuid.uuid4().hex}", self.clock()
            conn.execute(
                "INSERT INTO work_jobs(id,request_id,task_id,kind,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (job_id, request_id, task_id, MODEL_KIND, "queued", now, now),
            )
            model_work.insert(conn, job_id, approved)
            conn.execute(
                "INSERT INTO agent_run_work(job_id,agent_run_id,assignment_proposal_id) VALUES(?,?,?)",
                (job_id, agent_run_id, assignment_proposal_id),
            )
            row = self._job(conn, job_id)
            self._event(conn, row, "queued", {"agent_run_id": agent_run_id})
            return self._view(conn, row)

    def recover_agent_run_jobs(self) -> int:
        """Recreate a missing durable job after a crash between apply and enqueue."""

        with closing(self.store.connect()) as conn:
            rows = list(conn.execute(
                """
                SELECT p.id AS proposal_id, p.task_id, p.applied_agent_run_id, p.proposal_json
                FROM agent_assignment_proposals p
                JOIN agent_runs r ON r.id = p.applied_agent_run_id
                LEFT JOIN agent_run_work b ON b.assignment_proposal_id = p.id
                WHERE p.status = 'applied' AND p.runner_kind = 'local_ollama'
                  AND r.status = 'running' AND b.job_id IS NULL
                ORDER BY p.created_at, p.id
                """
            ))
        recovered = 0
        for row in rows:
            try:
                from leon_control_plane.agent_runtime import build_local_agent_prompt

                proposal = json.loads(row["proposal_json"])
                prompt = build_local_agent_prompt(proposal.get("task_packet") or {})
                self.enqueue_agent_run(
                    task_id=row["task_id"],
                    agent_run_id=row["applied_agent_run_id"],
                    assignment_proposal_id=row["proposal_id"],
                    prompt=prompt,
                )
                recovered += 1
            except (ValueError, json.JSONDecodeError):
                # Configuration may be temporarily unavailable during service
                # startup. The long-running worker retries this reconciliation.
                continue
        return recovered

    def reconcile_agent_runs(self) -> int:
        """Project terminal queue results into their reviewable agent runs."""

        with closing(self.store.connect()) as conn:
            rows = list(conn.execute(
                """
                SELECT b.job_id, b.agent_run_id, b.assignment_proposal_id, j.status, j.error
                FROM agent_run_work b
                JOIN work_jobs j ON j.id = b.job_id
                JOIN agent_runs r ON r.id = b.agent_run_id
                WHERE b.synced_at IS NULL AND r.status = 'running'
                  AND j.status IN ('succeeded','failed','cancelled')
                ORDER BY j.created_at, j.id
                """
            ))
        synced = 0
        for row in rows:
            with closing(self.store.connect()) as conn:
                results = self._results(conn, row["job_id"])
                details = model_work.view(conn, row["job_id"])
            if row["status"] == "succeeded" and results and results[-1].get("ok") is True:
                result = results[-1]
                text = str(result.get("text") or "").strip()
                encoded = text.encode("utf-8")[:16384]
                while True:
                    try:
                        summary = encoded.decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        encoded = encoded[:-1]
                evidence = [
                    {
                        "type": "local_model",
                        "summary": "Text-only result generated by the loopback Ollama worker on the local M40.",
                        "provider": details.get("provider"),
                        "model": details.get("model"),
                        "accounted_microusd": details.get("accounted_microusd", 0),
                    },
                    {
                        "type": "assignment_gate",
                        "summary": "Run started from an explicitly applied agent assignment and still requires human review.",
                        "agent_assignment_proposal_id": row["assignment_proposal_id"],
                    },
                    {
                        "type": "safety",
                        "summary": "No tools, shell commands, file writes, account access, external provider calls, or raw secret reads were available.",
                    },
                ]
                self.store.complete_agent_run(
                    row["agent_run_id"], result_summary=summary, evidence=evidence,
                    actor_id="local-ollama-agent-worker",
                )
            else:
                reason = "Local agent model work was cancelled." if row["status"] == "cancelled" else "Local agent model work failed after bounded retries."
                self.store.complete_agent_run(
                    row["agent_run_id"], result_summary=reason,
                    evidence=[{
                        "type": "local_model_failure",
                        "summary": reason,
                        "job_id": row["job_id"],
                        "reason": row["error"] or "check_failed",
                    }],
                    status="failed",
                    recovery_suggestions=[{"action": "create_new_assignment", "summary": "Check Ollama health and create a new assignment proposal."}],
                    actor_id="local-ollama-agent-worker",
                )
            with self._transaction() as conn:
                conn.execute("UPDATE agent_run_work SET synced_at = ? WHERE job_id = ?", (self.clock(), row["job_id"]))
            synced += 1
        return synced

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
                    "kind": row["kind"], "token": token, "results": self._results(conn, row["id"])}

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
            if (row["kind"] == MODEL_KIND and result.get("retry_allowed") is True
                    and result.get("provider_calls_made") is False):
                conn.execute(
                    "UPDATE work_jobs SET status='queued',lease_token=NULL,lease_until=NULL,error='local_model_retry',updated_at=? WHERE id=?",
                    (now, row["id"]),
                )
                self._event(conn, row, "retry_queued", {"step": row["next_step"], "attempt": row["attempts"]})
                return True
            conn.execute("INSERT INTO work_checkpoints VALUES(?,?,?,?)", (row["id"], row["next_step"], encoded, now))
            next_step = row["next_step"] + int(result["ok"])
            status = ("succeeded" if next_step == len(JOB_STEPS[row["kind"]]) else "queued") if result["ok"] else "failed"
            conn.execute(
                "UPDATE work_jobs SET status=?,next_step=?,attempts=0,lease_token=NULL,lease_until=NULL,error=?,updated_at=? WHERE id=?",
                (status, next_step, "" if result["ok"] else "check_failed", now, row["id"]),
            )
            self._event(conn, row, "checkpoint", {"step": row["next_step"], "status": status, "ok": result["ok"]})
            return True
