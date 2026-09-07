"""Loopback wire verification, independent of real credentials/account/network."""
from contextlib import closing
from datetime import date
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from unittest.mock import patch
import uuid

import pytest

from leon_control_plane.local_worker import LocalWorker
from leon_control_plane.model_work import ModelExecutor
from leon_control_plane.openai_text import (
    MODEL, ModelPreflightError, OpenAIConfig, request_payload, reservation,
)
from leon_control_plane.work_queue import MODEL_KIND, WorkQueue
from test_control_plane import make_store


def test_real_http_body_roundtrip_through_worker_and_sqlite(tmp_path):
    observed = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            observed.append((self.path, body, self.headers["Authorization"]))
            answer = json.dumps({"model": MODEL, "status": "completed", "error": None,
                                 "usage": {"input_tokens": 12, "output_tokens": 3},
                                 "output": [{"type": "message", "role": "assistant", "content": [
                                     {"type": "output_text", "text": "Goedemorgen."}]}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(answer)))
            self.end_headers()
            self.wfile.write(answer)
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            queue = WorkQueue(make_store(tmp_path))
            task = queue.store.create_task(title="Wire test", goal="Synthetic only", risk_level="low")
            job = queue.enqueue(task_id=task, request_id=str(uuid.uuid4()), kind=MODEL_KIND,
                                model_request={"prompt": "Begroet mij", "max_output_tokens": 128,
                                               "max_cost_microusd": 2000, "approve_external_text": True})
            def loopback(host, timeout):
                assert host == "api.openai.com" and timeout == 20
                return http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=timeout)
            with patch("leon_control_plane.openai_text.http.client.HTTPSConnection", side_effect=loopback), \
                    patch("leon_control_plane.openai_text.date") as clock:
                clock.today.return_value = date(2026, 9, 7)
                executor = ModelExecutor(queue, config=OpenAIConfig(True, "synthetic-only", 10000, 10000))
                LocalWorker(queue, model_executor=executor).run_once()
            assert observed == [("/v1/responses", request_payload("Begroet mij", 128), "Bearer synthetic-only")]
            saved = queue.get(job["id"])
            assert saved["status"] == "succeeded"
            assert saved["results"][0]["text"] == "Goedemorgen."
            assert queue.store.validate_audit_hash_chain()
        finally:
            server.shutdown()
            thread.join(5)


def test_price_review_deadline_blocks_transport():
    with patch("leon_control_plane.openai_text.date") as clock:
        clock.today.return_value = date(2026, 10, 8)
        with pytest.raises(ModelPreflightError, match="tariff_review"):
            OpenAIConfig(True, "synthetic-only", 10000, 10000).validate()


@pytest.mark.parametrize("daily,total", [(0, 100), (100, 0), (-1, 100), (True, 100)])
def test_invalid_global_budget_is_never_enabled(daily, total):
    with pytest.raises(ModelPreflightError, match="budget_not_configured"):
        OpenAIConfig(True, "synthetic-only", daily, total).validate()


def test_real_environment_config_defaults_off_and_zero(monkeypatch):
    for key in ("LEON_OPENAI_ENABLED", "LEON_OPENAI_DAILY_MICROUSD", "LEON_OPENAI_TOTAL_MICROUSD", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert OpenAIConfig.from_env() == OpenAIConfig()
    monkeypatch.setenv("LEON_OPENAI_ENABLED", "true")
    monkeypatch.setenv("LEON_OPENAI_DAILY_MICROUSD", "NaN")
    assert OpenAIConfig.from_env().enabled is False
    assert OpenAIConfig.from_env().daily_microusd == 0


def test_explicit_env_file_reads_only_selected_settings_and_process_wins(tmp_path, monkeypatch):
    for key in ("LEON_OPENAI_ENABLED", "LEON_OPENAI_DAILY_MICROUSD", "LEON_OPENAI_TOTAL_MICROUSD", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env.local"
    path.write_text("OPENAI_API_KEY='synthetic-only'\nLEON_OPENAI_DAILY_MICROUSD=1000\n"
                    "LEON_OPENAI_TOTAL_MICROUSD=2000\nIGNORED=$(never-run)\n", encoding="utf-8")
    config = OpenAIConfig.from_env(env_file=path)
    assert config.api_key == "synthetic-only"
    assert config.enabled is False  # A key alone never authorizes spending.
    assert config.daily_microusd == 1000 and config.total_microusd == 2000
    monkeypatch.setenv("LEON_OPENAI_DAILY_MICROUSD", "500")
    assert OpenAIConfig.from_env(env_file=path).daily_microusd == 500


def test_missing_or_symlink_env_file_fails_without_private_exception(tmp_path):
    missing = tmp_path / "private-account-name.env"
    with pytest.raises(ModelPreflightError, match="^openai_env_file_unavailable$"):
        OpenAIConfig.from_env(env_file=missing)
    real = tmp_path / "actual.env"
    real.write_text("OPENAI_API_KEY=synthetic-only", encoding="utf-8")
    missing.symlink_to(real)
    with pytest.raises(ModelPreflightError, match="^openai_env_file_unavailable$"):
        OpenAIConfig.from_env(env_file=missing)


def test_budget_day_rollover_does_not_reset_lifetime_budget(tmp_path):
    now = [1000.0]
    queue = WorkQueue(make_store(tmp_path), clock=lambda: now[0])
    task = queue.store.create_task(title="Budget test", goal="Synthetic only", risk_level="low")
    details = {"prompt": "Hallo", "max_output_tokens": 128, "max_cost_microusd": 2000, "approve_external_text": True}
    hold = reservation(request_payload("Hallo", 128))
    first = queue.enqueue(task_id=task, request_id=str(uuid.uuid4()), kind=MODEL_KIND, model_request=details)
    executor = ModelExecutor(queue, config=OpenAIConfig(True, "synthetic-only", hold, hold))
    with patch("leon_control_plane.openai_text.date") as clock:
        clock.today.return_value = date(2026, 9, 7)
        executor._begin(queue.claim())
        # Known full-reservation usage, previous UTC day. Actual transport is not needed.
        with closing(queue.store.connect()) as conn, conn:
            conn.execute("UPDATE model_work SET state='settled',held_microusd=0,charged_microusd=? WHERE job_id=?", (hold, first["id"]))
            conn.execute("UPDATE work_jobs SET status='succeeded' WHERE id=?", (first["id"],))
        now[0] += 86400
        queue.enqueue(task_id=task, request_id=str(uuid.uuid4()), kind=MODEL_KIND, model_request=details)
        with pytest.raises(ModelPreflightError, match="budget_exhausted"):
            executor._begin(queue.claim())
