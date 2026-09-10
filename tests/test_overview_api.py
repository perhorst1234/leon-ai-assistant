from leon_control_plane.overview_api import memory_snapshot, overview
from leon_control_plane.work_queue import WorkQueue
from test_control_plane import make_store
import uuid
import json
import urllib.error
import urllib.request
from test_control_plane import run_test_http_server


def test_memory_snapshot_is_fresh_and_excludes_deleted_items(tmp_path):
    store = make_store(tmp_path)
    item_id = store.create_memory_item({"content": "keep", "source": "test"})
    deleted_id = store.create_memory_item({"content": "remove", "source": "test"})
    store.delete_memory_item(deleted_id, reason="test")
    snapshot = memory_snapshot(store)
    assert snapshot["generated_at"]
    assert [item["id"] for item in snapshot["items"]] == [item_id]


def test_overview_reports_durable_jobs_and_memory_counts(tmp_path):
    store = make_store(tmp_path)
    task_id = store.create_task(title="Overview task", goal="Test durable overview")
    WorkQueue(store).enqueue(task_id=task_id, request_id=str(uuid.uuid4()), kind="python_syntax_check")
    store.create_memory_item({"content": "candidate", "source": "test"})
    result = overview(store)
    assert result["work"]["job_count"] == 1
    assert sum(result["work"]["status_counts"].values()) == 1
    assert result["memory"]["candidate_count"] >= 1
    assert "approvals" not in result


def test_overview_counts_all_jobs_beyond_recent_window(tmp_path):
    store = make_store(tmp_path)
    queue = WorkQueue(store)
    for index in range(101):
        task_id = store.create_task(title=f"Queue task {index}", goal="Test queue count")
        job = queue.enqueue(task_id=task_id, request_id=str(uuid.uuid4()), kind="python_syntax_check")
        with store.connect() as conn:
            conn.execute("UPDATE work_jobs SET status='done' WHERE id=?", (job["id"],))
    result = overview(store)
    assert result["work"]["job_count"] == 101
    assert sum(result["work"]["status_counts"].values()) == 101
    assert len(result["work"]["recent_jobs"]) == 10


def test_overview_endpoints_require_auth_and_return_fresh_nostore_data(tmp_path, monkeypatch):
    with run_test_http_server(tmp_path, monkeypatch) as (base_url, store):
        for path in ("/api/memory", "/api/overview"):
            request = urllib.request.Request(base_url + path, headers={"Host": "leon.example.ts.net"})
            try:
                urllib.request.urlopen(request, timeout=5)
            except urllib.error.HTTPError as error:
                assert error.code == 401
            else:
                raise AssertionError("endpoint accepted unauthenticated request")
            request = urllib.request.Request(base_url + path, headers={"Host": "leon.example.ts.net", "Authorization": "Bearer test-dashboard-token"})
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode())
                assert response.status == 200
                assert response.headers["cache-control"] == "no-store"
                assert payload["generated_at"]
