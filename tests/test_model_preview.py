from contextlib import closing
import json
import uuid
from urllib.request import Request, urlopen

import pytest

from leon_control_plane.work_api import work_request
from leon_control_plane.work_queue import WorkQueue
from test_control_plane import make_store, run_test_http_server, http_json


def test_preview_validates_costs_without_creating_jobs_or_approvals(tmp_path):
    store = make_store(tmp_path)
    queue = WorkQueue(store)
    with closing(store.connect()) as conn:
        before = list(conn.iterdump())
    result = work_request(store, method="POST", path="/api/work/model/preview",
                          body={"prompt": "Hallo", "max_output_tokens": 512, "max_cost_microusd": 10000})
    assert result["preview"]["reserved_microusd"] <= 10000
    assert result["preview"]["execution_allowed"] is False
    assert result["preview"]["provider_calls_made"] is False
    assert queue.list() == []
    with closing(store.connect()) as conn:
        assert list(conn.iterdump()) == before


@pytest.mark.parametrize("extra", [{"max_cost_microusd": 1}, {"prompt": "🌍" * 1025}, {"tools": []}, {"approve_external_text": True}])
def test_invalid_preview_fails_without_queue(tmp_path, extra):
    store = make_store(tmp_path)
    with pytest.raises(ValueError):
        work_request(store, method="POST", path="/api/work/model/preview",
                     body={"prompt": "Hallo", "max_output_tokens": 512, "max_cost_microusd": 10000, **extra})
    assert WorkQueue(store).list() == []


def test_recover_job_by_request_uuid_without_new_execution(tmp_path):
    store = make_store(tmp_path)
    queue = WorkQueue(store)
    task = store.create_task(title="Recovery", goal="Read only", risk_level="low")
    request_id = str(uuid.uuid4())
    assert queue.find_request(request_id) is None
    job = queue.enqueue(task_id=task, request_id=request_id)
    restored = work_request(store, method="GET", path=f"/api/work/jobs?request_id={request_id}")["job"]
    assert restored["id"] == job["id"] and restored["request_id"] == request_id
    assert restored["status"] == "queued"
    for query in ["request_id=bad", "request_id=", f"id=a&request_id={request_id}", f"request_id={request_id}&request_id={request_id}"]:
        with pytest.raises(ValueError):
            work_request(store, method="GET", path=f"/api/work/jobs?{query}")


def test_preview_http_requires_bearer_even_for_localhost(tmp_path, monkeypatch):
    token = "fixture-" + uuid.uuid4().hex
    with run_test_http_server(tmp_path, monkeypatch, env_text=f"LEON_DASHBOARD_TOKEN={token}\n") as (base, store):
        body = {"prompt": "Hallo", "max_output_tokens": 512, "max_cost_microusd": 10000}
        assert http_json(base, "/api/work/model/preview", method="POST", body=body)[0] == 401
        request = Request(base + "/api/work/model/preview", data=json.dumps(body).encode(),
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urlopen(request, timeout=5) as result:
            assert json.load(result)["preview"]["execution_allowed"] is False
        assert WorkQueue(store).list() == []
