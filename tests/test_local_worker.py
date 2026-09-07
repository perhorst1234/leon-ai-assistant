import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest

from leon_control_plane.local_worker import CheckError, LocalWorker, source_snapshot
from leon_control_plane.work_api import work_request
from leon_control_plane.work_queue import LEASE_SECONDS, WorkQueue
from test_control_plane import http_json, make_store, run_test_http_server


@pytest.fixture
def work(tmp_path):
    store = make_store(tmp_path)
    now = [1000.0]
    queue = WorkQueue(store, clock=lambda: now[0])
    task_id = store.create_task(title="Check Python sources", goal="Measure syntax only", risk_level="low")
    root = tmp_path / "project"
    source = root / "src" / "leon_control_plane"
    source.mkdir(parents=True)
    (source / "sample.py").write_text("answer = 42\n", encoding="utf-8")
    job = queue.enqueue(task_id=task_id, request_id=str(uuid.uuid4()))
    return queue, LocalWorker(queue, root=root), job, source, now


def finish(worker):
    for _ in range(4):
        worker.run_once()


def test_real_check_persists_hashes_and_does_not_complete_parent(work):
    queue, worker, job, source, _ = work
    finish(worker)
    result = WorkQueue(queue.store).get(job["id"])
    assert result["status"] == "succeeded"
    assert result["completed_steps"] == result["total_steps"] == 3
    assert result["results"][0]["files"][0]["sha256"] == hashlib.sha256((source / "sample.py").read_bytes()).hexdigest()
    assert result["results"][1]["files_checked"] == 1
    assert result["provider_calls_made"] is False
    assert "lease_token" not in json.dumps(result)
    assert queue.store.get_task(job["task_id"])["status"] == "new"
    assert queue.store.validate_audit_hash_chain()


def test_idempotency_returns_same_job_after_completion_and_rejects_rebinding(work):
    queue, worker, job, _, _ = work
    request_id = str(uuid.uuid4())
    one = queue.enqueue(task_id=job["task_id"], request_id=request_id)
    two = queue.enqueue(task_id=job["task_id"], request_id=request_id)
    assert one["id"] == two["id"]
    other_task = queue.store.create_task(title="Other", goal="Different work")
    with pytest.raises(ValueError, match="different work"):
        queue.enqueue(task_id=other_task, request_id=request_id)
    for _ in range(8):
        worker.run_once()
    assert queue.enqueue(task_id=job["task_id"], request_id=request_id)["status"] == "succeeded"


def test_new_worker_resumes_from_saved_checkpoint(work):
    queue, worker, job, _, _ = work
    worker.run_once()
    assert queue.get(job["id"])["completed_steps"] == 1
    restarted_queue = WorkQueue(queue.store, clock=queue.clock)
    finish(LocalWorker(restarted_queue, root=worker.root))
    result = restarted_queue.get(job["id"])
    assert result["status"] == "succeeded"
    assert [item["step"] for item in result["results"]] == ["snapshot", "syntax", "report"]


def test_two_workers_cannot_claim_the_same_live_lease(work):
    queue, _, job, _, _ = work
    other = WorkQueue(queue.store, clock=queue.clock)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda q: q.claim(), [queue, other]))
    assert sum(claim is not None for claim in claims) == 1
    assert queue.get(job["id"])["attempts"] == 1


def test_expired_worker_is_fenced_and_duplicate_checkpoint_is_rejected(work):
    queue, _, job, _, now = work
    stale = queue.claim()
    now[0] += LEASE_SECONDS
    assert queue.checkpoint(stale, {"ok": True}) is False
    current = queue.claim()
    assert current["token"] != stale["token"]
    assert queue.checkpoint(stale, {"ok": True}) is False
    assert queue.checkpoint(current, {"ok": True}) is True
    assert queue.checkpoint(current, {"ok": True}) is False
    assert queue.get(job["id"])["completed_steps"] == 1


def test_repeated_worker_crashes_hit_recovery_limit(work):
    queue, _, job, _, now = work
    for _ in range(3):
        assert queue.claim() is not None
        now[0] += LEASE_SECONDS
    assert queue.claim() is None
    result = queue.get(job["id"])
    assert result["status"] == "failed"
    assert result["error"] == "recovery_limit"
    assert result["results"] == []


