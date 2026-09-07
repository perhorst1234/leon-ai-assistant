"""Small API boundary: authenticated handler supplies no arbitrary paths or commands."""
from urllib.parse import parse_qs, urlsplit

from leon_control_plane.work_queue import KIND, WorkQueue


def work_request(store, *, method, path, body=None):
    url = urlsplit(path)
    if url.path not in {"/api/work/jobs", "/api/work/control", "/api/work/tasks"}:
        return None
    if method == "GET" and url.path == "/api/work/tasks" and not url.query:
        from contextlib import closing
        store.initialize()
        with closing(store.connect()) as conn:
            tasks = [dict(row) for row in conn.execute(
                "SELECT id,title FROM tasks WHERE status IN ('new','planned','active') "
                "AND approval_required=0 ORDER BY created_at DESC LIMIT 100",
            )]
        return {"ok": True, "tasks": tasks}
    if method == "GET" and url.path == "/api/work/jobs":
        query = parse_qs(url.query, keep_blank_values=True)
        if set(query) - {"id"} or ("id" in query and (len(query["id"]) != 1 or not query["id"][0])):
            raise ValueError("Expected only one optional job id")
        queue = WorkQueue(store)
        return {"ok": True, "job": queue.get(query["id"][0])} if "id" in query else {"ok": True, "jobs": queue.list()}
    if method != "POST" or url.query or url.path == "/api/work/tasks":
        raise ValueError("Unsupported work request")
    if not isinstance(body, dict):
        raise ValueError("Expected a JSON object")
    expected = {"task_id", "request_id", "kind"} if url.path == "/api/work/jobs" else {"id", "action"}
    if set(body) - expected or any(not isinstance(value, str) for value in body.values()):
        raise ValueError("Unexpected work fields; paths, commands and provider settings are not accepted")
    queue = WorkQueue(store)
    if url.path == "/api/work/jobs":
        return {"ok": True, "job": queue.enqueue(task_id=body.get("task_id", ""), request_id=body.get("request_id", ""), kind=body.get("kind", KIND))}
    return {"ok": True, "job": queue.control(body.get("id", ""), body.get("action", ""))}
