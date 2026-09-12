"""Safe one-shot local overnight source scan."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from leon_control_plane.night_queue import DEFAULT_ALLOWED_RISK_CLASSES, NightQueueScheduler
from leon_control_plane.store import ControlPlaneStore

def main(argv=None):
    parser = argparse.ArgumentParser(description="Run one bounded local Leon overnight source scan")
    parser.add_argument("--db", type=Path, default=Path("state/control-plane.sqlite"))
    parser.add_argument("--seed", type=Path, default=Path("state/control-plane.seed.json"))
    parser.add_argument("--budget-mode", choices=("economy", "balanced", "quality"), default="economy")
    args = parser.parse_args(argv)
    result = NightQueueScheduler(ControlPlaneStore(args.db, args.seed)).run_once(
        allowed_risk_classes=list(DEFAULT_ALLOWED_RISK_CLASSES),
        requested_actions=["index_new_sources"],
        budget_mode=args.budget_mode,
        local_gpu_ready=False,
    )
    # Journald output is deliberately scalar and bounded; the full brief remains
    # available through the local store/API and must never be dumped to logs.
    summary = {
        "run_id": str(result.get("id") or result.get("run_id") or "")[:120],
        "status": str(result.get("status") or "")[:80],
        "action_count": len(result.get("action_results") or []) if isinstance(result.get("action_results"), list) else 0,
        "failure_count": len(result.get("failures") or []) if isinstance(result.get("failures"), list) else 0,
        "source_count": len(result.get("sources") or []) if isinstance(result.get("sources"), list) else 0,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