def test_pause_resume_and_cancel_invalidate_inflight_worker(work):
    queue, _, job, _, _ = work
    old = queue.claim()
    assert queue.control(job["id"], "pause")["status"] == "paused"
    assert queue.control(job["id"], "pause")["status"] == "paused"
    assert queue.claim() is None
    queue.control(job["id"], "resume")
    new = queue.claim()
    assert queue.checkpoint(old, {"ok": True}) is False
    assert queue.control(job["id"], "cancel")["status"] == "cancelled"
    assert queue.checkpoint(new, {"ok": True}) is False
    assert queue.control(job["id"], "cancel")["status"] == "cancelled"
    with pytest.raises(ValueError):
        queue.control(job["id"], "resume")


def test_source_change_after_restart_fails_without_stale_success(work):
    queue, worker, job, source, _ = work
    worker.run_once()
    (source / "sample.py").write_text("answer = 43\n", encoding="utf-8")
    worker.run_once()
    result = queue.get(job["id"])
    assert result["status"] == "failed"
    assert result["completed_steps"] == 1
    assert result["results"][-1]["reason"] == "source_changed_since_checkpoint"


def test_report_rechecks_source_after_syntax_checkpoint(work):
    queue, worker, job, source, _ = work
    worker.run_once()
    worker.run_once()
    (source / "sample.py").write_text("changed = True\n", encoding="utf-8")
    worker.run_once()
    assert queue.get(job["id"])["status"] == "failed"


def test_invalid_syntax_is_measured_without_exposing_source_text(work):
    queue, worker, job, source, _ = work
    private_line = "do not expose this private source line"
    (source / "sample.py").write_text(private_line + " (\n", encoding="utf-8")
    finish(worker)
    result = queue.get(job["id"])
    assert result["status"] == "failed"
    assert result["results"][-1]["failures"][0]["reason"] == "invalid_python_syntax"
    assert private_line not in json.dumps(result)
    assert result["completed_steps"] == 1


