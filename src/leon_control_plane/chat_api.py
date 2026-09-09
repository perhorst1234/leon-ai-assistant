"""Durable, approval-bound chat over the existing bounded model work queue.

Chat messages are application data, separate from the dashboard's task and job
lists.  A model prompt is built only by the preview endpoint and its digest is
required when a turn is submitted, so prior turns are never silently shared.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import time
import uuid

from leon_control_plane.model_work import preview as model_preview
from leon_control_plane.openai_text import MAX_INPUT_BYTES
from leon_control_plane.secret_scanner import assert_no_secrets
from leon_control_plane.work_queue import MODEL_KIND, WorkQueue


MAX_MESSAGE_BYTES = 2048
MAX_TITLE_BYTES = 120
MAX_PAGE_SIZE = 100
PROMPT_PREFIX = (
    "You are Leon. Answer the final user message using only the displayed conversation. "
    "Do not claim that you performed actions, accessed systems, or observed facts that are not in it.\n\n"
    "Conversation:\n"
)
PROMPT_SUFFIX = "\n\nReply to the final user message."


def _uuid(value, label="request_id"):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f"{label} must be a UUID") from None


def _text(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > maximum:
        raise ValueError(f"{label} must be non-empty and at most {maximum} UTF-8 bytes")
    assert_no_secrets(label, value)
    return value.strip()


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _approval_digest(prompt, max_output_tokens, max_cost_microusd):
    """Bind the approved prompt and both execution limits together."""
    approval = json.dumps(
        {"prompt": prompt, "max_output_tokens": max_output_tokens, "max_cost_microusd": max_cost_microusd},
        sort_keys=True,
        separators=(",", ":"),
    )
    return _digest(approval)


class ChatService:
    def __init__(self, store, *, clock=time.time):
        self.store, self.clock = store, clock
        store.initialize()
        with closing(store.connect()) as conn, conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS chat_conversations (
                    id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL REFERENCES tasks(id), title TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES chat_conversations(id),
                    request_id TEXT UNIQUE, role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                    content TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
                    job_id TEXT UNIQUE, prompt TEXT, prompt_sha256 TEXT, conversation_revision INTEGER,
                    request_content TEXT, max_output_tokens INTEGER, max_cost_microusd INTEGER,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS chat_conversations_page ON chat_conversations(created_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS chat_messages_conversation ON chat_messages(conversation_id, created_at, id);
            """)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(chat_messages)")}
            if "request_content" not in columns:
                conn.execute("ALTER TABLE chat_messages ADD COLUMN request_content TEXT")

    @staticmethod
    def _conversation(conn, conversation_id):
        row = conn.execute("SELECT * FROM chat_conversations WHERE id=?", (conversation_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown chat conversation")
        return row

    @staticmethod
    def _message(conn, message_id):
        row = conn.execute("SELECT * FROM chat_messages WHERE id=?", (message_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown chat message")
        return row

    @staticmethod
    def _message_view(row):
        return {key: row[key] for key in ("id", "request_id", "role", "content", "status", "job_id", "created_at", "updated_at")}

    @staticmethod
    def _conversation_view(row):
        return {key: row[key] for key in ("id", "title", "revision", "created_at", "updated_at")}

    def create_conversation(self, details):
        if not isinstance(details, dict) or set(details) - {"request_id", "title"} or "request_id" not in details:
            raise ValueError("Expected a request id and optional title")
        request_id = _uuid(details["request_id"])
        title = details.get("title", "Chat")
        if not isinstance(title, str) or len(title.encode("utf-8")) > MAX_TITLE_BYTES:
            raise ValueError("title must be at most 120 UTF-8 bytes")
        title = title.strip() or "Chat"
        assert_no_secrets("Chat title", title)
        with closing(self.store.connect()) as conn, conn:
            existing = conn.execute("SELECT * FROM chat_conversations WHERE request_id=?", (request_id,)).fetchone()
            if existing is not None:
                if existing["title"] != title:
                    raise ValueError("request_id is already bound to a different conversation")
                return self._conversation_view(existing)
        # A single generic low-risk task owns all turns in this conversation.  User
        # text deliberately stays only in chat_messages and the approved wire prompt.
        task_id = self.store.create_task(title="Chat conversation", goal="Bounded approved text conversation", risk_level="low")
        now, conversation_id = self.clock(), f"chat-{uuid.uuid4().hex}"
        with closing(self.store.connect()) as conn, conn:
            existing = conn.execute("SELECT * FROM chat_conversations WHERE request_id=?", (request_id,)).fetchone()
            if existing is not None:
                if existing["title"] != title:
                    raise ValueError("request_id is already bound to a different conversation")
                return self._conversation_view(existing)
            conn.execute("INSERT INTO chat_conversations VALUES(?,?,?,?,?,?,?)",
                         (conversation_id, request_id, task_id, title, 0, now, now))
            return self._conversation_view(self._conversation(conn, conversation_id))

    def _included(self, conn, conversation_id, content):
        rows = list(conn.execute("""SELECT role,content FROM chat_messages
            WHERE conversation_id=? AND (role='user' OR status='complete') ORDER BY created_at,id""", (conversation_id,)))
        turns = [{"role": row["role"], "content": row["content"]} for row in rows]
        turns.append({"role": "user", "content": content})
        included = []
        # Keep whole most-recent turns. This is also the exact list presented for approval.
        for turn in reversed(turns):
            candidate = [turn] + included
            rendered = "".join(f"[{item['role']}] {item['content']}\n" for item in candidate)
            if len((PROMPT_PREFIX + rendered + PROMPT_SUFFIX).encode("utf-8")) > MAX_INPUT_BYTES:
                break
            included = candidate
        if not included or included[-1] != turns[-1]:
            raise ValueError("Current message leaves no room for an approved prompt")
        prompt = PROMPT_PREFIX + "".join(f"[{item['role']}] {item['content']}\n" for item in included) + PROMPT_SUFFIX
        return included, prompt

    def _refresh_conversation(self, conn, conversation_id):
        for row in conn.execute("SELECT * FROM chat_messages WHERE conversation_id=? AND role='assistant' ORDER BY created_at,id", (conversation_id,)):
            self._refresh(conn, row)

    def _recover_orphans(self, conversation_id):
        with closing(self.store.connect()) as conn:
            rows = list(conn.execute("SELECT * FROM chat_messages WHERE conversation_id=? AND role='assistant' AND job_id IS NULL", (conversation_id,)))
        for row in rows:
            self._recover(row)

    def preview(self, details):
        if not isinstance(details, dict) or set(details) != {"conversation_id", "content", "max_output_tokens", "max_cost_microusd"}:
            raise ValueError("Expected conversation, shared text and explicit limits")
        content = _text(details["content"], "Chat message", MAX_MESSAGE_BYTES)
        self._recover_orphans(details["conversation_id"])
        with closing(self.store.connect()) as conn, conn:
            conversation = self._conversation(conn, details["conversation_id"])
            self._refresh_conversation(conn, conversation["id"])
            included, prompt = self._included(conn, conversation["id"], content)
        quote = model_preview({"prompt": prompt, "max_output_tokens": details["max_output_tokens"], "max_cost_microusd": details["max_cost_microusd"]})
        return quote | {"conversation_id": conversation["id"], "conversation_revision": conversation["revision"],
                        "included_messages": included, "prompt": prompt,
                        # Keep the established field name for the web client, but
                        # bind the approval to the exact limits as well as text.
                        "prompt_sha256": _approval_digest(prompt, details["max_output_tokens"], quote["max_cost_microusd"])}

    def _recover(self, row):
        """Attach an already created queue record after a process crash."""
        if row["job_id"]:
            return row
        with closing(self.store.connect()) as conn:
            conversation = self._conversation(conn, row["conversation_id"])
        # enqueue is deliberately called even when a UUID already exists: its
        # idempotency path verifies task, kind, prompt and limits before returning it.
        job = WorkQueue(self.store).enqueue(task_id=conversation["task_id"], request_id=row["request_id"], kind=MODEL_KIND,
            model_request={"prompt": row["prompt"], "max_output_tokens": row["max_output_tokens"],
                           "max_cost_microusd": row["max_cost_microusd"], "approve_external_text": True})
        now = self.clock()
        with closing(self.store.connect()) as conn, conn:
            conn.execute("UPDATE chat_messages SET job_id=?,status='pending',updated_at=? WHERE id=?", (job["id"], now, row["id"]))
            return self._message(conn, row["id"])

    def submit(self, conversation_id, details):
        required = {"request_id", "content", "max_output_tokens", "max_cost_microusd", "approve_external_text", "preview_sha256"}
        if not isinstance(details, dict) or set(details) != required or details["approve_external_text"] is not True:
            raise ValueError("Expected an approved preview, shared text and explicit limits")
        request_id = _uuid(details["request_id"])
        content = _text(details["content"], "Chat message", MAX_MESSAGE_BYTES)
        if not isinstance(details["preview_sha256"], str) or len(details["preview_sha256"]) != 64:
            raise ValueError("Expected the preview digest")
        assistant = None
        with closing(self.store.connect()) as conn:
            existing = conn.execute("SELECT * FROM chat_messages WHERE request_id=?", (request_id,)).fetchone()
            if existing is not None:
                if (existing["conversation_id"] != conversation_id or existing["request_content"] != content or existing["prompt_sha256"] != details["preview_sha256"]
                        or existing["max_output_tokens"] != details["max_output_tokens"]
                        or existing["max_cost_microusd"] != details["max_cost_microusd"]):
                    raise ValueError("request_id is already bound to a different approved chat turn")
                assistant = existing
        if assistant is not None:
            assistant = self._recover(assistant)
            return self._message_view(assistant), WorkQueue(self.store).get(assistant["job_id"])
        # Reconcile completed turns outside the write transaction.  _recover can
        # enqueue and therefore must never open a nested writer under this lock.
        self.get_conversation(conversation_id)
        with closing(self.store.connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                existing = conn.execute("SELECT * FROM chat_messages WHERE request_id=?", (request_id,)).fetchone()
                if existing is not None:
                    if (existing["conversation_id"] != conversation_id or existing["request_content"] != content or existing["prompt_sha256"] != details["preview_sha256"]
                            or existing["max_output_tokens"] != details["max_output_tokens"] or existing["max_cost_microusd"] != details["max_cost_microusd"]):
                        raise ValueError("request_id is already bound to a different approved chat turn")
                    assistant = existing
                else:
                    conversation = self._conversation(conn, conversation_id)
                    included, prompt = self._included(conn, conversation_id, content)
                    model_preview({"prompt": prompt, "max_output_tokens": details["max_output_tokens"], "max_cost_microusd": details["max_cost_microusd"]})
                    if details["preview_sha256"] != _approval_digest(
                        prompt, details["max_output_tokens"], details["max_cost_microusd"]
                    ):
                        raise ValueError("Chat preview is stale or does not match the exact approved context")
                    previous_at = conn.execute("SELECT COALESCE(MAX(created_at),0) FROM chat_messages WHERE conversation_id=?", (conversation_id,)).fetchone()[0]
                    now = max(self.clock(), previous_at + 0.000001)
                    user_id, assistant_id = f"chatmsg-{uuid.uuid4().hex}", f"chatmsg-{uuid.uuid4().hex}"
                    assistant_at = now + 0.000001
                    next_revision = conversation["revision"] + 1
                    conn.execute("INSERT INTO chat_messages(id,conversation_id,role,content,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                                 (user_id, conversation_id, "user", content, "complete", now, now))
                    conn.execute("""INSERT INTO chat_messages(id,conversation_id,request_id,role,status,prompt,prompt_sha256,conversation_revision,
                        request_content,max_output_tokens,max_cost_microusd,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (assistant_id, conversation_id, request_id, "assistant", "pending", prompt,
                         _approval_digest(prompt, details["max_output_tokens"], details["max_cost_microusd"]), next_revision, content,
                         details["max_output_tokens"], details["max_cost_microusd"], assistant_at, assistant_at))
                    conn.execute("UPDATE chat_conversations SET revision=?,updated_at=? WHERE id=?", (next_revision, now, conversation_id))
                    assistant = self._message(conn, assistant_id)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        assistant = self._recover(assistant)
        return self._message_view(assistant), WorkQueue(self.store).get(assistant["job_id"])

    def _refresh(self, conn, row):
        if row["role"] != "assistant":
            return row
        if not row["job_id"]:
            return row
        job = WorkQueue(self.store).get(row["job_id"])
        result = job["results"][-1] if job["results"] else None
        status, content = "pending", row["content"]
        if job["status"] == "succeeded" and isinstance(result, dict) and result.get("ok") is True and isinstance(result.get("text"), str):
            status, content = "complete", result["text"]
        elif job.get("model_state") == "unknown" or (isinstance(result, dict) and result.get("reason") == "provider_outcome_unknown"):
            status, content = "unknown", ""
        elif job["status"] in {"failed", "cancelled"}:
            status, content = "error", ""
        if status != row["status"] or content != row["content"]:
            conn.execute("UPDATE chat_messages SET status=?,content=?,updated_at=? WHERE id=?", (status, content, self.clock(), row["id"]))
            row = self._message(conn, row["id"])
        return row

    def get_conversation(self, conversation_id):
        self._recover_orphans(conversation_id)
        with closing(self.store.connect()) as conn, conn:
            conversation = self._conversation(conn, conversation_id)
            rows = [self._refresh(conn, row) for row in conn.execute(
                "SELECT * FROM chat_messages WHERE conversation_id=? ORDER BY created_at,id", (conversation_id,))]
            return self._conversation_view(conversation) | {"messages": [self._message_view(row) for row in rows]}

    def list_conversations(self, *, limit=50, before=None):
        if type(limit) is not int or not 1 <= limit <= MAX_PAGE_SIZE:
            raise ValueError("limit must be between 1 and 100")
        with closing(self.store.connect()) as conn:
            condition, args = "", []
            if before is not None:
                cursor = self._conversation(conn, before)
                condition, args = "WHERE (created_at,id)<(?,?)", [cursor["created_at"], cursor["id"]]
            rows = list(conn.execute(f"SELECT * FROM chat_conversations {condition} ORDER BY created_at DESC,id DESC LIMIT ?", (*args, limit + 1)))
            next_before = rows[limit - 1]["id"] if len(rows) > limit else None
            return {"conversations": [self._conversation_view(row) for row in rows[:limit]], "next_before": next_before}


def chat_request(store, *, method, path, body=None):
    from urllib.parse import parse_qs, urlsplit
    url = urlsplit(path)
    if url.path != "/api/chat" and not url.path.startswith("/api/chat/"):
        return None
    service = ChatService(store)
    if method == "POST" and url.path == "/api/chat/conversations":
        return {"ok": True, "conversation": service.create_conversation(body)}
    if method == "POST" and url.path == "/api/chat/preview" and not url.query:
        return {"ok": True, "preview": service.preview(body)}
    if method == "GET" and url.path == "/api/chat/conversations":
        query = parse_qs(url.query, keep_blank_values=True)
        if set(query) - {"limit", "before"} or any(len(value) != 1 or not value[0] for value in query.values()):
            raise ValueError("Expected optional limit and before cursor")
        limit = int(query.get("limit", ["50"])[0])
        return {"ok": True, **service.list_conversations(limit=limit, before=query.get("before", [None])[0])}
    prefix = "/api/chat/conversations/"
    if url.path.startswith(prefix):
        tail = url.path[len(prefix):]
        if method == "GET" and tail and not url.query:
            return {"ok": True, "conversation": service.get_conversation(tail)}
        if method == "POST" and tail.endswith("/messages") and not url.query:
            message, job = service.submit(tail[:-len("/messages")], body)
            return {"ok": True, "message": message, "job": job}
    raise ValueError("Unsupported chat request")
