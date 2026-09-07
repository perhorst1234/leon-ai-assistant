"""Durable local checks and separately approved, cost-bounded text model work."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import time

from leon_control_plane.store import ControlPlaneStore
from leon_control_plane.secret_scanner import assert_no_secrets
from leon_control_plane.work_queue import STEPS, JOB_STEPS, MODEL_KIND, WorkQueue
from leon_control_plane.model_work import ModelExecutor
from leon_control_plane.openai_text import ModelPreflightError, OpenAIConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 8 * MAX_FILE_BYTES
MAX_FILES = 256


class CheckError(ValueError):
    """Messages are fixed reason codes, never source text or raw exception strings."""


def source_snapshot(root: Path) -> dict:
    root = root.resolve()
    source = root / "src" / "leon_control_plane"
    if not source.is_dir() or not source.resolve().is_relative_to(root):
        raise CheckError("source_directory_unavailable")
    files = []
    total = 0
    for path in sorted(source.iterdir()):
        if path.suffix != ".py":
            continue
        if len(files) >= MAX_FILES or path.is_symlink() or not path.is_file():
            raise CheckError("source_scope_or_count_limit")
        if not path.resolve().is_relative_to(source.resolve()):
            raise CheckError("source_scope_violation")
        with path.open("rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
        total += len(data)
        if len(data) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise CheckError("source_size_limit")
        files.append({"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    if not files:
        raise CheckError("no_python_sources")
    fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"ok": True, "step": "snapshot", "files": files, "source_sha256": fingerprint}


def execute_step(root: Path, claim: dict) -> dict:
    step = STEPS[claim["step"]]
    snapshot = source_snapshot(root)
    if step == "snapshot":
        return snapshot
    original = claim["results"][0]
    if snapshot["source_sha256"] != original["source_sha256"]:
        raise CheckError("source_changed_since_checkpoint")
    if step == "syntax":
        failures = []
        for item in snapshot["files"]:
            path = root / item["path"]
            # Check the same bytes that are parsed, not an earlier stat/hash.
            with path.open("rb") as handle:
                data = handle.read(MAX_FILE_BYTES + 1)
            if hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise CheckError("source_changed_during_check")
            try:
                ast.parse(data, filename=item["path"])
            except (SyntaxError, ValueError) as exc:
                failures.append({"path": item["path"], "line": getattr(exc, "lineno", None), "reason": "invalid_python_syntax"})
        return {"ok": not failures, "step": step, "files_checked": len(snapshot["files"]),
                "source_sha256": snapshot["source_sha256"], "failures": failures}
    return {"ok": True, "step": step, "source_sha256": snapshot["source_sha256"],
            "files_checked": len(snapshot["files"]), "summary": "Python syntax checked against a stable source snapshot.",
            "scope": "AST parsing only; no tests, code execution, model calls or parent-task acceptance."}


class LocalWorker:
    def __init__(self, queue: WorkQueue, *, root: Path = REPO_ROOT, model_executor=None):
        self.queue, self.root = queue, root.resolve()
        self.model_executor = model_executor if model_executor is not None else ModelExecutor(queue)

    def run_once(self) -> bool:
        claim = self.queue.claim()
        if claim is None:
            return False
        try:
            result = self.model_executor.execute(claim) if claim["kind"] == MODEL_KIND else execute_step(self.root, claim)
            assert_no_secrets("Worker result", result)
        except CheckError as exc:
            result = {"ok": False, "step": JOB_STEPS[claim["kind"]][claim["step"]], "reason": str(exc)}
        except ModelPreflightError as exc:
            result = {"ok": False, "step": "model", "reason": str(exc), "provider_calls_made": False}
        except Exception:
            # Private file contents/paths from unexpected exceptions stay out of receipts.
            result = {"ok": False, "step": JOB_STEPS[claim["kind"]][claim["step"]], "reason": "execution_error"}
        self.queue.checkpoint(claim, result)
        return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run real read-only Leon project checks from the durable queue.")
    parser.add_argument("--once", action="store_true", help="Process at most one checkpoint, then exit")
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "state" / "control-plane.sqlite")
    parser.add_argument("--seed", type=Path, default=REPO_ROOT / "state" / "control-plane.seed.json")
    parser.add_argument("--env-file", type=Path, help="Explicit private env file; only OpenAI settings are read, never executed")
    args = parser.parse_args(argv)
    try:
        model_config = OpenAIConfig.from_env(env_file=args.env_file)
    except ModelPreflightError as exc:
        parser.error(str(exc))
    queue = WorkQueue(ControlPlaneStore(args.db, args.seed))
    worker = LocalWorker(queue, model_executor=ModelExecutor(queue, config=model_config))
    try:
        while True:
            processed = worker.run_once()
            if args.once:
                return 0
            if not processed:
                time.sleep(1)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
