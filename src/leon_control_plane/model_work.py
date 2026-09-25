"""Approved text-only calls and durable cost accounting beside WorkQueue.

The sending marker commits before HTTP. A crash after that point is ambiguous,
not permission to retry. A separate database is a separate budget boundary.
"""
from __future__ import annotations

import hashlib
import json

from leon_control_plane.openai_text import (
    ModelPreflightError, OpenAIConfig, parse_response, positive_int, request_payload, reservation, send_response,
)
from leon_control_plane.local_model import (
    LocalModelConfig, parse_response as parse_local_response, request_payload as local_request_payload,
    send_response as send_local_response, is_busy as local_model_is_busy,
)
from leon_control_plane.secret_scanner import assert_no_secrets
from leon_control_plane import model_receipts


def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS model_work (
        job_id TEXT PRIMARY KEY REFERENCES work_jobs(id), approved_json TEXT NOT NULL,
        digest TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'approved',
        held_microusd INTEGER NOT NULL DEFAULT 0, charged_microusd INTEGER NOT NULL DEFAULT 0,
        sent_at REAL, result_json TEXT
    )""")
    model_receipts.initialize(conn)


def _route(prompt, max_output_tokens, local_config=None, *, provider=None, local_busy=False):
    local_config = local_config if local_config is not None else LocalModelConfig.from_env()
    if local_config.enabled and (provider == "ollama" or (provider is None and not local_busy)):
        return local_request_payload(prompt, max_output_tokens, local_config), 0
    if provider == "ollama":
        return local_request_payload(prompt, max_output_tokens, local_config), 0
    if provider not in {None, "openai"}:
        raise ValueError("Unsupported model provider")
    payload = request_payload(prompt, max_output_tokens)
    return payload, reservation(payload)


def prepare(details, *, local_config=None, local_busy=False):
    if not isinstance(details, dict) or set(details) - {
        "prompt", "max_output_tokens", "max_cost_microusd", "approve_external_text", "provider",
    } or not {"prompt", "max_output_tokens", "max_cost_microusd", "approve_external_text"}.issubset(details):
        raise ValueError("Expected exact shared text, output limit, cost cap and explicit approval")
    if details["approve_external_text"] is not True:
        raise ValueError("Explicit external-text and cost approval is required")
    payload, hold = _route(details["prompt"], details["max_output_tokens"], local_config,
                           provider=details.get("provider"), local_busy=local_busy)
    cap = positive_int(details["max_cost_microusd"], "per-call cost cap", 1_000_000)
    if hold > cap:
        raise ValueError("Approved cost cap is below the conservative reservation")
    return json.dumps({"payload": payload, "max_cost_microusd": cap}, sort_keys=True)


def insert(conn, job_id, approved_json):
    conn.execute("INSERT INTO model_work(job_id,approved_json,digest) VALUES(?,?,?)",
                 (job_id, approved_json, hashlib.sha256(approved_json.encode()).hexdigest()))


def preview(details, *, local_busy=False):
    """Local validation/quote only: no job, approval, reservation or provider call."""
    if not isinstance(details, dict) or set(details) - {"prompt", "max_output_tokens", "max_cost_microusd", "provider"} or not {"prompt", "max_output_tokens", "max_cost_microusd"}.issubset(details):
        raise ValueError("Expected shared text, output limit and cost cap")
    approved = json.loads(prepare({**details, "approve_external_text": True}, local_busy=local_busy))
    payload = approved["payload"]
    hold = 0 if payload.get("provider") == "ollama" else reservation(payload)
    return {"model": payload["model"], "provider": payload.get("provider", "openai"), "reserved_microusd": hold,
            "max_cost_microusd": approved["max_cost_microusd"], "provider_calls_made": False,
            "prompt_bytes": len(details["prompt"].encode("utf-8")), "execution_allowed": False}


def same_request(conn, job_id, approved_json):
    row = conn.execute("SELECT approved_json FROM model_work WHERE job_id=?", (job_id,)).fetchone()
    return row is not None and row[0] == approved_json


def view(conn, job_id):
    row = conn.execute("SELECT * FROM model_work WHERE job_id=?", (job_id,)).fetchone()
    if row is None:
        return {"provider_calls_made": None, "model_state": "missing_request"}
    approved = json.loads(row["approved_json"])
    return {"provider_calls_made": None if row["state"] in {"sending", "unknown"} else row["sent_at"] is not None,
            "model_state": row["state"], "reserved_microusd": row["held_microusd"],
            "accounted_microusd": row["charged_microusd"], "approval_sha256": row["digest"],
            "provider": approved["payload"].get("provider", "openai"), "model": approved["payload"]["model"]}


def _eligible(queue, conn, job):
    task = conn.execute("SELECT risk_level FROM tasks WHERE id=?", (job["task_id"],)).fetchone()
    if not queue._task_eligible(conn, job["task_id"]):
        return False
    try:
        job_id = job["id"]
    except (KeyError, IndexError):
        job_id = job.get("job_id") if isinstance(job, dict) else None
    binding = conn.execute(
        """
        SELECT r.status AS run_status, r.risk, p.status AS proposal_status, p.runner_kind
        FROM agent_run_work b
        JOIN agent_runs r ON r.id = b.agent_run_id
        JOIN agent_assignment_proposals p ON p.id = b.assignment_proposal_id
        WHERE b.job_id = ?
        """,
        (job_id,),
    ).fetchone()
    if binding is not None:
        return (
            binding["run_status"] == "running"
            and binding["proposal_status"] == "applied"
            and binding["runner_kind"] == "local_ollama"
            and str(binding["risk"]).lower() not in {"high", "r4", "r5"}
        )
    return task[0] in {"low", "R0", "R1"}


def _unknown():
    return {"ok": False, "step": "model", "reason": "provider_outcome_unknown",
            "provider_calls_made": None, "retry_allowed": False}


class ModelExecutor:
    def __init__(self, queue, *, config=None, transport=send_response, local_config=None, local_transport=send_local_response):
        self.queue = queue
        self.config = config if config is not None else OpenAIConfig.from_env()
        self.transport = transport
        self.local_config = local_config if local_config is not None else LocalModelConfig.from_env()
        self.local_transport = local_transport

    def _begin(self, claim):
        queue = self.queue
        with queue._transaction() as conn:
            job, now = queue._job(conn, claim["id"]), queue.clock()
            if (job["status"] != "running" or job["lease_token"] != claim["token"]
                    or job["lease_until"] <= now or job["next_step"] != claim["step"]):
                raise ValueError("Worker lease no longer authorizes execution")
            row = conn.execute("SELECT * FROM model_work WHERE job_id=?", (job["id"],)).fetchone()
            if row is None:
                raise ValueError("Missing approved model request")
            # Stored evidence is safe to reuse even when a provider is disabled.
            if row["result_json"] is not None:
                return None, json.loads(row["result_json"])
            if hashlib.sha256(row["approved_json"].encode()).hexdigest() != row["digest"]:
                raise ValueError("Approved request integrity mismatch")
            approved = json.loads(row["approved_json"])
            payload = approved["payload"]
            is_local = payload.get("provider") == "ollama"
            if row["state"] in {"sending", "unknown"} and not is_local:
                conn.execute("UPDATE model_work SET state='unknown' WHERE job_id=?", (job["id"],))
                queue._event(conn, job, "model_unknown")
                return None, _unknown()
            if is_local:
                self.local_config.validate()
            else:
                self.config.validate()
            if not _eligible(queue, conn, job):
                raise ValueError("Model execution requires an eligible low-risk task")
            # Model generation may legitimately outlive the queue's short
            # claim lease, especially while Ollama loads a cold model. Extend
            # the same fenced lease before sending; checkpoint still requires
            # the original token and rejects any stale worker.
            if is_local:
                execution_window = self.local_config.timeout_seconds + 30
                conn.execute(
                    "UPDATE work_jobs SET lease_until = ?, updated_at = ? WHERE id = ? AND lease_token = ?",
                    (now + execution_window, now, job["id"], claim["token"]),
                )
            # Revalidate the complete wire request, including the current model route.
            expected = (local_request_payload(payload["input"], payload["max_output_tokens"], self.local_config)
                        if is_local else request_payload(payload["input"], payload["max_output_tokens"]))
            if payload != expected:
                raise ValueError("Approved request no longer matches the execution contract")
            hold = 0 if is_local else reservation(payload)
            if hold > approved["max_cost_microusd"]:
                raise ValueError("Approved reservation exceeded")
            if not is_local and conn.execute("SELECT 1 FROM model_work WHERE state='unknown' LIMIT 1").fetchone():
                raise ModelPreflightError("openai_reconciliation_required")
            day_start = int(now // 86400) * 86400  # UTC budget days, explicit in docs.
            total, daily = conn.execute("""SELECT
                COALESCE(SUM(held_microusd+charged_microusd),0),
                COALESCE(SUM(held_microusd+CASE WHEN sent_at>=? THEN charged_microusd ELSE 0 END),0)
                FROM model_work""", (day_start,)).fetchone()
            if not is_local and (total + hold > self.config.total_microusd or daily + hold > self.config.daily_microusd):
                raise ModelPreflightError("openai_budget_exhausted")
            conn.execute("UPDATE model_work SET state='sending',held_microusd=?,sent_at=? WHERE job_id=?",
                         (hold, now, job["id"]))
            queue._event(conn, job, "model_send_authorized", {"reserved_microusd": hold, "approval_sha256": row["digest"]})
            return payload, None

    def execute(self, claim):
        payload, cached = self._begin(claim)
        if cached is not None:
            return cached
        try:
            is_local = payload.get("provider") == "ollama"
            if is_local:
                observed = self.local_transport(payload, self.local_config)
                result = parse_local_response(observed, payload)
            else:
                observed = self.transport(payload, self.config.api_key)
                # Persist validated usage before answer parsing can fail or the process dies.
                # Never store raw output, response bodies or credentials in this receipt.
                model_receipts.record(self.queue, claim["id"], payload, observed)
                result = parse_response(observed, payload)
            assert_no_secrets("Model result", result)
        except Exception:
            # HTTP status, parse, usage and transport errors can all be ambiguous.
            # No raw provider body, exception or credential in SQLite/audit/output.
            result = ({"ok": False, "step": "model", "reason": "local_model_unavailable",
                       "provider": "ollama", "provider_calls_made": False, "retry_allowed": True,
                       "accounted_microusd": 0} if payload.get("provider") == "ollama" else _unknown())
        encoded = json.dumps(result, sort_keys=True)
        with self.queue._transaction() as conn:
            row = self.queue._job(conn, claim["id"])
            ledger = conn.execute("SELECT state,result_json FROM model_work WHERE job_id=?", (claim["id"],)).fetchone()
            if ledger["state"] == "reconciled":
                # A late worker must not undo an approved cost-only recovery.
                return json.loads(ledger["result_json"])
            if result["provider_calls_made"] is True:
                conn.execute("UPDATE model_work SET state='settled',held_microusd=0,charged_microusd=?,result_json=? WHERE job_id=?",
                             (result["accounted_microusd"], encoded, claim["id"]))
            elif payload.get("provider") == "ollama":
                # A loopback-only generation has no paid or external side effect.
                # Leave it retryable so the durable queue can survive a local
                # model service restart without caching a transient failure.
                conn.execute("UPDATE model_work SET state='approved',held_microusd=0,result_json=NULL WHERE job_id=?", (claim["id"],))
            else:
                conn.execute("UPDATE model_work SET state='unknown',result_json=? WHERE job_id=?", (encoded, claim["id"]))
            # Billing evidence survives cancellation/lease expiry. Queue checkpoint
            # still requires its original fence; an in-flight HTTP call cannot be undone.
            self.queue._event(conn, row, "model_result_recorded", {"outcome_verified": result["provider_calls_made"] is True})
        return result
