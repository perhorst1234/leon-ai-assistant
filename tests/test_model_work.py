"""Offline provider integration: real queue, SQLite/audit and worker, fake wire only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
import json
import os
import subprocess
import sys
import uuid
from unittest.mock import patch
from urllib.request import Request, urlopen
from datetime import date

import pytest

from leon_control_plane.local_worker import LocalWorker
from leon_control_plane.model_work import ModelExecutor
from leon_control_plane.openai_text import (
    MODEL, OpenAIConfig, cost_microusd, parse_response, request_payload, reservation, send_response,
)
from leon_control_plane.work_api import work_request
from leon_control_plane.work_queue import LEASE_SECONDS, MODEL_KIND, WorkQueue
from test_control_plane import make_store, run_test_http_server, http_json


def details(**overrides):
    return {"prompt": "Geef een korte begroeting in het Nederlands.", "max_output_tokens": 128,
            "max_cost_microusd": 2000, "approve_external_text": True, **overrides}


def response(**overrides):
    return {"model": MODEL, "status": "completed", "error": None,
            "usage": {"input_tokens": 22, "output_tokens": 8},
            "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Hallo Per."}]}],
            **overrides}


@pytest.fixture(autouse=True)
def tariff_date():
    # The production tariff expires deliberately; do not make offline tests expire.
    with patch("leon_control_plane.openai_text.date") as clock:
        clock.today.return_value = date(2026, 9, 7)
        yield


@pytest.fixture
def model(tmp_path):
    store = make_store(tmp_path)
    now = [1000.0]
    queue = WorkQueue(store, clock=lambda: now[0])
    task = store.create_task(title="Begroeting", goal="Schrijf een begroeting", risk_level="low")
    config = OpenAIConfig(True, "synthetic-" + uuid.uuid4().hex, 10000, 50000)
    calls = []
    def transport(payload, key):
        calls.append(payload)
        return response()
    executor = ModelExecutor(queue, config=config, transport=transport)
    return queue, task, executor, calls, now


def enqueue(model, **changes):
    queue, task, *_ = model
    return queue.enqueue(task_id=task, request_id=str(uuid.uuid4()), kind=MODEL_KIND, model_request=details(**changes))


def test_real_worker_records_output_cost_and_no_implicit_context(model):
    queue, task, executor, calls, _ = model
    job = enqueue(model)
    assert LocalWorker(queue, model_executor=executor).run_once()
    saved = WorkQueue(queue.store).get(job["id"])
    assert saved["status"] == "succeeded"
    assert saved["total_steps"] == saved["completed_steps"] == 1
    assert saved["results"][0]["text"] == "Hallo Per."
    assert saved["reserved_microusd"] == 0
    assert saved["accounted_microusd"] == cost_microusd(22, 8)
    assert calls[0] == request_payload(details()["prompt"], 128)
    assert queue.store.get_task(task)["status"] == "new"
    assert queue.store.validate_audit_hash_chain()


@pytest.mark.parametrize("change", [
    {"approve_external_text": False}, {"approve_external_text": "true"},
    {"max_cost_microusd": 1}, {"max_cost_microusd": True}, {"max_cost_microusd": -1},
    {"max_output_tokens": 1025}, {"max_output_tokens": True}, {"max_output_tokens": 0},
    {"prompt": ""}, {"prompt": "🌍" * 1025}, {"prompt": "sk-" + uuid.uuid4().hex},
])
def test_approval_input_and_limits_fail_before_enqueue(model, change):
    with pytest.raises(ValueError):
        enqueue(model, **change)
    assert model[0].list() == []


def test_duplicate_id_binds_exact_prompt_and_approved_cost(model):
    queue, task, *_ = model
    rid = str(uuid.uuid4())
    def submit(**changes):
        return queue.enqueue(task_id=task, request_id=rid, kind=MODEL_KIND, model_request=details(**changes))
    assert submit()["id"] == submit()["id"]
    for change in ({"prompt": "Andere tekst"}, {"max_cost_microusd": 3000}, {"max_output_tokens": 256}):
        with pytest.raises(ValueError, match="different approved"):
            submit(**change)


def test_disabled_default_cannot_send_even_with_key(model):
    queue, _, executor, calls, _ = model
    job = enqueue(model)
    executor.config = replace(executor.config, enabled=False)
    LocalWorker(queue, model_executor=executor).run_once()
    assert calls == []
    assert queue.get(job["id"])["provider_calls_made"] is False


def test_config_repr_never_contains_key(model):
    assert model[2].config.api_key not in repr(model[2].config)


def test_route_change_requires_new_review(model):
    with patch("leon_control_plane.openai_text.choose_route", return_value={"provider": "openai", "route": "cheap", "model": "different", "approval_required": False}):
        with pytest.raises(ValueError, match="review"):
            enqueue(model)


def test_parallel_reservations_respect_one_shared_budget(model):
    queue, _, executor, _, _ = model
    for _ in range(2):
        enqueue(model)
    claims = [queue.claim(), queue.claim()]
    hold = reservation(request_payload(details()["prompt"], 128))
    executor.config = replace(executor.config, daily_microusd=hold, total_microusd=hold)
    def begin(claim):
        try:
            executor._begin(claim)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(begin, claims)) == 1
    assert sum(job["reserved_microusd"] for job in queue.list()) == hold


def test_unknown_outcome_survives_restart_and_blocks_new_spend(model):
    queue, _, executor, calls, now = model
    first = enqueue(model)
    original = queue.claim()
    executor._begin(original)  # Simulates process death at the send boundary.
    now[0] += LEASE_SECONDS
    restarted = ModelExecutor(queue, config=executor.config, transport=executor.transport)
    worker = LocalWorker(queue, model_executor=restarted)
    worker.run_once()
    assert queue.get(first["id"])["model_state"] == "unknown"
    assert queue.get(first["id"])["reserved_microusd"] > 0
    now[0] += 86400
    enqueue(model)
    worker.run_once()
    assert calls == []  # Neither the original nor a new job can silently spend.


def test_result_saved_before_checkpoint_is_reused_without_second_call(model):
    queue, _, executor, calls, now = model
    job = enqueue(model)
    claim = queue.claim()
    result = executor.execute(claim)
    now[0] += LEASE_SECONDS
    worker = LocalWorker(queue, model_executor=executor)
    worker.run_once()
    assert len(calls) == 1
    assert queue.get(job["id"])["results"] == [result]


@pytest.mark.parametrize("action", ["pause", "cancel"])
def test_stale_claim_cannot_send_after_control(model, action):
    queue, _, executor, calls, _ = model
    job = enqueue(model)
    claim = queue.claim()
    queue.control(job["id"], action)
    with pytest.raises(ValueError, match="lease"):
        executor.execute(claim)
    assert calls == []


def test_cancel_during_http_still_accounts_spend_but_cannot_complete_job(model):
    queue, _, executor, _, _ = model
    job = enqueue(model)
    def transport(payload, key):
        queue.control(job["id"], "cancel")
        return response()
    executor.transport = transport
    LocalWorker(queue, model_executor=executor).run_once()
    saved = queue.get(job["id"])
    assert saved["status"] == "cancelled"
    assert saved["results"] == []
    assert saved["accounted_microusd"] > 0


def test_timeout_body_and_secret_never_enter_result_or_audit(model):
    queue, _, executor, _, _ = model
    secret = "sk-" + uuid.uuid4().hex
    def broken(payload, key):
        raise TimeoutError(secret)
    executor.transport = broken
    job = enqueue(model)
    LocalWorker(queue, model_executor=executor).run_once()
    saved = queue.get(job["id"])
    assert saved["model_state"] == "unknown"
    assert secret not in json.dumps(saved)
    with closing(queue.store.connect()) as conn:
        assert secret not in "\n".join(conn.iterdump())


@pytest.mark.parametrize("bad", [
    {"usage": None}, {"model": "other"}, {"status": "in_progress"},
    {"usage": {"input_tokens": True, "output_tokens": 3}},
    {"usage": {"input_tokens": 22, "output_tokens": 129}},
    {"usage": {"input_tokens": 99999, "output_tokens": 2}},
    {"output": [{"type": "function_call", "name": "shell"}]},
])
def test_unverified_responses_hold_reservation(model, bad):
    queue, _, executor, _, _ = model
    executor.transport = lambda *_: response(**bad)
    job = enqueue(model)
    LocalWorker(queue, model_executor=executor).run_once()
    assert queue.get(job["id"])["model_state"] == "unknown"
    assert queue.get(job["id"])["reserved_microusd"] > 0


def test_incomplete_is_not_success_but_usage_is_accounted(model):
    queue, _, executor, _, _ = model
    executor.transport = lambda *_: response(status="incomplete")
    job = enqueue(model)
    LocalWorker(queue, model_executor=executor).run_once()
    assert queue.get(job["id"])["status"] == "failed"
    assert queue.get(job["id"])["model_state"] == "settled"
    assert queue.get(job["id"])["accounted_microusd"] > 0


def test_output_secrets_are_redacted():
    secret = "sk-" + uuid.uuid4().hex
    data = response(output=[{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": secret}]}])
    assert secret not in json.dumps(parse_response(data, request_payload("Hallo", 128)))


def test_audit_failure_rolls_back_authorization_before_transport(model):
    queue, _, executor, calls, _ = model
    job = enqueue(model)
    claim = queue.claim()
    with patch.object(queue.store, "append_audit_event", side_effect=RuntimeError("audit unavailable")):
        with pytest.raises(RuntimeError):
            executor.execute(claim)
    assert calls == []
    assert queue.get(job["id"])["model_state"] == "approved"


def test_real_process_crash_after_send_marker_never_retries(model):
    queue, task, executor, calls, now = model
    job = enqueue(model)
    code = (
        "import os; from pathlib import Path; from leon_control_plane.store import ControlPlaneStore; "
        "from leon_control_plane.work_queue import WorkQueue; from leon_control_plane.model_work import ModelExecutor; "
        "from leon_control_plane.openai_text import OpenAIConfig; "
        "import leon_control_plane.openai_text as ot; from datetime import date; "
        "ot.PRICE_VALID_UNTIL=date.max; "
        f"q=WorkQueue(ControlPlaneStore(Path({str(queue.store.db_path)!r}),Path({str(queue.store.seed_path)!r})),clock=lambda:1000); "
        "e=ModelExecutor(q,config=OpenAIConfig(True,'synthetic-only',10000,50000)); "
        "e._begin(q.claim()); os._exit(77)"
    )
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, timeout=10)
    assert result.returncode == 77, result.stderr.decode()
    now[0] += LEASE_SECONDS
    LocalWorker(queue, model_executor=executor).run_once()
    assert calls == []
    assert queue.get(job["id"])["model_state"] == "unknown"


def test_http_endpoint_requires_bearer_even_on_localhost(tmp_path, monkeypatch):
    token = "dashboard-" + uuid.uuid4().hex
    with run_test_http_server(tmp_path, monkeypatch, env_text=f"LEON_DASHBOARD_TOKEN={token}\n") as (base, store):
        task = store.create_task(title="HTTP model", goal="Explicit text", risk_level="low")
        body = {"task_id": task, "request_id": str(uuid.uuid4()), **details()}
        assert http_json(base, "/api/work/model", method="POST", body=body)[0] == 401
        request = Request(base + "/api/work/model", data=json.dumps(body).encode(),
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urlopen(request, timeout=5) as result:
            data = json.load(result)
        assert data["job"]["kind"] == MODEL_KIND
        assert data["job"]["provider_calls_made"] is False
        assert store.validate_audit_hash_chain()


def test_transport_fixed_destination_no_redirect_or_retry():
    class FakeResponse:
        status = 302
        def read(self, limit):
            assert limit == 262145
            return b'{}'
    with patch("leon_control_plane.openai_text.http.client.HTTPSConnection") as constructor:
        conn = constructor.return_value
        conn.getresponse.return_value = FakeResponse()
        with pytest.raises(ValueError):
            send_response(request_payload("Hallo", 128), "synthetic-only")
        constructor.assert_called_once_with("api.openai.com", timeout=20)
        assert conn.request.call_count == 1
        assert conn.request.call_args.args[:2] == ("POST", "/v1/responses")
        conn.close.assert_called_once()
