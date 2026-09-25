"""Local M40/Ollama routing and bounded loopback transport."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import uuid

from leon_control_plane.local_model import LocalModelConfig
from leon_control_plane.agent_assignment import build_agent_assignment_proposal
from leon_control_plane.agent_runtime import build_local_agent_prompt
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


def test_busy_local_preview_uses_openai_unless_provider_is_forced_local(monkeypatch):
    monkeypatch.setenv("LEON_LOCAL_MODEL_ENABLED", "1")
    cloud = preview({"prompt": "Een gewone vraag.", "max_output_tokens": 64, "max_cost_microusd": 5000}, local_busy=True)
    private = preview({"prompt": "Een sensueel onderwerp.", "max_output_tokens": 64, "max_cost_microusd": 1, "provider": "ollama"}, local_busy=True)
    assert cloud["provider"] == "openai"
    assert private["provider"] == "ollama"


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


def test_local_agent_assignment_runs_durably_and_waits_for_review(tmp_path, monkeypatch):
    monkeypatch.setenv("LEON_LOCAL_MODEL_ENABLED", "1")
    monkeypatch.setenv("LEON_LOCAL_MODEL_HOST", "127.0.0.1")
    monkeypatch.setenv("LEON_LOCAL_MODEL_PORT", "11434")
    monkeypatch.setenv("LEON_LOCAL_MODEL_NAME", "qwen2.5-coder:14b")
    queue = WorkQueue(make_store(tmp_path))
    task_id = queue.store.create_task(
        title="Maak lokaal implementatieplan",
        goal="Lever een kort en controleerbaar plan.",
        risk_level="medium",
    )
    proposal = build_agent_assignment_proposal(
        task=queue.store.get_task(task_id),
        runner_kind="local_ollama",
        agent_role="Leon Local Agent",
    )
    assert proposal["execution_allowed"] is True
    assert proposal["model_route"]["provider"] == "ollama"
    assert proposal["shell_commands_allowed"] is False
    assert proposal["file_writes_allowed"] is False
    proposal_id = queue.store.create_agent_assignment_proposal(proposal)
    applied = queue.store.apply_agent_assignment_proposal(
        proposal_id,
        review_note="Text-only lokale uitvoering is akkoord.",
        work_queue=queue,
    )
    running = next(item for item in queue.store.get_state()["agent_runs"] if item["id"] == applied["agent_run_id"])
    assert applied["status"] == "queued"
    assert running["status"] == "running"

    def transport(payload, config):
        assert "Voer geen tools" in payload["input"]
        return {
            "model": config.model,
            "response": "Resultaat\nPlan klaar.\n\nBewijs\nTaakcontext gebruikt.\n\nOpen vragen\nGeen.",
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 80,
            "eval_count": 24,
        }

    worker = LocalWorker(queue, model_executor=ModelExecutor(
        queue,
        config=OpenAIConfig(),
        local_config=_config(),
        local_transport=transport,
    ))
    assert worker.run_once()
    job = queue.get(applied["work_job_id"])
    completed = next(item for item in queue.store.get_state()["agent_runs"] if item["id"] == applied["agent_run_id"])
    assert job["status"] == "succeeded"
    assert job["provider"] == "ollama"
    assert job["accounted_microusd"] == 0
    assert completed["status"] == "waiting_for_review"
    assert completed["review_status"] == "pending"
    assert completed["result_summary"].startswith("Resultaat")
    assert any(item["type"] == "local_model" for item in completed["evidence"])
    assert queue.store.validate_audit_hash_chain()


def test_local_agent_prompt_is_bounded_and_redacted():
    raw_secret = "sk-" + ("z" * 32)
    prompt = build_local_agent_prompt({
        "title": "Veilige analyse",
        "goal": f"Vat dit samen zonder {raw_secret}",
        "acceptance_criteria": "Geen tools.",
        "agent_role": "Leon Local Agent",
        "task_type": "documentation",
        "source_refs": [],
        "allowed_actions": ["produce_reviewable_result"],
        "forbidden_actions": ["read_raw_secrets", "execute_shell_commands", "modify_files"],
    })
    assert raw_secret not in prompt
    assert "[REDACTED_SECRET]" in prompt
    assert len(prompt.encode("utf-8")) <= 4096


def test_local_model_extends_fenced_lease_for_cold_start(tmp_path, monkeypatch):
    monkeypatch.setenv("LEON_LOCAL_MODEL_ENABLED", "1")
    now = [1_000.0]
    queue = WorkQueue(make_store(tmp_path), clock=lambda: now[0])
    task = queue.store.create_task(title="Cold start", goal="Wait safely", risk_level="low")
    job = queue.enqueue(
        task_id=task,
        request_id=str(uuid.uuid4()),
        kind=MODEL_KIND,
        model_request={
            "prompt": "Geef een kort antwoord.",
            "max_output_tokens": 64,
            "max_cost_microusd": 1,
            "approve_external_text": True,
        },
    )

    def slow_transport(_payload, config):
        now[0] += 31
        return {
            "model": config.model,
            "response": "Klaar.",
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 5,
            "eval_count": 2,
        }

    worker = LocalWorker(queue, model_executor=ModelExecutor(
        queue,
        config=OpenAIConfig(),
        local_config=_config(),
        local_transport=slow_transport,
    ))
    assert worker.run_once()
    assert queue.get(job["id"])["status"] == "succeeded"


def test_worker_recovers_assignment_applied_before_queue_insert(tmp_path, monkeypatch):
    monkeypatch.setenv("LEON_LOCAL_MODEL_ENABLED", "1")
    store = make_store(tmp_path)
    task_id = store.create_task(title="Recover local run", goal="Resume after crash", risk_level="medium")
    proposal = build_agent_assignment_proposal(
        task=store.get_task(task_id),
        runner_kind="local_ollama",
        agent_role="Leon Local Agent",
    )
    proposal_id = store.create_agent_assignment_proposal(proposal)

    class LostAfterApplyQueue:
        def enqueue_agent_run(self, **_kwargs):
            return {"id": "job-lost-before-persist"}

    applied = store.apply_agent_assignment_proposal(
        proposal_id,
        review_note="Simulate crash boundary.",
        work_queue=LostAfterApplyQueue(),
    )
    queue = WorkQueue(store)
    recovered = [job for job in queue.list() if job["task_id"] == task_id]
    assert len(recovered) == 1
    assert recovered[0]["status"] == "queued"
    assert recovered[0]["provider"] == "ollama"
    run = next(item for item in store.get_state()["agent_runs"] if item["id"] == applied["agent_run_id"])
    assert run["status"] == "running"


def test_high_risk_local_agent_assignment_cannot_be_applied(tmp_path, monkeypatch):
    monkeypatch.setenv("LEON_LOCAL_MODEL_ENABLED", "1")
    store = make_store(tmp_path)
    task_id = store.create_task(title="High risk local run", goal="Do not execute", risk_level="high")
    proposal = build_agent_assignment_proposal(
        task=store.get_task(task_id),
        runner_kind="local_ollama",
        agent_role="Leon Local Agent",
    )
    assert proposal["execution_allowed"] is False
    proposal_id = store.create_agent_assignment_proposal(proposal)
    try:
        store.apply_agent_assignment_proposal(
            proposal_id,
            review_note="Must remain blocked.",
            work_queue=WorkQueue(store),
        )
    except ValueError as exc:
        assert "does not allow" in str(exc)
    else:
        raise AssertionError("high-risk local agent assignment was applied")
    assert store.get_state()["agent_runs"] == []
