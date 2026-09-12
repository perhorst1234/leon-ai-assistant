from leon_control_plane.overview_api import build_autonomy_projection
from leon_control_plane import autonomy_cli
from leon_control_plane import night_queue
from test_control_plane import make_store


def test_autonomy_projection_is_bounded_and_uses_latest_run():
    result = build_autonomy_projection({"night_queue_runs": [
        {"id": "old", "status": "succeeded", "ended_at": "2026-09-10T22:00:00Z"},
        {"id": "new", "status": "completed_with_attention", "ended_at": "2026-09-11T22:00:00Z",
         "action_results": [{"secret": "do-not-expose", "huge": "x" * 100000}],
         "morning_brief": {"status": "completed_with_attention", "sections": [],
                           "partial_failure_disclosure": {"status": "completed_with_attention", "secret": "do-not-expose", "nested": {"huge": "x" * 100000}}}},
    ]}, limit=1)["autonomy"]
    assert result["latest_run_id"] == "new"
    assert result["status"] == "completed_with_attention"
    assert len(result["latest_runs"]) == 1
    assert "action_results" not in result["latest_runs"][0]
    assert "do-not-expose" not in str(result)
    assert "nested" not in str(result)
    assert result["morning_brief"]["status"] == "completed_with_attention"
    assert result["bounded"] is True


def test_autonomy_projection_empty_state_is_idle():
    result = build_autonomy_projection({})["autonomy"]
    assert result["status"] == "idle"
    assert result["latest_run_id"] == ""
    assert result["morning_brief"] is None


def test_cli_restricts_scheduled_run_to_source_scan(monkeypatch, tmp_path):
    seen = {}
    class FakeScheduler:
        def __init__(self, store): pass
        def run_once(self, **kwargs):
            seen.update(kwargs)
            return {"status": "succeeded"}
    monkeypatch.setattr(autonomy_cli, "ControlPlaneStore", lambda db, seed: object())
    monkeypatch.setattr(autonomy_cli, "NightQueueScheduler", FakeScheduler)
    assert autonomy_cli.main(["--db", str(tmp_path / "db"), "--seed", str(tmp_path / "seed")]) == 0
    assert seen["requested_actions"] == ["index_new_sources"]
    assert seen["allowed_risk_classes"] == ["R1", "R2"]


def test_overview_truncates_brief_section_labels():
    value = "x" * 2000
    result = build_autonomy_projection({"night_queue_runs": [{
        "id": "run", "status": "succeeded", "ended_at": "2026-09-11T22:00:00Z",
        "morning_brief": {"status": "succeeded", "sections": [{
            "id": value, "title": value, "summary": value, "items": [],
        }]},
    }]})["autonomy"]["morning_brief"]["sections"][0]
    assert len(result["id"]) == 120
    assert len(result["title"]) == 240
    assert len(result["summary"]) == 500


def test_overview_bounds_object_shaped_brief_section_items():
    result = build_autonomy_projection({"night_queue_runs": [{
        "id": "run", "status": "succeeded", "ended_at": "2026-09-11T22:00:00Z",
        "morning_brief": {"sections": [{
            "id": "costs_and_models", "title": "Costs", "summary": "Bounded",
            "items": {"cost_estimate": {"secret": "drop", "huge": "x" * 10000}},
        }]},
    }]})["autonomy"]["morning_brief"]["sections"][0]
    assert result["items"] == [{}]
    assert "drop" not in str(result)


def test_brief_failure_closes_started_run_with_valid_audit(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    reason = "brief failure " + "secret-like detail " * 200

    def fail_brief(**kwargs):
        raise RuntimeError(reason)

    monkeypatch.setattr(night_queue, "build_morning_brief", fail_brief)
    result = night_queue.NightQueueScheduler(store).run_once(requested_actions=["index_new_sources"])
    run = store.get_night_queue_run(result["run_id"])
    assert run["status"] == "failed"
    assert run["ended_at"]
    assert run["morning_brief"]["sections"] == []
    assert run["morning_brief"]["completed_improvements"] == []
    assert run["failures"][-1]["action_id"] == "night_queue_finalization"
    assert len(run["failures"][-1]["reason"]) <= 500
    assert store.validate_audit_hash_chain()


def test_cli_prints_only_compact_scalar_summary(monkeypatch, tmp_path, capsys):
    class FakeScheduler:
        def __init__(self, store):
            pass

        def run_once(self, **kwargs):
            return {"id": "run", "status": "failed", "failures": [{"reason": "DO_NOT_PRINT"}],
                    "action_results": [{"secret": "DO_NOT_PRINT"}], "sources": []}

    monkeypatch.setattr(autonomy_cli, "ControlPlaneStore", lambda db, seed: object())
    monkeypatch.setattr(autonomy_cli, "NightQueueScheduler", FakeScheduler)
    assert autonomy_cli.main(["--db", str(tmp_path / "db"), "--seed", str(tmp_path / "seed")]) == 0
    output = capsys.readouterr().out
    assert "DO_NOT_PRINT" not in output
    assert '"run_id": "run"' in output
