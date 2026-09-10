"""Small read-only boundary for Today/Memory UI snapshots."""
from datetime import UTC, datetime
import json
from contextlib import closing
from leon_control_plane.work_queue import WorkQueue



def _now():
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def memory_snapshot(store):
    store.initialize()
    with closing(store.connect()) as conn:
        items = []
        for row in conn.execute("SELECT id,status,memory_type,content,source,source_task_id,confidence,sensitivity,privacy_level,expires_at,review_note,correction_of,graph_entities_json,provenance_json,conflict_status,conflict_memory_ids_json,conflict_note,audit_event_id,created_at,updated_at,deleted_at FROM memory_items WHERE status NOT IN ('deleted','scrubbed') ORDER BY updated_at DESC,id DESC LIMIT 100"):
            item = dict(row)
            item["graph_entities"] = json.loads(item.pop("graph_entities_json") or "[]")
            item["provenance"] = json.loads(item.pop("provenance_json") or "{}")
            item["conflict_memory_ids"] = json.loads(item.pop("conflict_memory_ids_json") or "[]")
            item["has_conflicts"] = item["conflict_status"] == "conflicted" or bool(item["conflict_memory_ids"])
            items.append(item)
    item_ids = {item.get("id") for item in items}
    with closing(store.connect()) as conn:
        edges = [dict(edge) for edge in conn.execute("SELECT id,source_memory_id,subject,predicate,object,relationship_type,confidence,source,status,audit_event_id,created_at,updated_at,deleted_at FROM memory_graph_edges WHERE status='active' ORDER BY updated_at DESC,id DESC LIMIT 100") if edge["source_memory_id"] in item_ids]
    return {"ok": True, "generated_at": _now(), "items": items, "graph_edges": edges}


def overview(store):
    WorkQueue(store)  # ensure the durable queue schema exists before projection
    store.initialize()
    with closing(store.connect()) as conn:
        job_count = conn.execute("SELECT count(*) FROM work_jobs").fetchone()[0]
        job_counts = {row["status"]: row["count"] for row in conn.execute("SELECT status,count(*) AS count FROM work_jobs GROUP BY status")}
        jobs = [dict(row) for row in conn.execute("SELECT id,request_id,task_id,kind,status,attempts,error,created_at,updated_at FROM work_jobs ORDER BY created_at DESC,id DESC LIMIT 10")]
        memory_counts = {row["status"]: row["count"] for row in conn.execute("SELECT status,count(*) AS count FROM memory_items WHERE status NOT IN ('deleted','scrubbed') GROUP BY status")}
    counts = {}
    return {"ok": True, "generated_at": _now(), "work": {"job_count": job_count, "status_counts": job_counts, "recent_jobs": jobs},
            "memory": {"item_count": sum(memory_counts.values()), "active_count": memory_counts.get("active", 0), "candidate_count": memory_counts.get("candidate", 0)}}


def overview_request(store, *, method, path):
    if method != "GET":
        return None
    if path == "/api/memory":
        return memory_snapshot(store)
    if path == "/api/overview":
        return overview(store)
    return None
