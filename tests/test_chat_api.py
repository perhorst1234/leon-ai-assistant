from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import patch
import json
import uuid
from urllib.request import Request, urlopen

import pytest

from leon_control_plane.chat_api import ChatService, chat_request
from leon_control_plane.local_worker import LocalWorker
from leon_control_plane.model_work import ModelExecutor
from leon_control_plane.openai_text import MODEL, OpenAIConfig
from leon_control_plane.work_queue import KIND, WorkQueue
from test_control_plane import make_store, run_test_http_server, http_json


def request_id():
    return str(uuid.uuid4())


def quote(service, conversation_id, content="Hallo"):
    return service.preview({"conversation_id": conversation_id, "content": content,
                            "max_output_tokens": 128, "max_cost_microusd": 2000})


def submit(service, conversation_id, content="Hallo", request=None, preview=None):
    preview = preview or quote(service, conversation_id, content)
    return service.submit(conversation_id, {"request_id": request or request_id(), "content": content,
        "max_output_tokens": 128, "max_cost_microusd": 2000, "approve_external_text": True,
        "preview_sha256": preview["prompt_sha256"]})


def test_chat_preview_shows_exact_bounded_context_and_submit_is_idempotent(tmp_path):
    service = ChatService(make_store(tmp_path))
    conversation = service.create_conversation({"request_id": request_id(), "title": "Gaia"})
    preview = quote(service, conversation["id"], "Hoe gaat het?")
    assert preview["included_messages"] == [{"role": "user", "content": "Hoe gaat het?"}]
    assert preview["prompt_sha256"]
    rid = request_id()
    message, job = submit(service, conversation["id"], "Hoe gaat het?", rid, preview)
    again, same_job = submit(service, conversation["id"], "Hoe gaat het?", rid, preview)
    assert message["status"] == again["status"] == "pending"
    assert job["id"] == same_job["id"]
    loaded = service.get_conversation(conversation["id"])
    assert [(item["role"], item["status"]) for item in loaded["messages"]] == [("user", "complete"), ("assistant", "pending")]


def test_stale_preview_cannot_approve_changed_conversation(tmp_path):
    service = ChatService(make_store(tmp_path))
    conversation = service.create_conversation({"request_id": request_id()})
    stale = quote(service, conversation["id"], "Eerste")
    submit(service, conversation["id"], "Andere")
    with pytest.raises(ValueError, match="stale"):
        submit(service, conversation["id"], "Eerste", preview=stale)


def test_replayed_request_id_binds_the_original_user_message(tmp_path):
    service = ChatService(make_store(tmp_path))
    conversation = service.create_conversation({"request_id": request_id()})
    preview = quote(service, conversation["id"], "Ongewijzigd")
    rid = request_id()
    submit(service, conversation["id"], "Ongewijzigd", rid, preview)
    with pytest.raises(ValueError, match="different approved"):
        submit(service, conversation["id"], "Gewijzigd", rid, preview)


def test_approval_digest_binds_execution_limits(tmp_path):
    service = ChatService(make_store(tmp_path))
    conversation = service.create_conversation({"request_id": request_id()})
    preview = quote(service, conversation["id"], "Zelfde tekst")
    with pytest.raises(ValueError, match="stale"):
        service.submit(conversation["id"], {
            "request_id": request_id(), "content": "Zelfde tekst",
            "max_output_tokens": 256, "max_cost_microusd": 4000,
            "approve_external_text": True, "preview_sha256": preview["prompt_sha256"],
        })


def test_concurrent_approved_previews_allow_only_one_current_context(tmp_path):
    service = ChatService(make_store(tmp_path))
    conversation = service.create_conversation({"request_id": request_id()})
    first, second = quote(service, conversation["id"], "Eerste"), quote(service, conversation["id"], "Tweede")
    def send(content, preview):
        try:
            submit(service, conversation["id"], content, preview=preview)
            return "accepted"
        except ValueError as error:
            return str(error)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda args: send(*args), [("Eerste", first), ("Tweede", second)]))
    assert outcomes.count("accepted") == 1
    assert any("stale" in outcome for outcome in outcomes)
    assert len(service.get_conversation(conversation["id"])["messages"]) == 2


