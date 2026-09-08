"""Cost-only recovery from usage actually observed by the one-shot transport.

No receipt imports, arbitrary charges, provider calls or successful task evidence.
The local database is trusted; hashes bind approvals, not proof against a DB owner.
"""
from contextlib import closing
import hashlib
import json

from leon_control_plane.openai_text import parse_usage


def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS model_usage_receipts (
        job_id TEXT PRIMARY KEY REFERENCES model_work(job_id),
        receipt_json TEXT NOT NULL, receipt_sha256 TEXT NOT NULL
    )""")


def record(queue, job_id, payload, data):
    usage = parse_usage(data, payload)
    with queue._transaction() as conn:
        job = queue._job(conn, job_id)
        row = conn.execute("SELECT * FROM model_work WHERE job_id=?", (job_id,)).fetchone()
        if row is None or row["sent_at"] is None or json.loads(row["approved_json"])["payload"] != payload:
            raise ValueError("Usage does not match an authorized send")
        receipt = {"job_id": job_id, "request_id": job["request_id"], "approval_sha256": row["digest"], **usage}
        encoded = json.dumps(receipt, sort_keys=True)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        existing = conn.execute("SELECT receipt_sha256 FROM model_usage_receipts WHERE job_id=?", (job_id,)).fetchone()
        if existing:
            if existing[0] != digest:
                raise ValueError("Conflicting provider usage")
            return
        conn.execute("INSERT INTO model_usage_receipts VALUES(?,?,?)", (job_id, encoded, digest))
        queue._event(conn, job, "model_usage_observed", {"receipt_sha256": digest})


def _proposal(queue, conn, job_id):
    job = queue._job(conn, job_id)
    row = conn.execute("SELECT * FROM model_work WHERE job_id=?", (job_id,)).fetchone()
    receipt = conn.execute("SELECT * FROM model_usage_receipts WHERE job_id=?", (job_id,)).fetchone()
    if row is None or row["state"] not in {"unknown", "reconciled"} or receipt is None:
        raise ValueError("No recoverable observed usage; reservation remains unchanged")
    if hashlib.sha256(receipt["receipt_json"].encode()).hexdigest() != receipt["receipt_sha256"]:
        raise ValueError("Usage receipt integrity mismatch")
    if hashlib.sha256(row["approved_json"].encode()).hexdigest() != row["digest"]:
        raise ValueError("Approved request integrity mismatch")
    observed = json.loads(receipt["receipt_json"])
    if (observed["job_id"], observed["request_id"], observed["approval_sha256"]) != (job_id, job["request_id"], row["digest"]):
        raise ValueError("Usage receipt belongs to different work")
    usage = parse_usage({"model": observed["model"], "status": observed["provider_status"],
                         "usage": {key: observed[key] for key in ("input_tokens", "output_tokens")}},
                        json.loads(row["approved_json"])["payload"])
    if any(observed[key] != value for key, value in usage.items()):
        raise ValueError("Usage receipt accounting mismatch")
    charge = usage["accounted_microusd"]
    if row["state"] == "unknown" and charge > row["held_microusd"]:
        raise ValueError("Observed usage exceeds reservation; review required")
    return {"job_id": job_id, "receipt_sha256": receipt["receipt_sha256"], **usage,
            "reserved_microusd": row["held_microusd"], "model_state": row["state"],
            "billing_basis": "conservative_usage_not_invoice", "retry_allowed": False,
            "task_completed": False}


def preview(queue, job_id):
    with closing(queue.store.connect()) as conn:
        return _proposal(queue, conn, job_id)


def reconcile(queue, job_id, receipt_sha256, approved):
    if approved is not True or not isinstance(receipt_sha256, str):
        raise ValueError("Explicit approval of the observed usage receipt is required")
    with queue._transaction() as conn:
        proposal = _proposal(queue, conn, job_id)
        if receipt_sha256 != proposal["receipt_sha256"]:
            raise ValueError("Receipt changed; review the current proposal")
        job = queue._job(conn, job_id)
        if proposal["model_state"] != "reconciled":
            # Do not manufacture a model answer or rewrite an earlier failure checkpoint.
            result = {"ok": False, "step": "model", "reason": "answer_unavailable_cost_reconciled",
                      "provider_calls_made": True, "retry_allowed": False,
                      "billing_basis": proposal["billing_basis"], "accounted_microusd": proposal["accounted_microusd"]}
            conn.execute("UPDATE model_work SET state='reconciled',held_microusd=0,charged_microusd=?,result_json=? WHERE job_id=?",
                         (proposal["accounted_microusd"], json.dumps(result, sort_keys=True), job_id))
            queue._event(conn, job, "model_cost_reconciled", {"receipt_sha256": receipt_sha256,
                         "accounted_microusd": proposal["accounted_microusd"], "approval_source": "dashboard_bearer"})
        return queue._view(conn, job)
