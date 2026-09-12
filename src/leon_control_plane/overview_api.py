"""Small read-only boundary for Today/Memory UI snapshots."""
from datetime import UTC, datetime
import json
from contextlib import closing
from leon_control_plane.work_queue import WorkQueue
from leon_control_plane.morning_brief import build_morning_brief_from_run
from leon_control_plane.secret_scanner import redact_value



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
            "memory": {"item_count": sum(memory_counts.values()), "active_count": memory_counts.get("active", 0), "candidate_count": memory_counts.get("candidate", 0)},
            "autonomy": build_autonomy_projection(store.get_state())["autonomy"]}


def _autonomy_latest(items, limit):
    runs = [dict(item) for item in (items or []) if isinstance(item, dict)]
    runs.sort(key=lambda item: str(item.get("ended_at") or item.get("started_at") or ""), reverse=True)
    return runs[:limit]


def _autonomy_run_summary(run):
    """Expose only scalar run metadata and bounded aggregate counts."""
    cost = run.get("cost_estimate") if isinstance(run.get("cost_estimate"), dict) else {}
    return redact_value({
        "id": str(run.get("id") or run.get("run_id") or ""),
        "status": str(run.get("status") or ""),
        "started_at": str(run.get("started_at") or ""),
        "ended_at": str(run.get("ended_at") or ""),
        "action_count": len(run.get("action_results") or []) if isinstance(run.get("action_results"), list) else 0,
        "failure_count": len(run.get("failures") or []) if isinstance(run.get("failures"), list) else 0,
        "proposal_count": len(run.get("proposals") or []) if isinstance(run.get("proposals"), list) else 0,
        "source_count": len(run.get("sources") or []) if isinstance(run.get("sources"), list) else 0,
        "change_count": len(run.get("changes") or []) if isinstance(run.get("changes"), list) else 0,
        "cost_estimate": {key: cost.get(key) for key in ("currency", "estimated_min", "estimated_max", "provider_calls_made") if key in cost},
    })


def _brief_item(item):
    if isinstance(item, dict):
        return {key: str(item[key])[:500] for key in ("id", "title", "summary", "status", "action_id") if key in item and not isinstance(item[key], (dict, list))}
    return str(item)[:500]


def _brief_section(section, limit):
    """Return a bounded section projection; labels are untrusted persisted data."""
    raw_items = section.get("items")
    if isinstance(raw_items, list):
        selected_items = raw_items[:limit]
    elif raw_items is None:
        selected_items = []
    else:
        selected_items = [raw_items]
    return {
        "id": str(section.get("id") or "")[:120],
        "title": str(section.get("title") or "")[:240],
        "summary": str(section.get("summary") or "")[:500],
        "items": [_brief_item(item) for item in selected_items],
    }


def _failure_disclosure(value):
    if not isinstance(value, dict):
        return None
    return {
        "visible_to_user": bool(value.get("visible_to_user")),
        "has_partial_failure": bool(value.get("has_partial_failure")),
        "status": str(value.get("status") or "")[:80],
        "failure_count": int(value.get("failure_count") or 0),
        "recovery_suggestions": [
            {"action": str(item.get("action") or "")[:80], "summary": str(item.get("summary") or "")[:300]}
            for item in (value.get("recovery_suggestions") or [])[:6]
            if isinstance(item, dict)
        ],
    }


def build_autonomy_projection(state, *, limit=5):
    """Bounded latest night queue status and morning brief for the overview UI."""
    limit = max(1, min(int(limit), 20))
    raw_runs = _autonomy_latest(state.get("night_queue_runs"), limit)
    latest = raw_runs[0] if raw_runs else {}
    runs = [_autonomy_run_summary(run) for run in raw_runs]
    raw_brief = latest.get("morning_brief")
    if not isinstance(raw_brief, dict) and latest:
        raw_brief = build_morning_brief_from_run(latest, generated_by="overview")
    brief = None
    if isinstance(raw_brief, dict):
        brief = {key: raw_brief[key] for key in ("run_id", "status", "generated_at", "generated_by") if key in raw_brief}
        if "partial_failure_disclosure" in raw_brief:
            brief["partial_failure_disclosure"] = _failure_disclosure(raw_brief["partial_failure_disclosure"])
        brief["sections"] = [_brief_section(section, limit)
                              for section in (raw_brief.get("sections") or [])[:7] if isinstance(section, dict)]
    return {"autonomy": redact_value({"status": str(latest.get("status") or "idle"), "latest_run_id": str(latest.get("id") or latest.get("run_id") or ""), "latest_runs": runs, "morning_brief": brief, "bounded": True, "limit": limit})}


def overview_request(store, *, method, path):
    if method != "GET":
        return None
    if path == "/api/memory":
        return memory_snapshot(store)
    if path == "/api/overview":
        return overview(store)
    return None
