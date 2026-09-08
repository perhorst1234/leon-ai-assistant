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
from leon_control_plane.secret_scanner import assert_no_secrets


def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS model_work (
        job_id TEXT PRIMARY KEY REFERENCES work_jobs(id), approved_json TEXT NOT NULL,
        digest TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'approved',
        held_microusd INTEGER NOT NULL DEFAULT 0, charged_microusd INTEGER NOT NULL DEFAULT 0,
        sent_at REAL, result_json TEXT
    )""")


def prepare(details):
    if not isinstance(details, dict) or set(details) != {
        "prompt", "max_output_tokens", "max_cost_microusd", "approve_external_text",
    }:
        raise ValueError("Expected exact shared text, output limit, cost cap and explicit approval")
    if details["approve_external_text"] is not True:
        raise ValueError("Explicit external-text and cost approval is required")
    payload = request_payload(details["prompt"], details["max_output_tokens"])
    cap = positive_int(details["max_cost_microusd"], "per-call cost cap", 1_000_000)
    if reservation(payload) > cap:
        raise ValueError("Approved cost cap is below the conservative reservation")
    return json.dumps({"payload": payload, "max_cost_microusd": cap}, sort_keys=True)


def insert(conn, job_id, approved_json):
    conn.execute("INSERT INTO model_work(job_id,approved_json,digest) VALUES(?,?,?)",
                 (job_id, approved_json, hashlib.sha256(approved_json.encode()).hexdigest()))


def preview(details):
    """Local validation/quote only: no job, approval, reservation or provider call."""
    if not isinstance(details, dict) or set(details) != {"prompt", "max_output_tokens", "max_cost_microusd"}:
        raise ValueError("Expected shared text, output limit and cost cap")
    approved = json.loads(prepare({**details, "approve_external_text": True}))
    return {"model": approved["payload"]["model"], "reserved_microusd": reservation(approved["payload"]),
            "max_cost_microusd": approved["max_cost_microusd"], "provider_calls_made": False,
            "prompt_bytes": len(details["prompt"].encode("utf-8")), "execution_allowed": False}


def same_request(conn, job_id, approved_json):
    row = conn.execute("SELECT approved_json FROM model_work WHERE job_id=?", (job_id,)).fetchone()
    return row is not None and row[0] == approved_json


def view(conn, job_id):
    row = conn.execute("SELECT * FROM model_work WHERE job_id=?", (job_id,)).fetchone()
    if row is None:
        return {"provider_calls_made": None, "model_state": "missing_request"}
    return {"provider_calls_made": None if row["state"] in {"sending", "unknown"} else row["sent_at"] is not None,
            "model_state": row["state"], "reserved_microusd": row["held_microusd"],
            "accounted_microusd": row["charged_microusd"], "approval_sha256": row["digest"]}


def _eligible(queue, conn, job):
    task = conn.execute("SELECT risk_level FROM tasks WHERE id=?", (job["task_id"],)).fetchone()
    return queue._task_eligible(conn, job["task_id"]) and task[0] in {"low", "R0", "R1"}


def _unknown():
    return {"ok": False, "step": "model", "reason": "provider_outcome_unknown",
            "provider_calls_made": None, "retry_allowed": False}


class ModelExecutor:
    def __init__(self, queue, *, config=None, transport=send_response):
        self.queue = queue
        self.config = config if config is not None else OpenAIConfig.from_env()
        self.transport = transport

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
            # Stored evidence is safe to reuse even when the provider is disabled.
            if row["result_json"] is not None:
                return None, json.loads(row["result_json"])
            if row["state"] in {"sending", "unknown"}:
                conn.execute("UPDATE model_work SET state='unknown' WHERE job_id=?", (job["id"],))
                queue._event(conn, job, "model_unknown")
                return None, _unknown()
            self.config.validate()
            if not _eligible(queue, conn, job):
                raise ValueError("Model execution requires an eligible low-risk task")
            if hashlib.sha256(row["approved_json"].encode()).hexdigest() != row["digest"]:
                raise ValueError("Approved request integrity mismatch")
            approved = json.loads(row["approved_json"])
            payload = approved["payload"]
            # Revalidate the complete wire request, including the current model route.
            if payload != request_payload(payload["input"], payload["max_output_tokens"]):
                raise ValueError("Approved request no longer matches the execution contract")
            hold = reservation(payload)
            if hold > approved["max_cost_microusd"]:
                raise ValueError("Approved reservation exceeded")
            if conn.execute("SELECT 1 FROM model_work WHERE state='unknown' LIMIT 1").fetchone():
                raise ModelPreflightError("openai_reconciliation_required")
            day_start = int(now // 86400) * 86400  # UTC budget days, explicit in docs.
            total, daily = conn.execute("""SELECT
                COALESCE(SUM(held_microusd+charged_microusd),0),
                COALESCE(SUM(held_microusd+CASE WHEN sent_at>=? THEN charged_microusd ELSE 0 END),0)
                FROM model_work""", (day_start,)).fetchone()
            if total + hold > self.config.total_microusd or daily + hold > self.config.daily_microusd:
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
            result = parse_response(self.transport(payload, self.config.api_key), payload)
            assert_no_secrets("Model result", result)
        except Exception:
            # HTTP status, parse, usage and transport errors can all be ambiguous.
            # No raw provider body, exception or credential in SQLite/audit/output.
            result = _unknown()
        encoded = json.dumps(result, sort_keys=True)
        with self.queue._transaction() as conn:
            row = self.queue._job(conn, claim["id"])
            if result["provider_calls_made"] is True:
                conn.execute("UPDATE model_work SET state='settled',held_microusd=0,charged_microusd=?,result_json=? WHERE job_id=?",
                             (result["accounted_microusd"], encoded, claim["id"]))
            else:
                conn.execute("UPDATE model_work SET state='unknown',result_json=? WHERE job_id=?", (encoded, claim["id"]))
            # Billing evidence survives cancellation/lease expiry. Queue checkpoint
            # still requires its original fence; an in-flight HTTP call cannot be undone.
            self.queue._event(conn, row, "model_result_recorded", {"outcome_verified": result["provider_calls_made"] is True})
        return result