def test_does_not_execute_inspected_python(work):
    queue, worker, job, source, _ = work
    sentinel = worker.root / "must-not-exist"
    (source / "sample.py").write_text(f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n", encoding="utf-8")
    finish(worker)
    assert queue.get(job["id"])["status"] == "succeeded"
    assert not sentinel.exists()


def test_file_limits_and_symlinks_are_rejected(work, monkeypatch):
    _, worker, _, source, _ = work
    monkeypatch.setattr("leon_control_plane.local_worker.MAX_FILE_BYTES", 4)
    with pytest.raises(CheckError, match="size_limit"):
        source_snapshot(worker.root)
    monkeypatch.setattr("leon_control_plane.local_worker.MAX_FILE_BYTES", 1024)
    (source / "link.py").symlink_to(source / "sample.py")
    with pytest.raises(CheckError, match="scope_or_count"):
        source_snapshot(worker.root)


def test_approval_required_task_cannot_be_used_for_execution(work):
    queue, _, _, _, _ = work
    task_id = queue.store.create_task(title="Needs approval", goal="Not yet allowed", approval_required=True)
    with pytest.raises(ValueError, match="approval"):
        queue.enqueue(task_id=task_id, request_id=str(uuid.uuid4()))


def test_parent_becoming_blocked_prevents_claim_and_checkpoint(work):
    queue, _, job, _, _ = work
    claim = queue.claim()
    queue.store.update_task_status(job["task_id"], "planned")
    queue.store.update_task_status(job["task_id"], "active")
    queue.store.update_task_status(job["task_id"], "blocked", blocked_reason="Wait for user")
    assert queue.checkpoint(claim, {"ok": True}) is False
    assert queue.get(job["id"])["status"] == "paused"
    with pytest.raises(ValueError, match="eligible"):
        queue.control(job["id"], "resume")


def test_audit_and_checkpoint_are_one_transaction(work, monkeypatch):
    queue, _, job, _, _ = work
    claim = queue.claim()
    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")
    monkeypatch.setattr(queue.store, "append_audit_event", fail_audit)
    with pytest.raises(RuntimeError):
        queue.checkpoint(claim, {"ok": True})
    result = queue.get(job["id"])
    assert result["results"] == []
    assert result["completed_steps"] == 0
    assert result["status"] == "running"


@pytest.mark.parametrize("extra", [{"command": "echo ignored"}, {"root": "/"}, {"kind": "shell"}, {"request_id": "bad"}])
def test_api_rejects_arbitrary_execution_fields(work, extra):
    queue, _, job, _, _ = work
    body = {"task_id": job["task_id"], "request_id": str(uuid.uuid4()), **extra}
    with pytest.raises(ValueError):
        work_request(queue.store, method="POST", path="/api/work/jobs", body=body)


def test_http_queue_is_authenticated_and_can_control_real_work(tmp_path, monkeypatch):
    with run_test_http_server(tmp_path, monkeypatch) as (base, store):
        task_id = store.create_task(title="HTTP local check", goal="Read-only syntax")
        body = {"task_id": task_id, "request_id": str(uuid.uuid4())}
        status, _ = http_json(base, "/api/work/jobs", method="POST", body=body, host="leon.example.ts.net")
        assert status == 401
        status, created = http_json(base, "/api/work/jobs", method="POST", body=body)
        assert status == 200
        job_id = created["job"]["id"]
        status, paused = http_json(base, "/api/work/control", method="POST", body={"id": job_id, "action": "pause"})
        assert status == 200 and paused["job"]["status"] == "paused"
        status, resumed = http_json(base, "/api/work/control", method="POST", body={"id": job_id, "action": "resume"})
        assert status == 200 and resumed["job"]["status"] == "queued"
        finish(LocalWorker(WorkQueue(store)))
        status, result = http_json(base, f"/api/work/jobs?id={job_id}")
        assert status == 200 and result["job"]["status"] == "succeeded"
        assert result["job"]["results"][1]["files_checked"] >= 24
        assert store.validate_audit_hash_chain()


def test_actual_process_death_recovers_without_repeating_committed_step(work):
    queue, worker, job, _, now = work
    worker.run_once()
    code = (
        "import os,sys; from pathlib import Path; "
        "from leon_control_plane.store import ControlPlaneStore; "
        "from leon_control_plane.work_queue import WorkQueue; "
        "q=WorkQueue(ControlPlaneStore(Path(sys.argv[1]),Path(sys.argv[2])),clock=lambda:1000.0); "
        "assert q.claim()['step']==1; os._exit(77)"
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    crashed = subprocess.run([sys.executable, "-c", code, str(queue.store.db_path), str(queue.store.seed_path)], env=env, capture_output=True, timeout=10)
    assert crashed.returncode == 77, crashed.stderr.decode()
    assert queue.get(job["id"])["status"] == "running"
    now[0] += LEASE_SECONDS
    finish(LocalWorker(WorkQueue(queue.store, clock=lambda: now[0]), root=worker.root))
    result = queue.get(job["id"])
    assert result["status"] == "succeeded"
    assert len(result["results"]) == 3
    assert queue.store.validate_audit_hash_chain()


def test_tasks_api_exposes_only_eligible_task_identity(work):
    queue, _, job, _, _ = work
    queue.store.create_task(title="Approval pending", goal="Not executable", approval_required=True)
    data = work_request(queue.store, method="GET", path="/api/work/tasks")
    assert any(item["id"] == job["task_id"] for item in data["tasks"])
    assert all(set(item) == {"id", "title"} for item in data["tasks"])
    assert all(item["title"] != "Approval pending" for item in data["tasks"])
    with pytest.raises(ValueError):
        work_request(queue.store, method="POST", path="/api/work/tasks", body={})


def test_blocked_parent_is_paused_before_claim(work):
    queue, _, job, _, _ = work
    for status in ("planned", "active"):
        queue.store.update_task_status(job["task_id"], status)
    queue.store.update_task_status(job["task_id"], "blocked", blocked_reason="Wait")
    assert queue.claim() is None
    assert queue.get(job["id"])["status"] == "paused"


def test_unexpected_private_error_is_not_saved_or_reported(work, monkeypatch):
    queue, worker, job, _, _ = work
    def broken_read(*args):
        raise OSError("private unpublishable detail")
    monkeypatch.setattr("leon_control_plane.local_worker.execute_step", broken_read)
    worker.run_once()
    result = queue.get(job["id"])
    assert result["status"] == "failed"
    assert result["results"][-1]["reason"] == "execution_error"
    assert "unpublishable" not in json.dumps(result)


def test_invalid_worker_result_cannot_advance_checkpoint(work):
    queue, _, job, _, _ = work
    claim = queue.claim()
    for result in ({"ok": "true"}, {"ok": True, "output": "x" * 262145}):
        with pytest.raises(ValueError):
            queue.checkpoint(claim, result)
    assert queue.get(job["id"])["completed_steps"] == 0


def test_full_queue_rejects_new_jobs_but_preserves_idempotent_retry(work):
    queue, _, job, _, _ = work
    request_id = str(uuid.uuid4())
    existing = queue.enqueue(task_id=job["task_id"], request_id=request_id)
    for _ in range(98):
        queue.enqueue(task_id=job["task_id"], request_id=str(uuid.uuid4()))
    with pytest.raises(ValueError, match="full"):
        queue.enqueue(task_id=job["task_id"], request_id=str(uuid.uuid4()))
    assert queue.enqueue(task_id=job["task_id"], request_id=request_id)["id"] == existing["id"]
