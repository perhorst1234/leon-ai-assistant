"""Real SQLite/worker/API cost recovery; only synthetic transport and credentials."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import patch

import pytest

from leon_control_plane import model_receipts
from leon_control_plane.local_worker import LocalWorker
from leon_control_plane.model_work import ModelExecutor
from leon_control_plane.openai_text import OpenAIConfig
from leon_control_plane.work_api import work_request
from leon_control_plane.work_queue import LEASE_SECONDS
from test_model_work import model, tariff_date, enqueue, response
from test_control_plane import run_test_http_server, http_json


def break_answer(model):
    queue, _, executor, calls, _ = model
    def transport(*_):
        calls.append('one-call')
        return response(output=[{"type": "unsupported-output"}])
    executor.transport = transport
    job = enqueue(model)
    LocalWorker(queue, model_executor=executor).run_once()
    return queue.get(job["id"])


def approve(queue, job_id):
    proposal = model_receipts.preview(queue, job_id)
    return model_receipts.reconcile(queue, job_id, proposal["receipt_sha256"], True)


def test_usage_receipt_recovers_cost_not_answer_or_parent_acceptance(model):
    queue, task, executor, calls, _ = model
    job = break_answer(model)
    assert job["model_state"] == "unknown" and job["status"] == "failed"
    with closing(queue.store.connect()) as conn:
        before = list(conn.iterdump())
    proposal = model_receipts.preview(queue, job["id"])
    assert 0 < proposal["accounted_microusd"] < proposal["reserved_microusd"]
    with closing(queue.store.connect()) as conn:
        assert list(conn.iterdump()) == before  # Preview does not grant anything.
    saved = approve(queue, job["id"])
    assert saved["model_state"] == "reconciled" and saved["reserved_microusd"] == 0
    assert saved["accounted_microusd"] == proposal["accounted_microusd"]
    assert saved["status"] == "failed" and saved["completed_steps"] == 0
    assert saved["results"] == job["results"]
    assert queue.store.get_task(task)["status"] == "new"
    assert calls == ['one-call']
    # New explicitly approved work can use the remaining budget, but the old job
    # was neither requeued nor paid again.
    executor.transport = lambda *_: response()
    next_job = enqueue(model)
    LocalWorker(queue, model_executor=executor).run_once()
    assert queue.get(next_job["id"])["status"] == "succeeded"
    assert queue.store.validate_audit_hash_chain()


@pytest.mark.parametrize('bad', [None, {"usage": None}, {"model": "other"},
    {"usage": {"input_tokens": 99999, "output_tokens": 2}},
    {"usage": {"input_tokens": True, "output_tokens": 2}}, {"status": "in_progress"}])
def test_missing_or_unbounded_evidence_cannot_release_costs(model, bad):
    queue, _, executor, _, _ = model
    def transport(*_):
        if bad is None:
            raise TimeoutError('synthetic failure')
        return response(**bad)
    executor.transport = transport
    job = enqueue(model)
    LocalWorker(queue, model_executor=executor).run_once()
    with pytest.raises(ValueError, match='No recoverable'):
        approve(queue, job["id"])
    assert queue.get(job["id"])["reserved_microusd"] > 0


def test_explicit_exact_approval_and_idempotent_concurrent_reconciliation(model):
    queue = model[0]
    job = break_answer(model)
    proposal = model_receipts.preview(queue, job["id"])
    for approved in [False, 1, 'true', None]:
        with pytest.raises(ValueError):
            model_receipts.reconcile(queue, job["id"], proposal["receipt_sha256"], approved)
    with pytest.raises(ValueError, match='Receipt changed'):
        model_receipts.reconcile(queue, job["id"], '0' * 64, True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: approve(queue, job["id"]), range(2)))
    assert results[0] == results[1]
    with closing(queue.store.connect()) as conn:
        # Audit naming is persisted by the real store, not a stub.
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE event_type='work_model_cost_reconciled'").fetchone()[0] == 1


def test_receipt_and_approval_tampering_fail_closed(model):
    queue = model[0]
    job = break_answer(model)
    with queue._transaction() as conn:
        conn.execute("UPDATE model_usage_receipts SET receipt_json='{}' WHERE job_id=?", (job["id"],))
    with pytest.raises(ValueError, match='integrity'):
        approve(queue, job["id"])
    assert queue.get(job["id"])["reserved_microusd"] > 0


def test_audit_failure_rolls_back_cost_reconciliation(model):
    queue = model[0]
    job = break_answer(model)
    with patch.object(queue.store, 'append_audit_event', side_effect=RuntimeError('unavailable')):
        with pytest.raises(RuntimeError):
            approve(queue, job["id"])
    assert queue.get(job["id"])["model_state"] == 'unknown'
    assert queue.get(job["id"])["reserved_microusd"] == job["reserved_microusd"]


def test_crash_after_usage_receipt_can_recover_without_transport(model):
    queue, _, executor, calls, now = model
    job = enqueue(model)
    claim = queue.claim()
    payload, _ = executor._begin(claim)
    model_receipts.record(queue, job["id"], payload, response())
    # Reconstruct the worker after the durable receipt but before answer parsing.
    now[0] += LEASE_SECONDS
    restarted = ModelExecutor(queue, config=OpenAIConfig(), transport=lambda *_: pytest.fail('No send'))
    LocalWorker(queue, model_executor=restarted).run_once()
    assert approve(queue, job["id"])["model_state"] == 'reconciled'
    assert calls == []


def test_late_worker_cannot_overwrite_approved_cost_recovery(model):
    queue, _, executor, _, now = model
    job = enqueue(model)
    claim = queue.claim()
    def parse_while_other_worker_recovers(*_):
        now[0] += LEASE_SECONDS
        restarted = ModelExecutor(queue, config=OpenAIConfig(), transport=lambda *_: pytest.fail('No retry'))
        LocalWorker(queue, model_executor=restarted).run_once()
        approve(queue, job["id"])
        raise ValueError('late invalid answer')
    with patch('leon_control_plane.model_work.parse_response', side_effect=parse_while_other_worker_recovers):
        result = executor.execute(claim)
    assert result['reason'] == 'answer_unavailable_cost_reconciled'
    assert queue.get(job['id'])['model_state'] == 'reconciled'
    assert not queue.checkpoint(claim, result)


def test_receipt_never_stores_raw_answer_or_secret(model):
    queue, _, executor, _, _ = model
    private = 'PRIVATE-SYNTHETIC-ANSWER'
    executor.transport = lambda *_: response(output=[{"type": "unsupported", "text": private}])
    job = enqueue(model)
    LocalWorker(queue, model_executor=executor).run_once()
    with closing(queue.store.connect()) as conn:
        assert private not in '\n'.join(conn.iterdump())
    assert model_receipts.preview(queue, job['id'])['accounted_microusd'] > 0


def test_api_refuses_arbitrary_amounts_and_malformed_queries(model):
    queue = model[0]
    job = break_answer(model)
    path = '/api/work/model/reconciliation'
    proposal = work_request(queue.store, method='GET', path=path+'?id='+job['id'])['reconciliation']
    for query in ['', '?id=', '?id=a&id=b', '?request_id=a', '?id=a&extra=b']:
        with pytest.raises(ValueError):
            work_request(queue.store, method='GET', path=path+query)
    body = {'id': job['id'], 'receipt_sha256': proposal['receipt_sha256'], 'approve_cost_reconciliation': True}
    with pytest.raises(ValueError):
        work_request(queue.store, method='POST', path=path, body={**body, 'charged_microusd': 0})
    assert work_request(queue.store, method='POST', path=path, body=body)['job']['model_state'] == 'reconciled'


def test_http_reconciliation_requires_bearer_even_locally(tmp_path, monkeypatch):
    token = 'synthetic-reconciliation-token'
    with run_test_http_server(tmp_path, monkeypatch, env_text=f'LEON_DASHBOARD_TOKEN={token}\n') as (base, store):
        body = {'id': 'missing', 'receipt_sha256': '0' * 64, 'approve_cost_reconciliation': True}
        assert http_json(base, '/api/work/model/reconciliation', method='POST', body=body)[0] == 401
