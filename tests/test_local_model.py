"""Local M40/Ollama routing and bounded loopback transport."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import uuid

from leon_control_plane.local_model import LocalModelConfig
from leon_control_plane.local_worker import LocalWorker
from leon_control_plane.model_work import ModelExecutor, preview
from leon_control_plane.openai_text import OpenAIConfig
from leon_control_plane.work_queue import MODEL_KIND, WorkQueue
from test_control_plane import make_store


def _config(port=11434):
    return LocalModelConfig(True, "127.0.0.1", port, "qwen2.5-coder:14b", 4096, 30)


def test_local_preview_has_no_provider_charge(monkeypatch):
    monkeypatch.setenv("LEON_LOCAL_MODEL_ENABLED", "1")
    quote = preview({"prompt": "Schrijf een begroeting.", "max_output_tokens": 64, "max_cost_microusd": 1})
    assert quote["provider"] == "ollama"
    assert quote["model"] == "qwen2.5-coder:14b"
    assert quote["reserved_microusd"] == 0
    assert quote["provider_calls_made"] is False


def test_local_http_roundtrip_uses_only_loopback_and_zero_cost(tmp_path, monkeypatch):
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            observed.append((self.path, body))
            answer = json.dumps({
                "model": "qwen2.5-coder:14b", "response": "Hallo vanaf de M40.",
                "done": True, "done_reason": "stop", "prompt_eval_count": 12, "eval_count": 7,
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(answer)))
            self.end_headers()
            self.wfile.write(answer)

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = _config(server.server_port)
            monkeypatch.setenv("LEON_LOCAL_MODEL_ENABLED", "1")
            monkeypatch.setenv("LEON_LOCAL_MODEL_PORT", str(server.server_port))
            queue = WorkQueue(make_store(tmp_path))
            task = queue.store.create_task(title="Lokaal", goal="Test M40", risk_level="low")
            job = queue.enqueue(
                task_id=task, request_id=str(uuid.uuid4()), kind=MODEL_KIND,
                model_request={"prompt": "Begroet mij", "max_output_tokens": 64,
                               "max_cost_microusd": 1, "approve_external_text": True},
            )
            executor = ModelExecutor(queue, config=OpenAIConfig(), local_config=config)
            assert LocalWorker(queue, model_executor=executor).run_once()
            saved = queue.get(job["id"])
            assert saved["status"] == "succeeded"
            assert saved["execution_kind"] == "local_gpu_text"
            assert saved["provider"] == "ollama"
            assert saved["accounted_microusd"] == 0
            assert saved["results"][0]["text"] == "Hallo vanaf de M40."
            assert observed[0][0] == "/api/generate"
            assert observed[0][1]["stream"] is False
            assert observed[0][1]["options"]["num_ctx"] == 4096
            assert observed[0][1]["options"]["num_predict"] == 64
        finally:
            server.shutdown()
            thread.join(5)


def test_non_loopback_local_model_is_rejected():
    config = LocalModelConfig(True, "192.0.2.1", 11434, "qwen2.5-coder:14b", 4096, 30)
    try:
        config.validate()
    except ValueError as exc:
        assert str(exc) == "local_model_must_use_loopback"
    else:
        raise AssertionError("non-loopback model endpoint was accepted")


def test_transient_local_failure_is_retried_without_external_cost(tmp_path, monkeypatch):
    monkeypatch.setenv("LEON_LOCAL_MODEL_ENABLED", "1")
    queue = WorkQueue(make_store(tmp_path))
    task = queue.store.create_task(title="Retry", goal="Survive local restart", risk_level="low")
    job = queue.enqueue(
        task_id=task, request_id=str(uuid.uuid4()), kind=MODEL_KIND,
        model_request={"prompt": "Begroet mij", "max_output_tokens": 64,
                       "max_cost_microusd": 1, "approve_external_text": True},
    )
    calls = []

    def transport(_payload, _config):
        calls.append(True)
        if len(calls) == 1:
            raise ConnectionError()
        return {"model": "qwen2.5-coder:14b", "response": "Hallo.", "done": True,
                "done_reason": "stop", "prompt_eval_count": 4, "eval_count": 2}

    worker = LocalWorker(queue, model_executor=ModelExecutor(
        queue, config=OpenAIConfig(), local_config=_config(), local_transport=transport,
    ))
    assert worker.run_once()
    assert queue.get(job["id"])["status"] == "queued"
    assert queue.get(job["id"])["results"] == []
    assert worker.run_once()
    saved = queue.get(job["id"])
    assert saved["status"] == "succeeded"
    assert saved["accounted_microusd"] == 0
    assert len(calls) == 2