def test_orphan_recovery_refuses_an_unrelated_queue_request_id(tmp_path):
    store, service = make_store(tmp_path), None
    service = ChatService(store)
    conversation = service.create_conversation({"request_id": request_id()})
    preview = quote(service, conversation["id"], "Herstel")
    rid = request_id()
    with closing(store.connect()) as conn, conn:
        task_id = conn.execute("SELECT task_id FROM chat_conversations WHERE id=?", (conversation["id"],)).fetchone()[0]
        conn.execute("""INSERT INTO chat_messages(id,conversation_id,request_id,role,status,prompt,prompt_sha256,conversation_revision,
            request_content,max_output_tokens,max_cost_microusd,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("chatmsg-orphan", conversation["id"], rid, "assistant", "pending", preview["prompt"], preview["prompt_sha256"], 1,
             "Herstel", 128, 2000, 1.0, 1.0))
    WorkQueue(store).enqueue(task_id=task_id, request_id=rid, kind=KIND)
    with pytest.raises(ValueError, match="different work"):
        service.get_conversation(conversation["id"])


def test_completed_queue_result_is_persisted_as_assistant_text(tmp_path):
    store, service = make_store(tmp_path), None
    service = ChatService(store)
    conversation = service.create_conversation({"request_id": request_id()})
    _, job = submit(service, conversation["id"], "Zeg hallo")
    queue = WorkQueue(store)
    config = OpenAIConfig(True, "synthetic-" + uuid.uuid4().hex, 10_000, 50_000)
    response = {"model": MODEL, "status": "completed", "error": None, "usage": {"input_tokens": 20, "output_tokens": 2},
                "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Hallo."}]}]}
    with patch("leon_control_plane.openai_text.date") as clock:
        clock.today.return_value = date(2026, 9, 7)
        LocalWorker(queue, model_executor=ModelExecutor(queue, config=config, transport=lambda *_: response)).run_once()
    loaded = service.get_conversation(conversation["id"])
    assistant = loaded["messages"][-1]
    assert assistant["job_id"] == job["id"]
    assert assistant["status"] == "complete" and assistant["content"] == "Hallo."
    with closing(store.connect()) as conn:
        assert conn.execute("SELECT content,status FROM chat_messages WHERE id=?", (assistant["id"],)).fetchone()[0] == "Hallo."


def test_conversation_listing_is_independent_of_hundred_job_window(tmp_path):
    service = ChatService(make_store(tmp_path))
    conversations = [service.create_conversation({"request_id": request_id(), "title": f"Chat {index}"}) for index in range(101)]
    first = service.list_conversations(limit=100)
    assert len(first["conversations"]) == 100 and first["next_before"]
    second = service.list_conversations(limit=100, before=first["next_before"])
    assert [item["id"] for item in second["conversations"]] == [conversations[0]["id"]]
    assert service.get_conversation(conversations[0]["id"])["id"] == conversations[0]["id"]


def test_chat_router_rejects_unsupported_path_without_creating_tables(tmp_path):
    store = make_store(tmp_path)
    assert chat_request(store, method="GET", path="/api/state") is None
    with closing(store.connect()) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='chat_messages'").fetchone() is None


def test_http_chat_requires_explicit_bearer_for_read_and_write(tmp_path, monkeypatch):
    token = "fixture-" + uuid.uuid4().hex
    with run_test_http_server(tmp_path, monkeypatch, env_text=f"LEON_DASHBOARD_TOKEN={token}\n") as (base, _):
        assert http_json(base, "/api/chat/conversations", method="POST", body={"request_id": request_id()})[0] == 401
        request = Request(base + "/api/chat/conversations", data=json.dumps({"request_id": request_id()}).encode(),
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            conversation = json.load(response)["conversation"]
        assert http_json(base, f"/api/chat/conversations/{conversation['id']}")[0] == 401
        request = Request(base + f"/api/chat/conversations/{conversation['id']}", headers={"Authorization": f"Bearer {token}"})
        with urlopen(request, timeout=5) as response:
            assert json.load(response)["conversation"]["id"] == conversation["id"]
