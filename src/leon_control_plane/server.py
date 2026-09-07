from __future__ import annotations

import argparse
import hmac
import html
import json
import os
import re
import secrets
import stat
import sys
import tempfile
from http.cookies import SimpleCookie
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from leon_control_plane.agent_assignment import build_agent_assignment_proposal
from leon_control_plane.agent_runtime import MockAgentRunner
from leon_control_plane.connector_registry import classify_connector_action, normalize_connector_manifest
from leon_control_plane.decision_layer import evaluate_cases, classify_user_request, load_eval_cases
from leon_control_plane.github_catalog import refresh_manifest_github_metadata
from leon_control_plane.local_gpu_validation import normalize_local_gpu_policy
from leon_control_plane.mcp_intake import build_mcp_candidate_intake
from leon_control_plane.night_queue import DEFAULT_ALLOWED_RISK_CLASSES, NightQueueScheduler
from leon_control_plane.orchestrator import build_orchestration_proposal
from leon_control_plane.planner_preview import build_planner_preview
from leon_control_plane.provider_adapter import build_openai_agents_sdk_dry_run_plan
from leon_control_plane.risk_policy import RISK_CLASSES
from leon_control_plane.secret_scanner import SecretScanError, assert_no_secrets, redact_text, redact_value
from leon_control_plane.store import ControlPlaneStore
from leon_control_plane.tool_adoption import build_tool_adoption_shortlist
from leon_control_plane.tool_registry import classify_tool_action, normalize_tool_manifest, score_tool_candidate
from leon_control_plane.tool_review import build_review_packets
from leon_control_plane.work_api import work_request
from leon_control_plane.ui_composition import (
    UI_POLICY_PATH,
    build_canvas_shell,
    compose_ui,
    derive_leon_character,
    load_ui_policy,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = REPO_ROOT / "state"
STATE_PATH = STATE_DIR / "control-plane.json"
SEED_PATH = STATE_DIR / "control-plane.seed.json"
DB_PATH = STATE_DIR / "control-plane.sqlite"
ENV_PATH = REPO_ROOT / ".env.local"
MODEL_POLICY_PATH = REPO_ROOT / "config" / "model-routing.json"
ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,80}$")
SESSION_COOKIE = "leon_session"
STORE = ControlPlaneStore(DB_PATH, SEED_PATH)
RUNNER = MockAgentRunner(STORE)


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_text(path: Path, content: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        if mode is not None:
            tmp_path.chmod(mode)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def load_state() -> dict[str, Any]:
    return STORE.get_state()


def save_state(state: dict[str, Any]) -> None:
    STORE.update_metadata(state.get("metadata", {}))


def parse_env_keys() -> set[str]:
    if not ENV_PATH.exists():
        return set()
    keys: set[str] = set()
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if ENV_KEY_RE.match(key):
            keys.add(key)
    return keys


def _parse_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = bytes(value[1:-1], "utf-8").decode("unicode_escape")
    return value


def parse_selected_env_values(allowed_keys: set[str]) -> dict[str, str]:
    allowed_keys = {key for key in allowed_keys if ENV_KEY_RE.match(key)}
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        with ENV_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line or line.lstrip().startswith("#") or "=" not in line:
                    continue
                key = line.split("=", 1)[0].strip()
                if key in allowed_keys:
                    values[key] = _parse_env_value(line.split("=", 1)[1])
    values.update({key: os.environ[key] for key in allowed_keys if key in os.environ})
    return values


def dashboard_token() -> str:
    return parse_selected_env_values({"LEON_DASHBOARD_TOKEN"}).get("LEON_DASHBOARD_TOKEN", "")


def auth_mode() -> str:
    return parse_selected_env_values({"LEON_DASHBOARD_AUTH_MODE"}).get("LEON_DASHBOARD_AUTH_MODE", "tailnet").lower()


def is_local_host_header(host: str) -> bool:
    host = host.split(":", 1)[0].strip().lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def quote_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
    return f'"{escaped}"'


def upsert_env_value(key: str, value: str) -> None:
    if not ENV_KEY_RE.match(key):
        raise ValueError("Invalid env key")
    if not value:
        raise ValueError("Empty secret values are not accepted")

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    output: list[str] = []
    replaced = False
    for line in lines:
        existing_key = line.split("=", 1)[0].strip() if "=" in line else ""
        if existing_key == key:
            output.append(f"{key}={quote_env_value(value)}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        if output and output[-1].strip():
            output.append("")
        output.append(f"{key}={quote_env_value(value)}")
    atomic_write_text(ENV_PATH, "\n".join(output).rstrip() + "\n", mode=stat.S_IRUSR | stat.S_IWUSR)


def build_technical_inspect_state(safe_state: dict[str, Any]) -> dict[str, Any]:
    """Build a redacted Settings/Inspect summary for internal control state."""

    def status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            status = str(item.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
        return counts

    approvals = [dict(item) for item in safe_state.get("approvals", [])]
    tasks = [dict(item) for item in safe_state.get("tasks", [])]
    audit_events = [dict(item) for item in safe_state.get("audit_events", [])]
    routing_decisions = [dict(item) for item in safe_state.get("routing_decisions", [])]
    routing_eval_cases = [dict(item) for item in safe_state.get("routing_eval_cases", [])]
    routing_eval_runs = [dict(item) for item in safe_state.get("routing_eval_runs", [])]
    required_env = [dict(item) for item in safe_state.get("required_env", [])]
    runtime = dict(safe_state.get("runtime") or {})
    model_policy = dict(safe_state.get("model_policy") or {})
    local_gpu = dict(model_policy.get("local_gpu") or {})
    local_gpu_validation = dict(local_gpu.get("validation") or {})

    latest_route: dict[str, Any] = {}
    if routing_decisions:
        latest = routing_decisions[-1]
        route_detail: dict[str, Any] = {}
        try:
            route_detail = json.loads(latest.get("decision_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            route_detail = {}
        model_route = route_detail.get("model_route") if isinstance(route_detail.get("model_route"), dict) else {}
        latest_route = {
            "id": latest.get("id"),
            "route": latest.get("route"),
            "intent": latest.get("intent"),
            "risk_level": latest.get("risk_level"),
            "value_score": latest.get("value_score"),
            "value_band": route_detail.get("value_band"),
            "value_score_inputs": route_detail.get("value_score_inputs"),
            "retrieved_context": route_detail.get("retrieved_context"),
            "execution_path": route_detail.get("execution_path"),
            "model": latest.get("model") or model_route.get("model"),
            "selected_runtime": model_route.get("selected_runtime"),
            "decision_label": (model_route.get("route_decision") or {}).get("label"),
            "fallback_active": bool((model_route.get("fallback") or {}).get("active")),
        }

    latest_audit = audit_events[-5:]
    return redact_value(
        {
            "surface": "settings/inspect",
            "default_collapsed": True,
            "internal_only": True,
            "auth": {
                "mode": runtime.get("auth_mode"),
                "dashboard_token_configured": bool(runtime.get("dashboard_token_configured")),
                "env_file_exists": bool(runtime.get("env_file_exists")),
            },
            "secrets": {
                "total_required": len(required_env),
                "present": sum(1 for item in required_env if item.get("present")),
                "missing_keys": [item.get("key") for item in required_env if not item.get("present")],
                "items": [
                    {
                        "key": item.get("key"),
                        "present": bool(item.get("present")),
                        "purpose": item.get("purpose"),
                    }
                    for item in required_env
                ],
                "raw_values_exposed": False,
            },
            "audit": {
                "event_count": len(audit_events),
                "hash_chain_valid": bool(runtime.get("audit_hash_chain_valid")),
                "latest_events": [
                    {
                        "sequence": item.get("sequence"),
                        "event_type": item.get("event_type"),
                        "summary": item.get("summary"),
                        "risk_level": item.get("risk_level"),
                        "timestamp": item.get("timestamp"),
                    }
                    for item in latest_audit
                ],
            },
            "approvals": {
                "count": len(approvals),
                "status_counts": status_counts(approvals),
                "pending": [
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "risk_level": item.get("risk_level"),
                    }
                    for item in approvals
                    if item.get("status") == "pending"
                ],
            },
            "task_store": {
                "task_count": len(tasks),
                "status_counts": status_counts(tasks),
                "db_path": runtime.get("db_path"),
                "open_task_ids": [
                    item.get("id")
                    for item in tasks
                    if item.get("status") not in {"done", "rejected"}
                ][:12],
            },
            "routing": {
                "decision_count": len(routing_decisions),
                "latest": latest_route,
                "default_budget_mode": model_policy.get("default_budget_mode"),
                "local_gpu_route_allowed": bool(local_gpu_validation.get("route_allowed")),
                "local_gpu_status": local_gpu_validation.get("status") or local_gpu.get("readiness_status"),
                "eval_case_count": len(routing_eval_cases),
                "active_eval_case_count": sum(1 for item in routing_eval_cases if item.get("status") == "active"),
                "latest_eval_run": routing_eval_runs[0] if routing_eval_runs else {},
            },
        }
    )


def state_for_client() -> dict[str, Any]:
    state = load_state()
    present_keys = parse_env_keys()
    safe_state = json.loads(json.dumps(state))
    for item in safe_state.get("required_env", []):
        item["present"] = item["key"] in present_keys
    for item in safe_state.get("tool_manifests", []):
        try:
            manifest = json.loads(item.get("manifest_json") or "{}")
            item["candidate_score"] = score_tool_candidate(manifest)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            item["candidate_score"] = {
                "score": 0,
                "recommendation": "invalid_manifest",
                "blockers": ["invalid_manifest"],
                "next_actions": ["fix_manifest"],
                "evidence_level": "invalid",
                "reason": str(exc),
            }
    for connector in safe_state.get("connector_manifests", []):
        connector["required_env_status"] = [
            {"key": key, "present": key in present_keys}
            for key in connector.get("required_env_keys", [])
        ]
    safe_state["tool_adoption_shortlist"] = build_tool_adoption_shortlist(safe_state.get("tool_manifests", []))
    safe_state["tool_review_packets"] = build_review_packets(safe_state["tool_adoption_shortlist"])
    safe_state["runtime"] = {
        "repo_root": str(REPO_ROOT),
        "env_path": str(ENV_PATH),
        "db_path": str(DB_PATH),
        "env_file_exists": ENV_PATH.exists(),
        "server_time": now_iso(),
        "audit_hash_chain_valid": STORE.validate_audit_hash_chain(),
        "auth_mode": auth_mode(),
        "dashboard_token_configured": bool(dashboard_token()),
    }
    safe_state["risk_policy"] = {
        "classes": RISK_CLASSES,
        "decisions": ["autonomous", "needs_review", "blocked"],
        "principle": "Every action is classified R1-R5 before execution; R4/R5 actions are approval-first.",
    }
    if MODEL_POLICY_PATH.exists():
        model_policy = read_json(MODEL_POLICY_PATH)
        safe_state["model_policy"] = {
            "default_budget_mode": model_policy.get("default_budget_mode"),
            "cost_policy": model_policy.get("cost_policy", {}),
            "cloud_models": model_policy.get("cloud_models", {}),
            "local_gpu": normalize_local_gpu_policy(model_policy.get("local_gpu", {})),
        }
    if UI_POLICY_PATH.exists():
        ui_policy = load_ui_policy(UI_POLICY_PATH)
        open_tasks = [task for task in safe_state.get("tasks", []) if task.get("status") != "done"]
        pending_approvals = [approval for approval in safe_state.get("approvals", []) if approval.get("status") == "pending"]
        missing_secret = any(not item.get("present") for item in safe_state.get("required_env", []))
        task_status = "waiting_for_approval" if pending_approvals else ("waiting_for_secret" if missing_secret else ("review" if any(task.get("status") == "review" for task in open_tasks) else ""))
        safe_state["ui_composition_policy"] = {
            "version": ui_policy.get("version"),
            "status": ui_policy.get("status"),
            "principle": ui_policy.get("principle"),
            "product_shell": ui_policy.get("product_shell", {}),
            "spaces": ui_policy.get("spaces", {}),
            "component_registry": ui_policy.get("component_registry", {}),
            "assistant_states": ui_policy.get("assistant_states", {}),
            "character_renderer": ui_policy.get("character_renderer", {}),
            "canvas_shell": ui_policy.get("canvas_shell", {}),
            "friction_metrics": ui_policy.get("friction_metrics", {}),
            "safety_invariants": ui_policy.get("safety_invariants", []),
        }
        safe_state["leon_canvas_shell"] = build_canvas_shell(ui_policy)
        ui_preview = compose_ui(
            route="approval_required" if pending_approvals else "task_queue",
            task_status=task_status,
            risk_level="high" if pending_approvals else "low",
            requires_approval=bool(pending_approvals),
            missing_secret=missing_secret,
            compact=False,
            policy=ui_policy,
        )
        safe_state["ui_composition_preview"] = ui_preview
        safe_state["leon_character"] = derive_leon_character(
            safe_state,
            ui_preview=ui_preview,
            policy=ui_policy,
        )
    safe_state["technical_inspect"] = build_technical_inspect_state(safe_state)
    return safe_state


def render_dashboard() -> str:
    return """<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Leon — Personal AI Environment</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #090b10;
      --bg-soft: #0d1118;
      --panel: rgba(255,255,255,0.075);
      --panel-strong: rgba(255,255,255,0.12);
      --line: rgba(255,255,255,0.12);
      --text: #f4f7fb;
      --muted: #a8b3c7;
      --faint: #69758d;
      --accent: #62a8ff;
      --blue: #62a8ff;
      --violet: #a78bfa;
      --amber: #fbbf24;
      --green: #34d399;
      --red: #fb7185;
      --cyan: #22d3ee;
      --motion-standard: 260ms;
      --motion-emphasis: 360ms;
      --motion-ease: cubic-bezier(0.2, 0.8, 0.2, 1);
    }
    * { box-sizing: border-box; }
    html { min-width: 0; }
    body {
      margin: 0;
      min-width: 320px;
      overflow-x: hidden;
      background:
        radial-gradient(circle at 20% 0%, rgba(98,168,255,0.18), transparent 32rem),
        radial-gradient(circle at 80% 10%, rgba(167,139,250,0.14), transparent 28rem),
        radial-gradient(circle at 50% 80%, rgba(34,211,238,0.08), transparent 30rem),
        var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: 0.11;
      background-image:
        linear-gradient(rgba(255,255,255,0.12) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px);
      background-size: 3px 3px;
      mask-image: radial-gradient(circle at center, black, transparent 72%);
    }
    main {
      width: min(1180px, calc(100vw - 32px));
      margin: 32px auto 56px;
    }
    header { display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; margin-bottom: 28px; }
    h1 { font-size: clamp(2.7rem, 4.8vw, 4.8rem); letter-spacing: 0; line-height: 0.94; margin: 0 0 12px; }
    h2 { margin: 0 0 14px; font-size: 1.05rem; letter-spacing: -0.02em; }
    h3 { margin: 0 0 6px; font-size: 0.96rem; }
    h1, h2, h3, p, button, input, select, textarea, .tag { overflow-wrap: anywhere; }
    p { margin: 0; color: var(--muted); }
    button, input, select, textarea {
      font: inherit;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.08);
      color: var(--text);
      padding: 10px 12px;
    }
    button { cursor: pointer; background: rgba(98,168,255,0.16); border-color: rgba(98,168,255,0.36); }
    button:hover { background: rgba(98,168,255,0.25); }
    label { display: grid; gap: 6px; color: var(--muted); font-size: 0.86rem; }
    input, select, textarea { width: 100%; }
    textarea { min-height: 78px; resize: vertical; }
    .grid { display: grid; gap: 16px; }
    .cols { grid-template-columns: repeat(12, minmax(0, 1fr)); }
    .shell {
      min-height: calc(100vh - 88px);
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: 22px;
      padding: 22px;
      margin-bottom: 34px;
      border: 1px solid rgba(255,255,255,0.09);
      border-radius: 34px;
      background:
        linear-gradient(145deg, rgba(255,255,255,0.11), rgba(255,255,255,0.035)),
        radial-gradient(circle at 24% 18%, color-mix(in srgb, var(--accent) 22%, transparent), transparent 28rem),
        rgba(8,11,17,0.74);
      box-shadow: 0 30px 120px rgba(0,0,0,0.42), inset 0 1px 0 rgba(255,255,255,0.12);
      backdrop-filter: blur(22px);
    }
    .shell > *,
    .canvas > *,
    .focus-panel > *,
    .presence-panel > * {
      min-width: 0;
    }
    .shell-top {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-start;
    }
    .eyebrow {
      color: var(--accent);
      font-size: 0.78rem;
      letter-spacing: 0;
      text-transform: uppercase;
      margin-bottom: 10px;
    }
    .shell-subtitle {
      max-width: 650px;
      font-size: 1.03rem;
      color: #c8d1e2;
    }
    .runtime-chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 999px;
      padding: 9px 12px;
      background: rgba(255,255,255,0.055);
      color: var(--muted);
      white-space: nowrap;
      backdrop-filter: blur(14px);
    }
    .canvas {
      display: grid;
      grid-template-columns: minmax(270px, 0.82fr) minmax(320px, 1.18fr);
      gap: 18px;
      align-items: stretch;
      transition: gap var(--motion-emphasis) var(--motion-ease);
    }
    .canvas[data-panel-mode="merged"] {
      gap: 10px;
    }
    .canvas[data-panel-mode="merged"] .presence-panel {
      border-top-right-radius: 18px;
      border-bottom-right-radius: 18px;
      border-color: color-mix(in srgb, var(--accent) 22%, rgba(255,255,255,0.095));
    }
    .canvas[data-panel-mode="merged"] .focus-panel {
      border-top-left-radius: 18px;
      border-bottom-left-radius: 18px;
      border-color: color-mix(in srgb, var(--accent) 22%, rgba(255,255,255,0.095));
    }
    .presence-panel,
    .focus-panel,
    .dock {
      border: 1px solid rgba(255,255,255,0.095);
      background: linear-gradient(180deg, rgba(255,255,255,0.105), rgba(255,255,255,0.045));
      box-shadow: 0 24px 80px rgba(0,0,0,0.26), inset 0 1px 0 rgba(255,255,255,0.12);
      backdrop-filter: blur(22px);
    }
    .presence-panel {
      display: grid;
      place-items: center;
      min-height: 390px;
      border-radius: 28px;
      padding: 24px;
      position: relative;
      overflow: hidden;
      transition: border-radius var(--motion-emphasis) var(--motion-ease), border-color var(--motion-standard) var(--motion-ease), transform var(--motion-emphasis) var(--motion-ease);
    }
    .presence-panel::before {
      content: "";
      position: absolute;
      inset: 18%;
      border-radius: 50%;
      background: radial-gradient(circle, color-mix(in srgb, var(--accent) 34%, transparent), transparent 64%);
      filter: blur(28px);
    }
    .leon-character {
      width: min(172px, 48vw);
      aspect-ratio: 1;
      position: relative;
      display: grid;
      place-items: center;
      opacity: 1;
      transform: translateY(0);
      animation: leon-breathe 5.8s ease-in-out infinite;
    }
    .leon-character[data-state="thinking"] { animation-duration: 4.2s; }
    .leon-character[data-state="acting"] { animation: leon-act 4.8s ease-in-out infinite; }
    .leon-character[data-state="interacting"] { animation: leon-touch 3.8s ease-in-out infinite; }
    .leon-character[data-state="sleeping"] { animation: leon-sleep 8s ease-in-out infinite; opacity: 0.48; }
    .leon-character[data-state="attention"] { animation: leon-attention 3.6s ease-in-out infinite; }
    .leon-character[data-state="error"] { animation: leon-error 3.2s ease-in-out infinite; }
    .leon-orb {
      width: 100%;
      aspect-ratio: 1;
      border-radius: 42% 58% 52% 48%;
      background:
        radial-gradient(circle at 38% 30%, rgba(255,255,255,0.95), transparent 8%),
        radial-gradient(circle at 45% 42%, color-mix(in srgb, var(--accent) 76%, white), color-mix(in srgb, var(--accent) 52%, transparent) 38%, rgba(8,11,17,0.28) 72%);
      box-shadow: 0 0 44px color-mix(in srgb, var(--accent) 42%, transparent), inset 0 0 60px rgba(255,255,255,0.16);
      position: relative;
    }
    .leon-character[data-state="sleeping"] .leon-orb {
      box-shadow: 0 0 18px color-mix(in srgb, var(--accent) 18%, transparent), inset 0 0 36px rgba(255,255,255,0.08);
      filter: saturate(0.7);
    }
    .leon-character[data-state="attention"] .leon-orb,
    .leon-character[data-state="error"] .leon-orb {
      box-shadow: 0 0 54px color-mix(in srgb, var(--accent) 52%, transparent), inset 0 0 58px rgba(255,255,255,0.14);
    }
    .leon-orb::after {
      content: "";
      position: absolute;
      inset: 22%;
      border: 1px solid rgba(255,255,255,0.22);
      border-radius: 45% 55% 50% 50%;
    }
    .leon-face {
      position: absolute;
      inset: 35% 26% auto;
      height: 24%;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 2;
    }
    .leon-eye {
      width: 16%;
      aspect-ratio: 1;
      border-radius: 50%;
      background: rgba(4,8,14,0.72);
      box-shadow: 0 0 12px rgba(255,255,255,0.26);
    }
    .leon-character[data-state="sleeping"] .leon-eye {
      height: 2px;
      aspect-ratio: auto;
      border-radius: 999px;
      background: rgba(4,8,14,0.58);
    }
    .leon-core {
      position: absolute;
      width: 28%;
      aspect-ratio: 1;
      border-radius: 50%;
      bottom: 27%;
      background: color-mix(in srgb, var(--accent) 66%, white);
      box-shadow: 0 0 22px color-mix(in srgb, var(--accent) 58%, transparent);
      z-index: 2;
    }
    .leon-particles {
      position: absolute;
      inset: -13%;
      pointer-events: none;
    }
    .leon-particles span {
      position: absolute;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: color-mix(in srgb, var(--accent) 72%, white);
      box-shadow: 0 0 12px color-mix(in srgb, var(--accent) 56%, transparent);
      opacity: 0;
      animation: leon-particle 4.2s ease-in-out infinite;
    }
    .leon-particles span:nth-child(1) { left: 18%; top: 24%; animation-delay: 0s; }
    .leon-particles span:nth-child(2) { right: 14%; top: 36%; animation-delay: 0.9s; }
    .leon-particles span:nth-child(3) { left: 42%; bottom: 8%; animation-delay: 1.8s; }
    .leon-character[data-state="idle"] .leon-particles span,
    .leon-character[data-state="sleeping"] .leon-particles span,
    .leon-character[data-state="error"] .leon-particles span {
      animation: none;
      opacity: 0;
    }
    .leon-target {
      position: absolute;
      right: -36px;
      top: 44%;
      width: 54px;
      height: 2px;
      border-radius: 999px;
      background: linear-gradient(90deg, color-mix(in srgb, var(--accent) 8%, transparent), var(--accent));
      box-shadow: 0 0 16px color-mix(in srgb, var(--accent) 42%, transparent);
      opacity: 0;
      transform-origin: left center;
    }
    .leon-character[data-state="acting"] .leon-target,
    .leon-character[data-state="interacting"] .leon-target {
      opacity: 0.82;
    }
    .presence-copy {
      position: relative;
      text-align: center;
      display: grid;
      gap: 8px;
      margin-top: 22px;
    }
    .presence-target {
      min-height: 1.2em;
      color: color-mix(in srgb, var(--accent) 72%, white);
    }
    .focus-panel {
      border-radius: 28px;
      padding: 24px;
      display: grid;
      gap: 16px;
      align-content: start;
      transition: border-radius var(--motion-emphasis) var(--motion-ease), border-color var(--motion-standard) var(--motion-ease), transform var(--motion-emphasis) var(--motion-ease);
    }
    .focus-panel > .item-head {
      min-width: 0;
    }
    .focus-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .space-canvas {
      display: grid;
      grid-template-columns: repeat(5, minmax(76px, 1fr));
      grid-auto-rows: minmax(78px, auto);
      gap: 10px;
      padding: 12px;
      border-radius: 24px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.06), rgba(0,0,0,0.11)),
        rgba(0,0,0,0.12);
      border: 1px solid rgba(255,255,255,0.075);
      overflow: hidden;
      transition: background var(--motion-standard) var(--motion-ease), border-color var(--motion-standard) var(--motion-ease);
    }
    .space-canvas.home-focus {
      grid-template-columns: minmax(0, 1fr);
      grid-auto-rows: auto;
      gap: 12px;
      padding: 0;
      background: transparent;
      border-color: transparent;
      overflow: visible;
    }
    .space-canvas.task-detail-space {
      grid-template-columns: minmax(0, 1fr);
      grid-auto-rows: auto;
      max-height: min(54vh, 520px);
      overflow: auto;
    }
    .space-canvas.settings-inspect-space {
      grid-template-columns: minmax(0, 1fr);
      grid-auto-rows: auto;
      max-height: min(54vh, 520px);
      overflow: auto;
    }
    .home-focus-card {
      min-height: 92px;
      border-radius: 20px;
      padding: 16px;
      border: 1px solid rgba(255,255,255,0.075);
      background: rgba(0,0,0,0.15);
    }
    .home-focus-card.primary {
      min-height: 148px;
      display: grid;
      align-content: space-between;
      background:
        linear-gradient(135deg, color-mix(in srgb, var(--accent) 14%, rgba(255,255,255,0.055)), rgba(0,0,0,0.16));
      border-color: color-mix(in srgb, var(--accent) 24%, rgba(255,255,255,0.08));
      box-shadow: 0 18px 56px color-mix(in srgb, var(--accent) 10%, transparent);
    }
    .home-signal-row {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .inspect-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .inspect-card {
      min-height: 112px;
      border-radius: 18px;
      padding: 12px;
      border: 1px solid rgba(255,255,255,0.075);
      background: rgba(0,0,0,0.14);
    }
    .inspect-card.wide {
      grid-column: 1 / -1;
    }
    .inspect-mini-list {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 8px;
    }
    .space-node {
      min-height: 78px;
      display: grid;
      align-content: space-between;
      gap: 8px;
      border-radius: 18px;
      padding: 12px;
      border: 1px solid rgba(255,255,255,0.075);
      background: rgba(255,255,255,0.045);
      color: var(--muted);
      transition: transform var(--motion-standard) var(--motion-ease), background var(--motion-standard) var(--motion-ease), box-shadow var(--motion-standard) var(--motion-ease), border-color var(--motion-standard) var(--motion-ease);
      will-change: transform;
    }
    .space-node.active {
      color: var(--text);
      transform: translateY(-2px);
      border-color: color-mix(in srgb, var(--accent) 48%, transparent);
      background: color-mix(in srgb, var(--accent) 16%, rgba(255,255,255,0.05));
      box-shadow: 0 18px 54px color-mix(in srgb, var(--accent) 16%, transparent);
    }
    .space-node.active.magnetized {
      transform: translate(var(--magnet-x, 0), var(--magnet-y, -2px));
    }
    .space-node .small { color: inherit; }
    .component-strip {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .component-chip {
      max-width: 100%;
      padding: 4px 7px;
      border-radius: 999px;
      background: rgba(0,0,0,0.18);
      border: 1px solid rgba(255,255,255,0.08);
      color: #d8e2f1;
      font-size: 0.72rem;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .focus-tile {
      min-height: 118px;
      min-width: 0;
      border-radius: 18px;
      padding: 14px;
      background: rgba(0,0,0,0.16);
      border: 1px solid rgba(255,255,255,0.075);
      transition: transform var(--motion-standard) var(--motion-ease), background var(--motion-standard) var(--motion-ease), border-color var(--motion-standard) var(--motion-ease), box-shadow var(--motion-standard) var(--motion-ease);
    }
    .focus-tile[data-expand-card] {
      cursor: pointer;
    }
    .focus-tile[data-expand-card]:hover,
    .focus-tile[data-expand-card]:focus-visible {
      outline: 0;
      transform: translateY(-2px);
      border-color: color-mix(in srgb, var(--accent) 34%, transparent);
      background: color-mix(in srgb, var(--accent) 9%, rgba(0,0,0,0.18));
      box-shadow: 0 18px 48px color-mix(in srgb, var(--accent) 11%, transparent);
    }
    .intent-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: center;
      padding: 10px;
      border-radius: 20px;
      background: rgba(0,0,0,0.18);
      border: 1px solid rgba(255,255,255,0.08);
    }
    .intent-row button {
      min-height: 52px;
      white-space: nowrap;
    }
    .intent-row textarea {
      min-height: 52px;
      border: 0;
      background: transparent;
      padding: 8px;
    }
    .dock {
      justify-self: center;
      display: flex;
      align-items: center;
      gap: 7px;
      max-width: 100%;
      overflow-x: auto;
      padding: 7px;
      border-radius: 20px;
      position: sticky;
      bottom: 16px;
      z-index: 5;
      scrollbar-width: none;
    }
    .dock::-webkit-scrollbar { display: none; }
    .dock-section {
      display: flex;
      align-items: center;
      gap: 5px;
      flex: 0 0 auto;
    }
    .dock-divider {
      width: 1px;
      align-self: stretch;
      min-height: 34px;
      background: rgba(255,255,255,0.12);
      margin: 0 2px;
    }
    .dock button {
      border-radius: 14px;
      min-width: 74px;
      min-height: 44px;
      padding: 9px 11px;
      background: rgba(255,255,255,0.055);
      border-color: transparent;
      color: var(--muted);
      transition: transform 160ms ease, background 160ms ease, color 160ms ease, box-shadow 160ms ease;
      white-space: nowrap;
    }
    .dock button:hover,
    .dock button:focus-visible {
      color: var(--text);
      transform: translateY(-1px);
      outline: 0;
      border-color: color-mix(in srgb, var(--accent) 34%, transparent);
      background: color-mix(in srgb, var(--accent) 12%, rgba(255,255,255,0.06));
    }
    .dock button.active {
      color: var(--text);
      background: color-mix(in srgb, var(--accent) 22%, transparent);
      box-shadow: 0 0 28px color-mix(in srgb, var(--accent) 18%, transparent);
    }
    .dock button[data-dock-action] {
      min-width: 64px;
      background: rgba(0,0,0,0.16);
    }
    .operations-label {
      margin: 0 0 16px;
      color: var(--faint);
      font-size: 0.84rem;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .span-4 { grid-column: span 4; }
    .span-5 { grid-column: span 5; }
    .span-7 { grid-column: span 7; }
    .span-8 { grid-column: span 8; }
    .span-12 { grid-column: span 12; }
    .card {
      background: linear-gradient(180deg, var(--panel-strong), var(--panel));
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 20px;
      box-shadow: 0 24px 80px rgba(0,0,0,0.24);
      backdrop-filter: blur(18px);
      transition: transform var(--motion-standard) var(--motion-ease), border-color var(--motion-standard) var(--motion-ease), box-shadow var(--motion-standard) var(--motion-ease);
    }
    .card:focus-within {
      border-color: color-mix(in srgb, var(--accent) 28%, var(--line));
    }
    .status-pill {
      display: inline-flex; align-items: center; gap: 8px;
      padding: 7px 10px; border-radius: 999px;
      border: 1px solid var(--line); color: var(--muted); font-size: 0.82rem;
      background: rgba(255,255,255,0.06);
    }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--blue); }
    .dot.waiting { background: var(--amber); }
    .dot.done { background: var(--green); }
    .dot.risk { background: var(--red); }
    .metric { font-size: 2rem; letter-spacing: -0.04em; color: var(--text); }
    .list { display: grid; gap: 10px; }
    .item { border: 1px solid var(--line); border-radius: 18px; padding: 12px; background: rgba(0,0,0,0.14); }
    .item-head { display: flex; justify-content: space-between; gap: 10px; align-items: start; min-width: 0; }
    .item-head > * { min-width: 0; }
    .muted { color: var(--muted); }
    .small { font-size: 0.84rem; }
    .tag { display: inline-flex; padding: 4px 8px; border: 1px solid var(--line); border-radius: 999px; color: var(--muted); font-size: 0.75rem; }
    .tag.p0 { color: var(--red); border-color: rgba(251,113,133,0.42); }
    .tag.p1 { color: var(--amber); border-color: rgba(251,191,36,0.42); }
    .tag.p2 { color: var(--cyan); border-color: rgba(34,211,238,0.42); }
    .progress { height: 10px; background: rgba(255,255,255,0.08); border-radius: 999px; overflow: hidden; }
    .bar { height: 100%; background: linear-gradient(90deg, var(--blue), var(--violet)); border-radius: 999px; }
    .form-row { display: grid; grid-template-columns: 1fr 1.2fr auto; gap: 10px; align-items: end; }
    .notice { color: var(--amber); }
    .attention { color: var(--amber); }
    .ok { color: var(--green); }
    .danger { color: var(--red); }
    details { border-top: 1px solid var(--line); margin-top: 10px; padding-top: 10px; }
    summary { cursor: pointer; color: var(--muted); font-size: 0.84rem; }
    .operations-shell {
      margin-top: 18px;
      border: 1px solid rgba(255,255,255,0.095);
      border-radius: 26px;
      padding: 14px 18px 18px;
      background: rgba(255,255,255,0.035);
    }
    .operations-shell > summary {
      list-style: none;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      color: var(--text);
      font-size: 0.95rem;
    }
    .operations-shell > summary::-webkit-details-marker { display: none; }
    .operations-shell > summary::after {
      content: "Open";
      display: inline-flex;
      padding: 4px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      font-size: 0.75rem;
    }
    .operations-shell[open] > summary::after { content: "Close"; }
    .inspector-block { border-top: 1px solid var(--line); margin-top: 10px; padding-top: 10px; display: grid; gap: 6px; }
    pre { white-space: pre-wrap; color: var(--muted); margin: 0; }
    .detail-backdrop {
      position: fixed;
      inset: 0;
      z-index: 20;
      display: grid;
      place-items: center;
      padding: 24px;
      background: rgba(3,6,12,0.58);
      backdrop-filter: blur(14px);
    }
    .detail-backdrop[hidden] { display: none; }
    .detail-window {
      width: min(680px, calc(100vw - 36px));
      max-height: min(76vh, 720px);
      overflow: auto;
      border: 1px solid color-mix(in srgb, var(--accent) 28%, rgba(255,255,255,0.12));
      border-radius: 24px;
      padding: 20px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.13), rgba(255,255,255,0.065)),
        rgba(8,11,17,0.94);
      box-shadow: 0 34px 120px rgba(0,0,0,0.52), 0 0 70px color-mix(in srgb, var(--accent) 16%, transparent);
      transform-origin: center;
    }
    .detail-body {
      display: grid;
      gap: 10px;
      margin-top: 12px;
    }
    @keyframes leon-breathe {
      0%, 100% { transform: translateY(0) scale(1); }
      50% { transform: translateY(-5px) scale(1.018); }
    }
    @keyframes leon-act {
      0%, 100% { transform: translate(0, 0) scale(1); }
      50% { transform: translate(9px, -4px) scale(1.018); }
    }
    @keyframes leon-touch {
      0%, 100% { transform: translate(0, 0) rotate(0deg); }
      50% { transform: translate(6px, -3px) rotate(1.4deg); }
    }
    @keyframes leon-sleep {
      0%, 100% { transform: translateY(0) scale(0.985); }
      50% { transform: translateY(-2px) scale(0.99); }
    }
    @keyframes leon-attention {
      0%, 100% { transform: translateY(0) scale(1); filter: brightness(1); }
      50% { transform: translateY(-3px) scale(1.012); filter: brightness(1.12); }
    }
    @keyframes leon-error {
      0%, 100% { transform: translateY(0); filter: brightness(1); }
      50% { transform: translateY(-2px); filter: brightness(1.14); }
    }
    @keyframes leon-particle {
      0%, 100% { opacity: 0; transform: translateY(8px) scale(0.7); }
      45% { opacity: 0.78; transform: translateY(-4px) scale(1); }
    }
    @media (prefers-reduced-motion: reduce) {
      .leon-character,
      .leon-particles span {
        animation: none !important;
      }
      *,
      *::before,
      *::after {
        scroll-behavior: auto !important;
        transition-duration: 1ms !important;
        animation-duration: 1ms !important;
        animation-iteration-count: 1 !important;
      }
    }
    @media (min-width: 1600px) and (min-aspect-ratio: 16/10) {
      main {
        width: min(1680px, calc(100vw - 80px));
        margin-top: 24px;
      }
      .shell {
        min-height: calc(100vh - 72px);
        gap: 20px;
        padding: 24px;
      }
      .canvas {
        grid-template-columns: minmax(360px, 0.78fr) minmax(560px, 1.22fr);
      }
      .presence-panel {
        min-height: clamp(420px, 54vh, 680px);
      }
      .leon-character {
        width: clamp(172px, 12vw, 260px);
      }
      .focus-panel {
        grid-template-rows: auto minmax(0, 1fr) auto auto;
      }
      .space-canvas.home-focus {
        align-content: stretch;
      }
      .home-focus-card.primary {
        min-height: clamp(160px, 20vh, 250px);
      }
      .focus-grid {
        grid-template-columns: repeat(3, minmax(160px, 1fr));
      }
    }
    @media (min-width: 2300px) and (min-aspect-ratio: 16/10) {
      main {
        width: min(1960px, calc(100vw - 120px));
      }
      .shell {
        min-height: calc(100vh - 84px);
        padding: 30px;
      }
      .canvas {
        grid-template-columns: minmax(460px, 0.76fr) minmax(760px, 1.24fr);
        gap: 24px;
      }
      .canvas[data-panel-mode="merged"] {
        gap: 14px;
      }
      .presence-panel,
      .focus-panel {
        padding: 30px;
      }
      .dock {
        max-width: min(100%, 1500px);
      }
    }
    @media (max-width: 1200px) {
      .dock {
        position: static;
      }
    }
    @media (max-width: 900px) {
      header, .form-row { grid-template-columns: 1fr; display: grid; }
      main { width: min(100vw - 20px, 1180px); margin-top: 10px; }
      h1 { font-size: 2.7rem; }
      .shell { min-height: calc(100vh - 20px); padding: 14px; border-radius: 24px; }
      .shell-top, .canvas, .intent-row, .focus-grid { grid-template-columns: 1fr; display: grid; }
      .home-signal-row { grid-template-columns: 1fr; }
      .inspect-grid { grid-template-columns: 1fr; }
      .space-canvas { grid-template-columns: 1fr; }
      .space-node { grid-column: auto !important; grid-row: auto !important; }
      .presence-panel { min-height: 270px; }
      .runtime-chip { white-space: normal; }
      .dock {
        justify-self: stretch;
        width: 100%;
        padding: 6px;
        border-radius: 18px;
      }
      .dock button { min-width: 66px; padding-inline: 10px; }
      .span-4, .span-5, .span-7, .span-8 { grid-column: span 12; }
    }
  </style>
</head>
<body>
  <main>
    <section class="shell" aria-label="Leon environment">
      <div class="shell-top">
        <div>
          <p class="eyebrow">Personal AI Environment</p>
          <h1>Leon</h1>
          <p class="shell-subtitle">Een rustige AI-native ruimte voor kennis, werk, memory en gecontroleerde autonomie.</p>
        </div>
        <div class="runtime-chip"><span class="dot" id="shellDot"></span><span id="shellStatus">laden…</span></div>
      </div>

      <div class="canvas" id="leonCanvas" data-panel-mode="merged">
        <article class="presence-panel" data-motion-key="presence-panel">
          <div>
            <div class="leon-character" id="leonCharacter" data-state="idle" aria-hidden="true">
              <div class="leon-particles"><span></span><span></span><span></span></div>
              <div class="leon-target"></div>
              <div class="leon-orb">
                <div class="leon-face"><span class="leon-eye"></span><span class="leon-eye"></span></div>
                <div class="leon-core"></div>
              </div>
            </div>
            <div class="presence-copy">
              <h2 id="shellPresenceTitle">Leon is beschikbaar</h2>
              <p id="shellPresenceText">Status wordt geladen.</p>
              <p class="small presence-target" id="shellPresenceTarget"></p>
            </div>
          </div>
        </article>

        <article class="focus-panel" data-motion-key="focus-panel">
          <div class="item-head">
            <div>
              <h2 id="shellSpaceTitle">Vandaag in focus</h2>
              <p class="small" id="shellSpacePurpose">Morning brief, actieve workflow en veilige aandachtspunten komen hier samen.</p>
            </div>
            <span class="tag" id="shellMode">preview</span>
          </div>
          <div class="space-canvas" id="spaceCanvas" aria-label="Connected Leon canvas spaces"></div>
          <div class="focus-grid">
            <div class="focus-tile" data-expand-card="next_action" data-motion-key="focus-next" tabindex="0" role="button" aria-label="Expand next action detail">
              <h3>Next action</h3>
              <p class="small" id="shellNextAction">Laden…</p>
            </div>
            <div class="focus-tile" data-expand-card="attention" data-motion-key="focus-attention" tabindex="0" role="button" aria-label="Expand attention detail">
              <h3>Attention</h3>
              <p class="small" id="shellAttention">Laden…</p>
            </div>
            <div class="focus-tile" data-expand-card="memory" data-motion-key="focus-memory" tabindex="0" role="button" aria-label="Expand memory detail">
              <h3>Memory</h3>
              <p class="small" id="shellMemory">Laden…</p>
            </div>
          </div>
          <form id="shellIntentForm" class="intent-row">
            <label aria-label="Intent"><textarea id="shellIntent" placeholder="Vraag Leon om iets te onderzoeken, plannen of voorbereiden."></textarea></label>
            <button type="submit">Routeer intent</button>
          </form>
        </article>
      </div>

      <nav class="dock" aria-label="Leon dock" data-dock-placement="bottom_center_floating">
        <div class="dock-section" role="list" aria-label="Primary spaces">
          <button type="button" class="active" data-space="home" aria-label="Open Home canvas space" aria-pressed="true">Home</button>
          <button type="button" data-space="chat" aria-label="Open Chat canvas space" aria-pressed="false">Chat</button>
          <button type="button" data-space="workflows" aria-label="Open Tasks canvas space" aria-pressed="false">Tasks</button>
          <button type="button" data-space="memory" aria-label="Open Memory canvas space" aria-pressed="false">Memory</button>
          <button type="button" data-space="skills" aria-label="Open Skills canvas space" aria-pressed="false">Skills</button>
          <button type="button" data-space="projects" aria-label="Open Projects canvas space" aria-pressed="false">Projects</button>
          <button type="button" data-space="settings" aria-label="Open Settings canvas space" aria-pressed="false">Settings</button>
        </div>
        <span class="dock-divider" aria-hidden="true"></span>
        <div class="dock-section" role="list" aria-label="Core actions">
          <button type="button" data-dock-action="new_intent" data-target-space="chat" data-operation="focus_intent" aria-label="Start a new Leon intent">Intent</button>
          <button type="button" data-dock-action="review_attention" data-target-space="skills" data-operation="focus_attention" aria-label="Open attention and review queues">Review</button>
          <button type="button" data-dock-action="search_memory" data-target-space="memory" data-operation="focus_memory_search" aria-label="Search Leon memory">Memory</button>
          <button type="button" data-dock-action="morning_brief" data-target-space="home" data-operation="generate_morning_brief" aria-label="Generate or inspect the morning brief">Brief</button>
        </div>
      </nav>
    </section>

    <div class="detail-backdrop" id="detailBackdrop" hidden>
      <article class="detail-window" id="detailWindow" role="dialog" aria-modal="true" aria-labelledby="detailTitle">
        <div class="item-head">
          <div>
            <h2 id="detailTitle">Detail</h2>
            <p class="small muted" id="detailSubtitle"></p>
          </div>
          <button type="button" id="detailClose" aria-label="Close detail window">Close</button>
        </div>
        <div class="detail-body" id="detailBody"></div>
      </article>
    </div>

    <details class="operations-shell" id="technicalInspectSurfaces">
      <summary><span>Settings/Inspect · Control-plane inspection surfaces</span><span class="small muted">technical state stays internal</span></summary>
      <p class="operations-label">Control-plane inspection surfaces</p>

    <header>
      <div>
        <h2>Operational state</h2>
        <p>Voortgang, approvals, taakqueue en veilige local env-intake blijven inspecteerbaar onder de Leon-omgeving.</p>
      </div>
      <div class="status-pill"><span class="dot" id="runDot"></span><span id="runStatus">laden…</span></div>
    </header>

    <section class="grid cols">
      <article class="card span-4">
        <h2>Projectstatus</h2>
        <div class="metric" id="phaseMetric">—</div>
        <p id="phaseText">Laden…</p>
        <div style="height:14px"></div>
        <div class="progress"><div class="bar" id="progressBar" style="width:0%"></div></div>
      </article>

      <article class="card span-4">
        <h2>Open approvals</h2>
        <div class="metric" id="approvalMetric">—</div>
        <p>Risicovolle acties blijven hier wachten tot jij beslist.</p>
      </article>

      <article class="card span-4">
        <h2>Env intake</h2>
        <div class="metric" id="envMetric">—</div>
        <p>Secrets gaan naar <code>.env.local</code> en worden niet teruggestuurd naar de UI.</p>
      </article>

      <article class="card span-12">
        <h2>Model routing</h2>
        <div class="list" id="modelPolicy"></div>
      </article>

      <article class="card span-12">
        <div class="item-head">
          <div>
            <h2>Morning brief</h2>
            <p class="small muted">Rustige samenvatting van de laatste night run. Inspectors staan standaard dicht.</p>
          </div>
          <button type="button" onclick="requestMorningBrief()">Genereer brief</button>
        </div>
        <p class="small" id="morningBriefResult"></p>
        <div class="list" id="morningBrief"></div>
      </article>

      <article class="card span-12">
        <h2>UI Composition foundation</h2>
        <p class="small muted">Read-only component-DNA en assistant statuslaag. Dit is niet de definitieve chat UI; het voorkomt juist ad-hoc UI en behoudt safety states.</p>
        <form id="uiComposeForm" class="grid" style="margin-top:14px">
          <div class="form-row">
            <label>Route<select id="uiRoute"><option>direct_answer</option><option>clarification_required</option><option>quick_tool_use</option><option>memory_retrieval</option><option>shell_agent_flow</option><option>research_agent</option><option>task_queue</option><option>approval_required</option><option>refuse_redirect</option><option>unknown_route</option></select></label>
            <label>Task status<select id="uiTaskStatus"><option value="">none</option><option>waiting_for_approval</option><option>waiting_for_secret</option><option>blocked</option><option>review</option><option>done</option></select></label>
            <label>Risk<select id="uiRisk"><option>low</option><option>medium</option><option>high</option><option>critical</option></select></label>
          </div>
          <div class="form-row">
            <label>Component need optioneel<input id="uiComponentNeed" placeholder="ApprovalSheet of onbekend component" /></label>
            <label><input id="uiRequiresApproval" type="checkbox" /> Requires approval</label>
            <label><input id="uiMissingSecret" type="checkbox" /> Missing secret</label>
          </div>
          <button type="submit">Preview compositie</button>
          <p class="small" id="uiComposeResult"></p>
        </form>
        <div style="height:14px"></div>
        <div class="list" id="uiCompositionPreview"></div>
      </article>

      <article class="card span-12">
        <h2>Tool / MCP registry</h2>
        <p class="small muted">GitHub-repo’s en MCP-servers worden eerst kandidaat-manifesten. Checks voeren niets uit; ze beslissen alleen of een toolactie binnen scope en approval valt.</p>
        <form id="toolManifestForm" class="grid" style="margin-top:14px">
          <label>Manifest JSON<textarea id="toolManifestJson" placeholder='{"tool_id":"github-mcp-candidate","name":"GitHub MCP Server","source_type":"mcp_server","source_url":"https://github.com/github/github-mcp-server","status":"candidate","risk_level":"medium","read_scopes":["repo:metadata"],"write_scopes":["repo:issues"],"required_env_keys":["GITHUB_TOKEN"]}'></textarea></label>
          <div style="display:flex; gap:8px; flex-wrap:wrap">
            <button type="submit">Registreer kandidaat</button>
            <button type="button" onclick="fillToolCandidate()">Vul GitHub kandidaat</button>
            <button type="button" onclick="refreshGithubCandidates()">Refresh GitHub metadata</button>
          </div>
          <p class="small" id="toolManifestResult"></p>
        </form>
        <form id="toolCheckForm" class="grid" style="margin-top:14px">
          <div class="form-row">
            <label>Tool<select id="toolCheckId"></select></label>
            <label>Scope<input id="toolCheckScope" placeholder="repo:metadata" /></label>
            <button type="submit">Check permissie</button>
          </div>
          <div class="form-row">
            <label>Actie<select id="toolCheckAction"><option>read</option><option>write</option><option>install</option><option>connect</option><option>resource_heavy</option><option>spend_money</option><option>read_raw_secret</option></select></label>
            <label>Consumed approval id optioneel<input id="toolCheckApproval" placeholder="approval-..." /></label>
            <span></span>
          </div>
          <p class="small" id="toolCheckResult"></p>
        </form>
        <div style="height:14px"></div>
        <h3>Hergebruik shortlist</h3>
        <button type="button" onclick="createToolReviewTasks()">Maak review-taken voor Evaluate now</button>
        <p class="small" id="toolReviewTaskResult"></p>
        <div class="list" id="toolAdoptionShortlist"></div>
        <div style="height:14px"></div>
        <h3>Review packets</h3>
        <div class="list" id="toolReviewPackets"></div>
        <div style="height:14px"></div>
        <h3>Alle manifests</h3>
        <div class="list" id="toolRegistry"></div>
        <div style="height:14px"></div>
        <h3>Recente permission checks</h3>
        <div class="list" id="toolPermissionChecks"></div>
      </article>

      <article class="card span-12">
        <h2>Decision Layer</h2>
        <p class="small muted">Routeert alleen lokaal en voert geen actie uit. High-risk werk blijft achter approval gates.</p>
        <form id="routingForm" class="grid" style="margin-top:14px">
          <div class="form-row">
            <label>Prompt<textarea id="routingPrompt" placeholder="Bijv. onderzoek beste MCP servers voor agenda en mail"></textarea></label>
            <label>Expected route optioneel<input id="routingExpected" placeholder="direct_answer, approval_required, …" /></label>
            <button type="submit">Routeer</button>
          </div>
          <p class="small" id="routingResult"></p>
        </form>
        <div style="height:14px"></div>
        <button type="button" onclick="runRoutingEval()">Run routing eval</button>
        <div style="height:14px"></div>
        <div class="list" id="routingEvalSummary"></div>
        <div style="height:14px"></div>
        <div class="list" id="routingDecisions"></div>
      </article>

      <article class="card span-12">
        <h2>Planner read-only PoC</h2>
        <p class="small muted">Lokale sample-data analyseert agenda/mail-signalen en maakt alleen previews. Geen MCP install, geen accountkoppeling, geen Gmail/Calendar write en geen secret-read.</p>
        <form id="plannerPreviewForm" class="grid" style="margin-top:14px">
          <div class="form-row">
            <label>Vraag<textarea id="plannerPreviewRequest" placeholder="Plan een projectblok zonder iets in mijn agenda te schrijven"></textarea></label>
            <label>Actie<select id="plannerPreviewAction"><option value="preview">preview</option><option value="create_event">create_event (moet geweigerd worden)</option><option value="send">send mail (moet geweigerd worden)</option><option value="connect_account">connect account (moet geweigerd worden)</option></select></label>
            <button type="submit">Maak planner preview</button>
          </div>
          <p class="small" id="plannerPreviewResult"></p>
        </form>
        <div style="height:14px"></div>
        <div class="list" id="plannerPreviews"></div>
      </article>

      <article class="card span-12">
        <h2>Memory en knowledge graph MVP</h2>
        <p class="small muted">Review-first lokaal geheugen. Nieuwe memory start als candidate; sensitive/long-term active memory vereist review note. Delete scrubt content en graph-labels.</p>
        <form id="memoryRetrievalForm" class="grid" style="margin-top:14px">
          <label>Vraag aan memory<textarea id="memoryRetrievalQuery" placeholder="Vraag iets over een project, document of context"></textarea></label>
          <div class="form-row">
            <label>Scope<select id="memoryRetrievalScope"><option>context</option><option>project</option><option>document</option><option>memory</option><option>source</option></select></label>
            <label>Resultaten<input id="memoryRetrievalLimit" type="number" min="1" max="10" step="1" value="5" /></label>
            <button type="submit">Zoek kennis</button>
          </div>
          <p class="small" id="memoryRetrievalResult"></p>
        </form>
        <div style="height:14px"></div>
        <h3>Recent retrieval</h3>
        <div class="list" id="memoryRetrievalQueries"></div>
        <div style="height:14px"></div>
        <form id="memoryForm" class="grid" style="margin-top:14px">
          <label>Memory content<textarea id="memoryContent" placeholder="Bijv. Leon wil antwoorden standaard in het Nederlands. Geen secrets of wachtwoorden."></textarea></label>
          <div class="form-row">
            <label>Type<select id="memoryType"><option>working</option><option>session</option><option>long_term</option><option>episodic</option><option>negative</option><option>preference</option><option>project_fact</option></select></label>
            <label>Bron<input id="memorySource" placeholder="docs/... of task-..." /></label>
            <label>Confidence<input id="memoryConfidence" type="number" min="0" max="1" step="0.01" value="0.70" /></label>
          </div>
          <div class="form-row">
            <label>Sensitivity<select id="memorySensitivity"><option>medium</option><option>low</option><option>high</option></select></label>
            <label>Privacy<select id="memoryPrivacy"><option>private</option><option>normal</option><option>sensitive</option></select></label>
            <label>Expiry optioneel<input id="memoryExpiry" placeholder="2026-12-31T00:00:00+00:00" /></label>
          </div>
          <div class="form-row">
            <label>Graph entities comma-separated<input id="memoryEntities" placeholder="Leon, taalvoorkeur, project" /></label>
            <label>Review note optioneel<input id="memoryReviewNote" placeholder="Waarom mag dit actief/langdurig worden?" /></label>
            <button type="submit">Maak memory candidate</button>
          </div>
          <p class="small" id="memoryResult"></p>
        </form>
        <div style="height:14px"></div>
        <h3>Memory items</h3>
        <div class="list" id="memoryItems"></div>
        <div style="height:14px"></div>
        <h3>Graph relaties</h3>
        <div class="list" id="memoryGraphEdges"></div>
      </article>

      <article class="card span-7">
        <h2>Fases</h2>
        <div class="list" id="phases"></div>
      </article>

      <article class="card span-5">
        <h2>API keys / secrets</h2>
        <form id="secretForm" class="grid">
          <div class="form-row">
            <label>Key<select id="secretKey"></select></label>
            <label>Waarde<input id="secretValue" type="password" autocomplete="off" placeholder="plak key hier" /></label>
            <button type="submit">Opslaan</button>
          </div>
          <p class="small" id="secretResult"></p>
        </form>
        <div style="height:14px"></div>
        <div class="list" id="envList"></div>
      </article>

      <article class="card span-8">
        <h2>Tasks</h2>
        <p class="small muted">Volledige taakdetails, inclusief done en rejected, blijven hier inspecteerbaar.</p>
        <form id="taskForm" class="grid" style="margin-bottom:14px">
          <div class="form-row">
            <label>Titel<input id="taskTitle" placeholder="Nieuwe taak" /></label>
            <label>Doel<input id="taskGoal" placeholder="Wat moet bewezen klaar zijn?" /></label>
            <button type="submit">Taak maken</button>
          </div>
          <div class="form-row">
            <label>Waarde 0-5<input id="taskValue" type="number" min="0" max="5" value="3" /></label>
            <label>Parent task id optioneel<input id="taskParent" placeholder="task-..." /></label>
            <label>Bronnen, één per regel<textarea id="taskSources" placeholder="docs/...&#10;https://..."></textarea></label>
          </div>
        </form>
        <div class="list" id="tasks"></div>
      </article>

      <article class="card span-4">
        <h2>Approval queue</h2>
        <div class="list" id="approvals"></div>
      </article>

      <article class="card span-12">
        <h2>Audit log</h2>
        <div class="list" id="auditLog"></div>
      </article>

      <article class="card span-12">
        <h2>Source records</h2>
        <p class="small muted">Geindexeerde bronnen blijven rustig samengevat; details tonen alleen redacted excerpts, graph links, policy en rollback-data.</p>
        <div class="list" id="sourceRecords"></div>
      </article>

      <article class="card span-12">
        <h2>Orchestration proposals</h2>
        <p class="small muted">Voorstellen maken alleen lokale tasks/approval-cards aan na review; ze voeren geen acties uit.</p>
        <div class="list" id="orchestrationProposals"></div>
      </article>

      <article class="card span-12">
        <h2>Agent assignment proposals</h2>
        <p class="small muted">Assignments starten alleen local_mock agent-runs na expliciete apply; geen externe calls of secret reads.</p>
        <div class="list" id="agentAssignmentProposals"></div>
      </article>

      <article class="card span-12">
        <h2>Provider adapter dry-runs</h2>
        <p class="small muted">Dry-runs maken alleen een lokaal providerplan. Geen SDK import, install, provider-call, approval-consumptie of secretwaarde.</p>
        <div class="list" id="providerDryRuns"></div>
      </article>

      <article class="card span-12">
        <h2>MCP candidate intakes</h2>
        <p class="small muted">MCP intakes leggen reviewchecklists vast. Geen install, connect, statuspromotie of approval.</p>
        <div class="list" id="mcpCandidateIntakes"></div>
      </article>

      <article class="card span-12">
        <h2>Agent runs</h2>
        <div class="list" id="agentRuns"></div>
      </article>

      <article class="card span-12">
        <h2>Engineering regels</h2>
        <pre id="rules"></pre>
      </article>
    </section>
    </details>
  </main>

  <script>
    let currentState = null;
    let activeCanvasSpace = "home";
    let detailReturnFocus = null;
    const reducedMotionMedia = window.matchMedia("(prefers-reduced-motion: reduce)");

    function motionConfig() {
      const system = currentState?.leon_canvas_shell?.animation_system || {};
      const timing = system.timing || {};
      return {
        standard: Number(timing.standard_ms || 260),
        emphasis: Number(timing.emphasis_ms || 360),
        max: Number(timing.max_ms || 420),
        easing: timing.easing || "cubic-bezier(0.2, 0.8, 0.2, 1)",
        reduced: reducedMotionMedia.matches
      };
    }

    function captureMotionBounds() {
      if (motionConfig().reduced) return new Map();
      return new Map(Array.from(document.querySelectorAll("[data-motion-key]")).map(node => [
        node.dataset.motionKey,
        node.getBoundingClientRect()
      ]));
    }

    function playLayoutContinuity(previousBounds) {
      if (!previousBounds?.size || motionConfig().reduced) return;
      const config = motionConfig();
      requestAnimationFrame(() => {
        document.querySelectorAll("[data-motion-key]").forEach(node => {
          const previous = previousBounds.get(node.dataset.motionKey);
          if (!previous || typeof node.animate !== "function") return;
          const current = node.getBoundingClientRect();
          const dx = previous.left - current.left;
          const dy = previous.top - current.top;
          const sx = previous.width && current.width ? previous.width / current.width : 1;
          const sy = previous.height && current.height ? previous.height / current.height : 1;
          if (Math.abs(dx) + Math.abs(dy) + Math.abs(sx - 1) + Math.abs(sy - 1) < 0.5) return;
          node.animate(
            [
              { transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})` },
              { transform: "translate(0, 0) scale(1, 1)" }
            ],
            { duration: Math.min(config.emphasis, config.max), easing: config.easing }
          );
        });
      });
    }

    function setPanelMode(mode) {
      const canvas = document.getElementById("leonCanvas");
      if (!canvas) return;
      canvas.dataset.panelMode = mode === "merged" ? "merged" : "split";
    }

    function applyMagneticMotion(spaceId) {
      document.querySelectorAll(".space-node[data-space-node]").forEach(node => {
        node.classList.remove("magnetized");
        node.style.removeProperty("--magnet-x");
        node.style.removeProperty("--magnet-y");
      });
      if (motionConfig().reduced) return;
      const canvas = document.getElementById("spaceCanvas");
      const node = Array.from(document.querySelectorAll(".space-node[data-space-node]")).find(item => item.dataset.spaceNode === spaceId);
      if (!canvas || !node) return;
      const canvasRect = canvas.getBoundingClientRect();
      const nodeRect = node.getBoundingClientRect();
      const max = Number(currentState?.leon_canvas_shell?.animation_system?.operations?.magnetic_move?.max_translate_px || 14);
      const clamp = (value) => Math.max(-max, Math.min(max, value));
      const dx = clamp(((canvasRect.left + canvasRect.width / 2) - (nodeRect.left + nodeRect.width / 2)) * 0.08);
      const dy = clamp(((canvasRect.top + canvasRect.height / 2) - (nodeRect.top + nodeRect.height / 2)) * 0.08 - 2);
      node.style.setProperty("--magnet-x", `${dx.toFixed(1)}px`);
      node.style.setProperty("--magnet-y", `${dy.toFixed(1)}px`);
      node.classList.add("magnetized");
    }

    function detailPayloadFor(source) {
      const kind = source?.dataset?.expandCard || source?.dataset?.spaceNode || "detail";
      if (source?.dataset?.spaceNode && currentState) {
        const shell = currentState.leon_canvas_shell || {};
        const space = (shell.spaces || []).find(item => item.id === source.dataset.spaceNode) || {};
        const signal = spaceSignal(space.id || "home", currentState);
        return {
          title: `${space.label || "Space"} canvas`,
          subtitle: space.purpose || "Connected Leon space.",
          items: [
            ["Next", signal.next],
            ["Attention", signal.attention],
            ["Detail", signal.detail],
            ["Components", (space.approved_components || []).join(", ") || "No approved components."]
          ]
        };
      }
      const active = currentState ? spaceSignal(activeCanvasSpace, currentState) : {};
      const payloads = {
        next_action: {
          title: "Next action",
          subtitle: active.next || "",
          items: [["Canvas", activeCanvasSpace], ["Focus", active.next || "No active next action."]]
        },
        attention: {
          title: "Attention",
          subtitle: active.attention || "",
          items: [["Canvas", activeCanvasSpace], ["Signal", active.attention || "No attention signal."]]
        },
        memory: {
          title: "Memory",
          subtitle: active.detail || "",
          items: [["Canvas", activeCanvasSpace], ["Context", active.detail || "No memory context."]]
        }
      };
      return payloads[kind] || { title: "Detail", subtitle: "", items: [] };
    }

    function openDetailWindow(source) {
      const backdrop = document.getElementById("detailBackdrop");
      const windowNode = document.getElementById("detailWindow");
      if (!backdrop || !windowNode) return;
      const payload = detailPayloadFor(source);
      detailReturnFocus = source || document.activeElement;
      document.getElementById("detailTitle").textContent = payload.title;
      document.getElementById("detailSubtitle").textContent = payload.subtitle;
      document.getElementById("detailBody").innerHTML = (payload.items || []).map(([label, value]) => `
        <div class="item">
          <h3>${esc(label)}</h3>
          <p class="small">${esc(value)}</p>
        </div>
      `).join("");
      const sourceRect = source?.getBoundingClientRect?.();
      backdrop.hidden = false;
      document.body.classList.add("detail-open");
      document.getElementById("detailClose")?.focus({ preventScroll: true });
      if (motionConfig().reduced || !sourceRect || typeof windowNode.animate !== "function") return;
      const config = motionConfig();
      const targetRect = windowNode.getBoundingClientRect();
      const scaleX = sourceRect.width / Math.max(targetRect.width, 1);
      const scaleY = sourceRect.height / Math.max(targetRect.height, 1);
      const dx = sourceRect.left + sourceRect.width / 2 - (targetRect.left + targetRect.width / 2);
      const dy = sourceRect.top + sourceRect.height / 2 - (targetRect.top + targetRect.height / 2);
      backdrop.animate([{ opacity: 0 }, { opacity: 1 }], { duration: config.standard, easing: config.easing });
      windowNode.animate(
        [
          { transform: `translate(${dx}px, ${dy}px) scale(${scaleX}, ${scaleY})`, opacity: 0.86 },
          { transform: "translate(0, 0) scale(1, 1)", opacity: 1 }
        ],
        { duration: Math.min(config.emphasis, config.max), easing: config.easing }
      );
    }

    function closeDetailWindow() {
      const backdrop = document.getElementById("detailBackdrop");
      if (!backdrop) return;
      backdrop.hidden = true;
      document.body.classList.remove("detail-open");
      if (detailReturnFocus && typeof detailReturnFocus.focus === "function") {
        detailReturnFocus.focus({ preventScroll: true });
      }
      detailReturnFocus = null;
    }

    const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const pct = (n) => Math.max(0, Math.min(100, Number(n || 0)));
    const shellStatusKey = (state) => {
      if (state.leon_character?.status_color_key) return state.leon_character.status_color_key;
      const previewState = state.ui_composition_preview?.assistant_state?.id || "idle";
      const pendingApprovals = (state.approvals || []).some(item => item.status === "pending");
      const missingSecret = (state.required_env || []).some(item => !item.present);
      const failedTask = (state.tasks || []).some(item => item.status === "failed");
      if (failedTask) return "error";
      if (pendingApprovals || missingSecret || previewState.includes("approval") || previewState.includes("secret") || previewState === "blocked") return "attention";
      if (["thinking", "researching", "reviewing"].includes(previewState)) return "thinking";
      if (previewState === "acting") return "acting";
      return "idle";
    };

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { "content-type": "application/json" },
        ...options
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || response.statusText);
      return data;
    }

    function compactJson(value) {
      if (Array.isArray(value) && !value.length) return "[]";
      if (value && typeof value === "object" && !Array.isArray(value) && !Object.keys(value).length) return "{}";
      return JSON.stringify(value ?? null, null, 2);
    }

    function renderTransparency(transparency) {
      const payload = transparency || {};
      const defaultView = payload.default_view || {};
      const inspectors = payload.inspectors || [];
      if (!inspectors.length) return "";
      const attention = defaultView.risk_or_attention_signals || [];
      return `
        <div class="inspector-block">
          <div class="item-head">
            <div>
              <h3>Status · ${esc(defaultView.status || "unknown")}</h3>
              <p class="small">${esc(defaultView.final_result || "Geen eindresultaat.")}</p>
            </div>
            <span class="tag">inspectors collapsed</span>
          </div>
          <p class="small muted">Progress: ${esc(compactJson(defaultView.progress))}</p>
          ${attention.length ? `<p class="small notice">Attention: ${esc(attention.map(item => typeof item === "string" ? item : compactJson(item)).join(" · "))}</p>` : ""}
          <details>
            <summary>Inspecteer bronnen, modellen, kosten, prompts/samenvattingen, logs, diffs, graph, policy en rollback</summary>
            ${inspectors.map(group => `
              <details>
                <summary>${esc(group.title)}</summary>
                <pre>${esc(compactJson(group.content))}</pre>
              </details>
            `).join("")}
          </details>
        </div>
      `;
    }

    function renderModelRouteDecision(modelRoute) {
      if (!modelRoute) return "";
      const decision = modelRoute.route_decision || {};
      const fallback = modelRoute.fallback || {};
      const local = modelRoute.local_gpu_diagnostics || {};
      const label = decision.label || (fallback.active ? "API fallback" : (modelRoute.route === "local_gpu" ? "Local M40/GPU" : "API route"));
      const reason = decision.reason || modelRoute.user_visible_reason || modelRoute.reason || "Route decision recorded.";
      const localBits = local.requested ? `Local GPU: ${local.selected ? "selected" : "not selected"} · gate: ${local.route_allowed ? "passed" : "blocked"} · status: ${local.local_route_status || "not_attempted"}${local.local_latency_ms != null ? ` · latency: ${local.local_latency_ms}ms/${local.max_latency_ms || "—"}ms` : ""}` : "";
      return `
        <p class="small notice">Route decision: ${esc(label)} · final: ${esc(decision.final_route || modelRoute.route || "—")}</p>
        <p class="small muted">${esc(reason)}</p>
        ${fallback.active ? `<p class="small attention">Fallback: ${esc(fallback.from_route || "local_gpu")} -> ${esc(fallback.to_route || modelRoute.route || "api")} · ${esc(fallback.reason || "API fallback selected.")}</p>` : ""}
        ${localBits ? `<p class="small muted">${esc(localBits)}</p>` : ""}
      `;
    }

    function updateDockActive(spaceId) {
      document.querySelectorAll(".dock button[data-space]").forEach(button => {
        const isActive = button.dataset.space === spaceId;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      });
    }

    function setDockFromContract(state) {
      const dock = state.leon_canvas_shell?.dock || {};
      const placement = dock.placement || "bottom_center_floating";
      document.querySelector(".dock")?.setAttribute("data-dock-placement", placement);
      (dock.primary_spaces || []).forEach(item => {
        const button = Array.from(document.querySelectorAll(".dock button[data-space]")).find(node => node.dataset.space === item.id);
        if (!button) return;
        button.textContent = item.label || item.id;
        button.setAttribute("aria-label", item.aria_label || `Open ${item.label || item.id} canvas space`);
      });
      (dock.core_actions || []).forEach(item => {
        const button = Array.from(document.querySelectorAll(".dock button[data-dock-action]")).find(node => node.dataset.dockAction === item.id);
        if (!button) return;
        button.textContent = item.label || item.id;
        button.dataset.targetSpace = item.target_space || "home";
        button.dataset.operation = item.operation || "focus_space";
        button.setAttribute("aria-label", item.aria_label || item.label || item.id);
      });
    }

    function focusElementInCanvas(elementId) {
      const target = document.getElementById(elementId);
      if (!target) return;
      target.scrollIntoView({ behavior: motionConfig().reduced ? "auto" : "smooth", block: "center" });
      if (typeof target.focus === "function") target.focus({ preventScroll: true });
    }

    function setCanvasSpace(spaceId, options = {}) {
      const previousBounds = captureMotionBounds();
      activeCanvasSpace = spaceId || "home";
      if (currentState) renderSpaceCanvas(currentState);
      playLayoutContinuity(previousBounds);
      if (options.scroll !== false) {
        document.getElementById("spaceCanvas")?.scrollIntoView({ behavior: motionConfig().reduced ? "auto" : "smooth", block: "center" });
      }
    }

    async function handleDockAction(button) {
      const operation = button.dataset.operation || "focus_space";
      let targetSpace = button.dataset.targetSpace || "home";
      if (operation === "focus_attention" && currentState) {
        const pendingApprovals = (currentState.approvals || []).some(item => item.status === "pending");
        const missingEnv = (currentState.required_env || []).some(item => !item.present);
        const reviewTasks = (currentState.tasks || []).some(item => ["review", "blocked"].includes(item.status));
        if (pendingApprovals) targetSpace = "skills";
        else if (missingEnv) targetSpace = "settings";
        else if (reviewTasks) targetSpace = "workflows";
      }
      setCanvasSpace(targetSpace, { scroll: operation === "focus_space" });
      if (operation === "focus_intent") {
        focusElementInCanvas("shellIntent");
      } else if (operation === "focus_attention") {
        if (targetSpace === "settings") focusElementInCanvas("secretForm");
        else if (targetSpace === "workflows") focusElementInCanvas("taskForm");
        else focusElementInCanvas("approvals");
      } else if (operation === "focus_memory_search") {
        focusElementInCanvas("memoryRetrievalQuery");
      } else if (operation === "generate_morning_brief") {
        await requestMorningBrief();
        focusElementInCanvas("morningBrief");
      }
    }

    function spaceSignal(spaceId, state) {
      const openTasks = (state.tasks || []).filter(task => task.status !== "done");
      const pendingApprovals = (state.approvals || []).filter(item => item.status === "pending");
      const preparedProposals = (state.orchestration_proposals || []).filter(item => item.status === "prepared");
      const missingEnv = (state.required_env || []).filter(item => !item.present);
      const memoryCount = (state.memory_items || []).length;
      const graphCount = (state.memory_graph_edges || []).length;
      const toolCount = (state.tool_manifests || []).length;
      const sourceCount = (state.source_records || []).length;
      const routes = (state.routing_decisions || []).length;
      const runCount = (state.agent_runs || []).length;
      const phase = state.metadata?.current_phase || "Leon";
      const signals = {
        home: {
          next: preparedProposals[0]?.summary || openTasks[0]?.title || "Geen open taak; Leon staat klaar voor nieuwe intent.",
          attention: pendingApprovals.length ? `${pendingApprovals.length} approval(s) wachten.` : (preparedProposals.length ? `${preparedProposals.length} voorstel(len) wachten op review.` : "Geen directe attention-state."),
          detail: `${phase} · ${pct(state.metadata?.progress_percent)}%`
        },
        chat: {
          next: "Routeer een compacte vraag, voorstel of vervolgactie.",
          attention: preparedProposals.length ? `${preparedProposals.length} proposal(s) klaar.` : (routes ? `${routes} recente routing decision(s).` : "Nog geen recente chatroutes."),
          detail: "Intent -> proposal -> approval -> continuation"
        },
        workflows: {
          next: openTasks[0]?.title || "Geen actieve workflow in de lokale queue.",
          attention: runCount ? `${runCount} agent run(s) inspecteerbaar.` : "Nog geen agent run actief.",
          detail: `${openTasks.length} open taak/taken`
        },
        memory: {
          next: "Zoek, corrigeer, activeer, vergeet of scrub memory.",
          attention: `${memoryCount} memory item(s), ${graphCount} graph relatie(s).`,
          detail: "Inspectable local memory"
        },
        skills: {
          next: "Beoordeel toolkandidaten en permission checks zonder impliciete uitvoering.",
          attention: pendingApprovals.length ? `${pendingApprovals.length} gated approval(s).` : `${toolCount} tool manifest(en).`,
          detail: "Skills + MCP + approvals"
        },
        projects: {
          next: openTasks.find(task => (task.source_refs || []).length)?.title || "Bundel projectcontext, bronnen en research boards.",
          attention: sourceCount ? `${sourceCount} source record(s) geindexeerd.` : "Nog geen source records in deze state.",
          detail: "Project context + source stack"
        },
        settings: {
          next: missingEnv.length ? "Vul ontbrekende env keys via write-only intake." : "Controleer modelroutes en autonomiebeleid.",
          attention: missingEnv.length ? `${missingEnv.length} env item(s) ontbreken.` : "Runtime policy beschikbaar.",
          detail: `${state.runtime?.auth_mode || "local"} auth · secrets hidden`
        }
      };
      return signals[spaceId] || signals.home;
    }

    function homeTaskAttention(state, activeSignal) {
      const tasks = state.tasks || [];
      const approvals = state.approvals || [];
      const requiredEnv = state.required_env || [];
      const agentRuns = state.agent_runs || [];
      const nightRuns = state.night_queue_runs || [];
      const preparedProposal = (state.orchestration_proposals || []).find(item => item.status === "prepared");
      const pendingApproval = approvals.find(item => item.status === "pending");
      const runningRun = agentRuns.find(item => ["running", "active", "executing", "in_progress"].includes(item.status))
        || nightRuns.find(item => ["running", "active", "executing", "in_progress"].includes(item.status));
      const waitingTask = tasks.find(task => ["waiting_for_approval", "waiting_for_secret", "waiting_for_user", "blocked"].includes(task.status));
      const missingEnv = requiredEnv.find(item => !item.present);
      const reviewTask = tasks.find(task => ["review", "active"].includes(task.status));
      const openTask = tasks.find(task => !["done", "rejected"].includes(task.status));
      const doneTask = tasks.find(task => task.status === "done") || tasks.find(task => task.status === "rejected");

      if (pendingApproval) {
        return {
          state: "approval needed",
          title: pendingApproval.title || pendingApproval.summary || "Approval needed",
          detail: pendingApproval.reason || "Leon wacht op jouw keuze voordat deze actie verder gaat.",
          tag: "Approval"
        };
      }
      if (runningRun) {
        const runTask = runningRun.task || {};
        return {
          state: "running",
          title: runTask.title || runningRun.task_id || runningRun.id || "Agent run actief",
          detail: `${runningRun.status || "running"} · ${runningRun.agent_role || runningRun.runner_kind || "Leon"}`,
          tag: "Running"
        };
      }
      if (waitingTask || missingEnv) {
        const item = waitingTask || {};
        return {
          state: "waiting",
          title: item.title || missingEnv?.key || "Waiting for input",
          detail: item.blocked_reason || item.review_note || (missingEnv ? "Secret intake is nodig voordat Leon verder kan." : `${item.status || "waiting"} · ${item.risk || "low"} risk`),
          tag: "Waiting"
        };
      }
      if (preparedProposal) {
        let proposal = {};
        try { proposal = JSON.parse(preparedProposal.proposal_json || "{}"); } catch (_) {}
        const taskCount = (proposal.proposed_tasks || []).length;
        const approvalCount = (proposal.proposed_approvals || []).length;
        return {
          state: "proposal ready",
          title: preparedProposal.summary || proposal.summary || "Leon heeft een voorstel klaar",
          detail: `${preparedProposal.route || proposal.route} · ${taskCount} task(s) · ${approvalCount} approval gate(s) · review voordat iets wordt aangemaakt.`,
          tag: "Proposal"
        };
      }
      if (reviewTask || openTask) {
        const item = reviewTask || openTask;
        return {
          state: "current task",
          title: item.title || activeSignal.next || "Current task",
          detail: `${item.status || "open"} · ${item.risk || "low"} risk · ${item.approval_status || "no approval gate"}`,
          tag: "Task"
        };
      }
      if (doneTask) {
        return {
          state: "done",
          title: doneTask.title || "Laatste taak afgerond",
          detail: doneTask.result || doneTask.verification_note || `${doneTask.status} · details blijven beschikbaar in Tasks.`,
          tag: "Done"
        };
      }
      return {
        state: "current task",
        title: activeSignal.next || "Leon staat klaar voor een nieuwe intent.",
        detail: "Geen taak vraagt nu aandacht. Tasks bevat de volledige historie zodra die bestaat.",
        tag: "Ready"
      };
    }

    function renderHomeFocusCanvas(state, activeSignal) {
      const pendingApprovals = (state.approvals || []).filter(item => item.status === "pending");
      const missingEnv = (state.required_env || []).filter(item => !item.present);
      const attention = homeTaskAttention(state, activeSignal);
      const attentionText = pendingApprovals.length
        ? `${pendingApprovals.length} approval(s) wachten op jouw keuze.`
        : (missingEnv.length ? `${missingEnv.length} setup item(s) vragen aandacht.` : "Geen directe aandacht nodig.");
      const briefText = (state.morning_brief?.generated?.sections || state.morning_brief?.latest_night_run?.morning_brief?.sections || []).length
        ? "Morning brief is beschikbaar."
        : "Nog geen morning brief voor vandaag.";
      return `
        <div class="home-focus-card primary" aria-label="Leon home focus" data-motion-key="home-focus-primary">
          <div class="item-head">
            <div>
              <h3>${esc(attention.state)}</h3>
              <p class="small">${esc(attention.title)}</p>
            </div>
            <span class="tag">${esc(attention.tag)}</span>
          </div>
          <p class="small muted">${esc(attention.detail)}</p>
        </div>
        <div class="home-signal-row" data-motion-key="home-focus-signals">
          <div class="home-focus-card">
            <h3>Attention</h3>
            <p class="small">${esc(attentionText)}</p>
          </div>
          <div class="home-focus-card">
            <h3>Morning brief</h3>
            <p class="small">${esc(briefText)}</p>
          </div>
        </div>
      `;
    }

    function renderTaskDetailCard(task, options = {}) {
      const controls = options.controls !== false;
      return `
        <div class="item">
          <div class="item-head">
            <div>
              <h3>${esc(task.title)}</h3>
              <p class="small">${esc(task.goal || task.acceptance)}</p>
            </div>
            <span class="tag ${esc(task.priority).toLowerCase()}">${esc(task.priority)}</span>
          </div>
          <p class="small muted">Status: ${esc(task.status)} · Eigenaar: ${esc(task.owner)} · Risico: ${esc(task.risk)} · Waarde: ${esc(task.value_score ?? 3)}/5 · Approval: ${esc(task.approval_status || "none")}</p>
          <p class="small muted">Parent: ${esc(task.parent_task_id || "—")} · Subtaken: ${esc(task.subtask_count || 0)} · Sources: ${esc((task.source_refs || []).join(", ") || "—")}</p>
          ${task.approval_id ? `<p class="small muted">Approval gate: ${esc(task.approval_id)} · ${esc(task.approval_gate_summary || "—")}</p>` : ""}
          ${task.audit_events?.length ? `<p class="small muted">Audit: ${esc(task.audit_events.map(item => `${item.event_type}#${item.sequence}`).join(", "))}</p>` : ""}
          ${task.subtasks?.length ? `<p class="small muted">Subtasks: ${esc(task.subtasks.map(item => `${item.title} (${item.status})`).join(", "))}</p>` : ""}
          ${task.blocked_reason ? `<p class="small notice">Blocked: ${esc(task.blocked_reason)}</p>` : ""}
          ${task.result ? `<p class="small ok">Result: ${esc(task.result)}</p>` : ""}
          ${controls ? `
            <div style="height:10px"></div>
            <div style="display:flex; gap:8px; flex-wrap:wrap">
              <button type="button" onclick="setTaskStatus('${esc(task.id)}', 'planned')">Planned</button>
              <button type="button" onclick="setTaskStatus('${esc(task.id)}', 'active')">Active</button>
              <button type="button" onclick="setTaskStatus('${esc(task.id)}', 'blocked')">Block</button>
              <button type="button" onclick="setTaskStatus('${esc(task.id)}', 'review')">Review</button>
              <button type="button" onclick="setTaskStatus('${esc(task.id)}', 'done')">Done</button>
              <button type="button" onclick="setTaskStatus('${esc(task.id)}', 'rejected')">Reject</button>
              <button type="button" onclick="proposeAgentAssignment('${esc(task.id)}')">Maak assignment</button>
              <button type="button" onclick="createProviderDryRun('${esc(task.id)}')">Provider dry-run</button>
            </div>
          ` : ""}
        </div>
      `;
    }

    function renderTasksCanvas(state) {
      const tasks = state.tasks || [];
      if (!tasks.length) {
        return `<div class="item"><p class="small muted">Nog geen taken. Nieuwe taken verschijnen hier met volledige details.</p></div>`;
      }
      return tasks.map(task => renderTaskDetailCard(task, { controls: false })).join("");
    }

    function renderInspectChips(values) {
      const entries = Object.entries(values || {});
      if (!entries.length) return `<span class="tag">none</span>`;
      return entries.map(([key, value]) => `<span class="tag">${esc(key)}:${esc(value)}</span>`).join("");
    }

    function renderSettingsInspectCanvas(state) {
      const inspect = state.technical_inspect || {};
      const auth = inspect.auth || {};
      const secrets = inspect.secrets || {};
      const audit = inspect.audit || {};
      const approvals = inspect.approvals || {};
      const taskStore = inspect.task_store || {};
      const routing = inspect.routing || {};
      const latestRoute = routing.latest || {};
      const missingKeys = secrets.missing_keys || [];
      return `
        <div class="inspect-grid" aria-label="Settings/Inspect technical state" data-motion-key="settings-inspect-grid">
          <div class="inspect-card">
            <div class="item-head">
              <h3>Auth</h3>
              <span class="tag">${esc(auth.mode || "local")}</span>
            </div>
            <p class="small muted">Dashboard token: ${auth.dashboard_token_configured ? "configured" : "missing"} · env file: ${auth.env_file_exists ? "present" : "absent"}</p>
          </div>
          <div class="inspect-card">
            <div class="item-head">
              <h3>Secrets</h3>
              <span class="tag">${esc(secrets.present || 0)}/${esc(secrets.total_required || 0)}</span>
            </div>
            <p class="small muted">Raw values exposed: ${secrets.raw_values_exposed ? "yes" : "no"}</p>
            <p class="small ${missingKeys.length ? "notice" : "ok"}">${esc(missingKeys.length ? `Missing: ${missingKeys.join(", ")}` : "All required keys are present.")}</p>
          </div>
          <div class="inspect-card">
            <div class="item-head">
              <h3>Audit</h3>
              <span class="tag">${esc(audit.event_count || 0)}</span>
            </div>
            <p class="small ${audit.hash_chain_valid ? "ok" : "danger"}">Hash chain: ${audit.hash_chain_valid ? "valid" : "invalid"}</p>
            <p class="small muted">${esc((audit.latest_events || []).map(item => `${item.event_type}#${item.sequence}`).join(", ") || "No audit events yet.")}</p>
          </div>
          <div class="inspect-card">
            <div class="item-head">
              <h3>Approvals</h3>
              <span class="tag">${esc(approvals.count || 0)}</span>
            </div>
            <div class="inspect-mini-list">${renderInspectChips(approvals.status_counts)}</div>
            <p class="small muted">${esc((approvals.pending || []).map(item => item.title || item.id).join(", ") || "No pending approvals.")}</p>
          </div>
          <div class="inspect-card">
            <div class="item-head">
              <h3>Task store</h3>
              <span class="tag">${esc(taskStore.task_count || 0)}</span>
            </div>
            <div class="inspect-mini-list">${renderInspectChips(taskStore.status_counts)}</div>
            <p class="small muted">${esc((taskStore.open_task_ids || []).join(", ") || "No open task ids.")}</p>
          </div>
          <div class="inspect-card">
            <div class="item-head">
              <h3>Routing</h3>
              <span class="tag">${esc(routing.decision_count || 0)}</span>
            </div>
            <p class="small muted">Latest: ${esc(latestRoute.route || "none")} · ${esc(latestRoute.decision_label || latestRoute.selected_runtime || "no route yet")}</p>
            <p class="small muted">Local GPU: ${routing.local_gpu_route_allowed ? "allowed" : "blocked"} · ${esc(routing.local_gpu_status || "not_validated")}</p>
          </div>
          <div class="inspect-card wide">
            <div class="item-head">
              <div>
                <h3>Internal technical state</h3>
                <p class="small muted">Settings/Inspect contains auth, secrets, audit, approvals, task store and routing summaries. Full records stay below, closed by default.</p>
              </div>
              <span class="tag">${inspect.internal_only ? "internal" : "public"}</span>
            </div>
            <div style="height:10px"></div>
            <button type="button" onclick="openTechnicalInspectSurfaces()">Open full inspect surfaces</button>
          </div>
        </div>
      `;
    }

    function renderProposalCanvas(state) {
      const proposals = state.orchestration_proposals || [];
      if (!proposals.length) {
        return `<div class="item"><p class="small muted">Nog geen voorstellen. Dien een intent in zodat Leon eerst een plan maakt.</p></div>`;
      }
      return proposals.slice(0, 8).map(item => {
        let proposal = {};
        try { proposal = JSON.parse(item.proposal_json || "{}"); } catch (_) {}
        const tasks = proposal.proposed_tasks || [];
        const approvals = proposal.proposed_approvals || [];
        const safety = proposal.safety_notes || [];
        return `
          <div class="item">
            <div class="item-head">
              <div>
                <h3>${esc(item.route)} · ${esc(item.status)}</h3>
                <p class="small">${esc(item.summary)}</p>
              </div>
              <span class="tag">${Number(item.execution_allowed) ? "exec allowed" : "proposal only"}</span>
            </div>
            <p class="small muted">Next: ${esc(item.recommended_next_step)} · tasks: ${tasks.length} · approvals: ${approvals.length}</p>
            ${tasks[0] ? `<p class="small">Plan: ${esc(tasks[0].goal || tasks[0].title)}</p>` : ""}
            ${approvals[0] ? `<p class="small notice">Approval needed before execution: ${esc(approvals[0].reason || approvals[0].summary)}</p>` : ""}
            ${proposal.safe_response ? `<p class="small notice">${esc(proposal.safe_response)}</p>` : ""}
            ${safety.length ? `<p class="small muted">${esc(safety[0])}</p>` : ""}
            ${item.status === "prepared" ? `
              <div style="height:10px"></div>
              <div style="display:flex; gap:8px; flex-wrap:wrap">
                <button type="button" onclick="applyOrchestration('${esc(item.id)}')">Apply proposal</button>
                <button type="button" onclick="rejectOrchestration('${esc(item.id)}')">Reject proposal</button>
              </div>
            ` : `<p class="small muted">Review: ${esc(item.review_note || "—")}</p>`}
          </div>
        `;
      }).join("");
    }

    function renderSpaceCanvas(state) {
      const shell = state.leon_canvas_shell || {};
      const spaces = shell.spaces || [];
      if (!spaces.length) return;
      if (!spaces.some(space => space.id === activeCanvasSpace)) activeCanvasSpace = spaces[0].id;
      const activeSpace = spaces.find(space => space.id === activeCanvasSpace) || spaces[0];
      const activeSignal = spaceSignal(activeSpace.id, state);
      setDockFromContract(state);
      updateDockActive(activeSpace.id);
      document.getElementById("shellSpaceTitle").textContent = activeSpace.id === "home" ? "Leon workspace" : `${activeSpace.label} canvas`;
      document.getElementById("shellSpacePurpose").textContent = activeSpace.id === "home" ? "Een rustige start voor intent, aandacht en de eerstvolgende stap." : (activeSpace.purpose || "Connected Leon space.");
      document.getElementById("shellMode").textContent = activeSpace.id === "home" ? "Leon" : activeSpace.label;
      document.getElementById("shellNextAction").textContent = activeSignal.next;
      document.getElementById("shellAttention").textContent = activeSignal.attention;
      document.getElementById("shellMemory").textContent = activeSignal.detail;
      setPanelMode(activeSpace.id === "home" ? "merged" : "split");
      const canvas = document.getElementById("spaceCanvas");
      canvas.classList.toggle("home-focus", activeSpace.id === "home");
      canvas.classList.toggle("task-detail-space", activeSpace.id === "workflows");
      canvas.classList.toggle("settings-inspect-space", activeSpace.id === "settings");
      if (activeSpace.id === "home") {
        canvas.innerHTML = renderHomeFocusCanvas(state, activeSignal);
        return;
      }
      if (activeSpace.id === "workflows") {
        canvas.innerHTML = renderTasksCanvas(state);
        return;
      }
      if (activeSpace.id === "chat") {
        canvas.innerHTML = renderProposalCanvas(state);
        return;
      }
      if (activeSpace.id === "settings") {
        canvas.innerHTML = renderSettingsInspectCanvas(state);
        return;
      }
      canvas.innerHTML = spaces.map(space => {
        const position = space.position || {};
        const chips = (space.approved_components || []).slice(0, 3);
        const style = `grid-column:${Number(position.x || 0) + 1} / span ${Number(position.w || 1)}; grid-row:${Number(position.y || 0) + 1} / span ${Number(position.h || 1)};`;
        return `
          <button type="button" class="space-node ${space.id === activeSpace.id ? "active" : ""}" style="${style}" data-space-node="${esc(space.id)}" data-expand-card="space" data-motion-key="space-${esc(space.id)}">
            <span>
              <strong>${esc(space.label)}</strong>
              <span class="small"> · ${(space.connected_to || []).map(item => esc(item)).join(" / ")}</span>
            </span>
            <span class="component-strip">
              ${chips.map(component => `<span class="component-chip">${esc(component)}</span>`).join("")}
            </span>
          </button>
        `;
      }).join("");
      document.querySelectorAll(".space-node[data-space-node]").forEach(button => {
        button.addEventListener("click", () => {
          if (button.dataset.spaceNode === activeCanvasSpace) {
            openDetailWindow(button);
            return;
          }
          setCanvasSpace(button.dataset.spaceNode, { scroll: false });
        });
      });
      applyMagneticMotion(activeSpace.id);
    }

    function renderMorningBrief(briefState) {
      const brief = briefState.generated || briefState.latest_night_run?.morning_brief || {};
      const sections = brief.sections || [];
      const details = brief.inspectors || brief.expandable_details || [];
      const partial = briefState.partial_failure_summary || brief.partial_failure_disclosure || {};
      const partialItems = partial.items || [];
      const target = document.getElementById("morningBrief");
      if (!sections.length) {
        target.innerHTML = `<div class="item"><p class="small muted">Nog geen morning brief. Start een night run of genereer de laatste brief handmatig.</p></div>`;
        return;
      }
      const partialHtml = partial.has_partial_failure || Number(partial.count || partial.failure_count || 0) ? `
        <div class="item">
          <div class="item-head">
            <div>
              <h3>Partial failure visible</h3>
              <p class="small">${esc(partial.count || partial.failure_count || 0)} failure(s) need review or recovery.</p>
            </div>
            <span class="tag">attention</span>
          </div>
          ${partialItems.length ? `<pre>${esc(compactJson(partialItems))}</pre>` : `<pre>${esc(compactJson(partial.recovery_suggestions || []))}</pre>`}
        </div>
      ` : "";
      target.innerHTML = partialHtml + sections.map(section => `
        <div class="item">
          <div class="item-head">
            <div>
              <h3>${esc(section.title)}</h3>
              <p class="small">${esc(section.summary || "Geen samenvatting.")}</p>
            </div>
            <span class="tag">${section.details_collapsed === false ? "open" : "collapsed"}</span>
          </div>
          <pre>${esc(compactJson(section.items))}</pre>
          <details>
            <summary>Inspecteer bronnen, modellen, kosten, prompts/samenvattingen, logs, diffs, graph, policy en rollback</summary>
            ${details.map(group => `
              <details>
                <summary>${esc(group.title)}</summary>
                <pre>${esc(compactJson(group.content))}</pre>
              </details>
            `).join("")}
          </details>
        </div>
      `).join("");
    }

    function render(state) {
      const previousBounds = captureMotionBounds();
      currentState = state;
      const uiPolicy = state.ui_composition_policy || {};
      const uiPreview = state.ui_composition_preview || {};
      const character = state.leon_character || {};
      const productShell = uiPolicy.product_shell || {};
      const statusColors = productShell.status_colors || {};
      const statusKey = shellStatusKey(state);
      const accent = character.color || statusColors[statusKey]?.color || productShell.dynamic_accent?.fallback || "#62a8ff";
      const animationTiming = state.leon_canvas_shell?.animation_system?.timing || {};
      document.documentElement.style.setProperty("--accent", accent);
      document.documentElement.style.setProperty("--motion-standard", `${Number(animationTiming.standard_ms || 260)}ms`);
      document.documentElement.style.setProperty("--motion-emphasis", `${Number(animationTiming.emphasis_ms || 360)}ms`);
      document.documentElement.style.setProperty("--motion-ease", animationTiming.easing || "cubic-bezier(0.2, 0.8, 0.2, 1)");
      document.getElementById("shellDot").style.background = accent;
      document.getElementById("shellStatus").textContent = `${statusColors[statusKey]?.label || statusKey} · ${state.runtime.server_time}`;
      const characterNode = document.getElementById("leonCharacter");
      if (characterNode) characterNode.dataset.state = character.id || "idle";
      document.getElementById("shellPresenceTitle").textContent = character.label ? `Leon · ${character.label}` : (uiPreview.assistant_state?.label || "Leon is beschikbaar");
      document.getElementById("shellPresenceText").textContent = character.reason || uiPreview.assistant_state?.description || "Leon wacht op intent, context of review.";
      const targetText = character.active_component
        ? `${character.active_space || "home"} · ${character.active_component}${character.active_component_label ? ` · ${character.active_component_label}` : ""}`
        : "";
      document.getElementById("shellPresenceTarget").textContent = targetText;
      renderSpaceCanvas(state);
      playLayoutContinuity(previousBounds);
      document.getElementById("runStatus").textContent = `${state.metadata.status} · ${state.runtime.server_time}`;
      document.getElementById("phaseMetric").textContent = state.metadata.current_phase;
      document.getElementById("phaseText").textContent = state.metadata.summary;
      document.getElementById("progressBar").style.width = `${pct(state.metadata.progress_percent)}%`;

      const approvals = state.approvals.filter(a => a.status === "pending");
      document.getElementById("approvalMetric").textContent = approvals.length;
      const presentEnv = state.required_env.filter(e => e.present).length;
      document.getElementById("envMetric").textContent = `${presentEnv}/${state.required_env.length}`;
      renderMorningBrief(state.morning_brief || {});

      const modelPolicy = state.model_policy || {};
      const cloudModels = modelPolicy.cloud_models || {};
      const localGpu = modelPolicy.local_gpu || {};
      const localGpuValidation = localGpu.validation || {};
      const localGpuChecks = Array.isArray(localGpuValidation.checks) ? localGpuValidation.checks : [];
      document.getElementById("modelPolicy").innerHTML = Object.entries(cloudModels).map(([route, config]) => `
        <div class="item">
          <div class="item-head">
            <div>
              <h3>${esc(route)} · ${esc(config.model)}</h3>
              <p class="small">${esc((config.use_for || []).join(", "))}</p>
            </div>
            <span class="tag">${esc(config.reasoning_effort)} · ${esc(config.relative_cost || "unknown cost")}</span>
          </div>
          <p class="small muted">Estimate: ${esc(modelPolicy.cost_policy?.currency || "USD")} ${esc(config.default_run_estimate?.estimated_min ?? "—")}-${esc(config.default_run_estimate?.estimated_max ?? "—")} per bounded run</p>
          ${route === "premium" ? `<p class="small attention">Premium route: visible cost warning required before execution.</p>` : ""}
        </div>
      `).join("") + `
        <div class="item">
          <div class="item-head">
            <div>
              <h3>local_gpu · ${localGpuValidation.route_allowed ? "validated" : "blocked"}</h3>
              <p class="small">${esc(localGpu.policy || "GPU route not configured yet.")}</p>
            </div>
            <span class="tag">${esc(localGpuValidation.status || localGpu.readiness_status || "not_validated")}</span>
          </div>
          <p class="small muted">Enabled: ${localGpu.enabled ? "yes" : "no"} · Backend: ${esc(localGpu.selected_backend || "—")} · Model: ${esc(localGpu.selected_model || "—")}</p>
          <p class="small attention">${esc(((localGpuValidation.routing_gate || {}).reasons || ["Local GPU validation has not passed."]).join(" "))}</p>
          ${localGpuChecks.map(check => `
            <p class="small muted">${esc(check.title || check.id)}: ${esc(check.status || "not_run")} · ${esc(check.summary || "")}</p>
          `).join("")}
        </div>
      `;

      const registry = uiPolicy.component_registry || {};
      const spaces = uiPolicy.spaces || {};
      document.getElementById("uiCompositionPreview").innerHTML = `
        <div class="item">
          <div class="item-head">
            <div>
              <h3>${esc(uiPreview.space || "home")} · ${esc(uiPreview.assistant_state?.label || "status onbekend")}</h3>
              <p class="small">${esc(uiPolicy.principle || "Component composition policy not loaded.")}</p>
            </div>
            <span class="tag">${esc(uiPreview.status || "preview_only")}</span>
          </div>
          <p class="small muted">Components: ${esc((uiPreview.component_ids || []).join(", ") || "—")}</p>
          <p class="small muted">Assistant: ${esc(uiPreview.assistant_state?.description || "—")} · motion: ${esc(uiPreview.assistant_state?.motion || "none")}</p>
          <p class="small ${uiPreview.friction_required ? "notice" : "ok"}">Friction required: ${uiPreview.friction_required ? "ja" : "nee"} · Missing component protocol: ${uiPreview.missing_component_protocol ? "ja" : "nee"} · Execution allowed: ${uiPreview.execution_allowed ? "ja" : "nee"}</p>
          <p class="small muted">Safety: ${esc((uiPreview.safety_notes || []).join(" ") || (uiPreview.safety_invariants || []).slice(0, 3).join(" · "))}</p>
        </div>
        <div class="item">
          <div class="item-head">
            <h3>Spaces</h3>
            <span class="tag">${esc(Object.keys(spaces).length)}</span>
          </div>
          <p class="small muted">${esc(Object.entries(spaces).map(([id, space]) => `${id}: ${(space.primary_components || []).slice(0, 3).join("/")}`).join(" · "))}</p>
        </div>
        <div class="item">
          <div class="item-head">
            <h3>Component DNA registry</h3>
            <span class="tag">${esc(Object.keys(registry).length)}</span>
          </div>
          <p class="small muted">${esc(Object.keys(registry).slice(0, 18).join(", "))}${Object.keys(registry).length > 18 ? "…" : ""}</p>
        </div>
      `;

      const toolSelect = document.getElementById("toolCheckId");
      const previousTool = toolSelect.value;
      toolSelect.innerHTML = (state.tool_manifests || []).map(item => `<option value="${esc(item.tool_id)}">${esc(item.tool_id)}</option>`).join("");
      if ([...toolSelect.options].some(o => o.value === previousTool)) toolSelect.value = previousTool;

      const adoption = state.tool_adoption_shortlist || { items: [], lanes: {} };
      const laneLabels = {
        evaluate_now: "Evaluate now",
        sandbox_later: "Sandbox later",
        hold: "Hold",
        reject: "Reject"
      };
      document.getElementById("toolAdoptionShortlist").innerHTML = ["evaluate_now", "sandbox_later", "hold", "reject"].map(lane => {
        const laneItems = (adoption.items || []).filter(item => item.lane === lane);
        if (!laneItems.length) return "";
        return `
          <div class="item">
            <div class="item-head">
              <h3>${esc(laneLabels[lane] || lane)}</h3>
              <span class="tag">${laneItems.length}</span>
            </div>
            <div class="list" style="margin-top:10px">
              ${laneItems.map(item => `
                <div class="item">
                  <div class="item-head">
                    <div>
                      <h3>${esc(item.name)} · ${esc(item.score)}/100</h3>
                      <p class="small">${esc(item.next_task)}</p>
                    </div>
                    <span class="tag">${esc(item.evidence_level)}</span>
                  </div>
                  <p class="small muted">Status: ${esc(item.status)} unchanged · Risk: ${esc(item.risk_level)} · Resource: ${esc(item.resource_profile)} · Cost: ${esc(item.cost_profile)}</p>
                  <p class="small muted">Source: ${item.source_url ? `<a href="${esc(item.source_url)}" target="_blank" rel="noreferrer">${esc(item.source_url)}</a>` : "—"}</p>
                  <p class="small muted">Why: ${esc((item.lane_reason || []).join(", ") || "—")}</p>
                  <p class="small muted">Read scopes: ${esc((item.read_scopes || []).join(", ") || "—")}</p>
                  <p class="small muted">Write scopes: ${esc((item.write_scopes || []).join(", ") || "geen")}</p>
                  <p class="small muted">Env keys: ${esc((item.required_env_keys || []).join(", ") || "geen")} · Sandbox: ${item.sandbox_required ? "ja" : "nee"}</p>
                  <p class="small muted">Approval required for: ${esc((item.approval_required_for || []).join(", ") || "—")}</p>
                  <p class="small muted">Allowed without approval: ${esc((item.allowed_without_approval || []).join(", ") || "—")}</p>
                  <p class="small muted">Forbidden: ${esc((item.forbidden_actions || []).join(", ") || "—")}</p>
                  <p class="small notice">No approval granted · geen install/connect/write/resource-heavy/spend-money uitvoering.</p>
                  ${item.blockers?.length ? `<p class="small notice">Blockers: ${esc(item.blockers.join(", "))}</p>` : ""}
                  ${(item.write_scope_count || 0) > 0 || (item.external_effects || []).length ? `<p class="small danger">Niet uitvoerbaar tot approved status + passende consumed approval + runtime permission check.</p>` : ""}
                </div>
              `).join("")}
            </div>
          </div>
        `;
      }).join("") || `<div class="item"><p class="small muted">Geen shortlist beschikbaar.</p></div>`;

      const reviewPackets = state.tool_review_packets || { packets: [] };
      const tasksByTitle = Object.fromEntries((state.tasks || []).map(task => [task.title, task]));
      document.getElementById("toolReviewPackets").innerHTML = (reviewPackets.packets || []).map(packet => {
        const task = tasksByTitle[packet.recommended_task_title] || null;
        return `
          <div class="item">
            <div class="item-head">
              <div>
                <h3>${esc(packet.name)} · ${esc(packet.review_status)}</h3>
                <p class="small">${esc(packet.summary)}</p>
              </div>
              <span class="tag">${esc(packet.scope)}</span>
            </div>
            <p class="small muted">License: ${esc(packet.license_status)} · Score: ${esc(packet.evidence?.score ?? "—")} · Evidence: ${esc(packet.evidence?.evidence_level || "—")}</p>
            <p class="small muted">Required checks: ${esc((packet.required_checks || []).join(", "))}</p>
            <p class="small muted">Decision options: ${esc((packet.decision_options || []).join(", "))}</p>
            <p class="small muted">Approval gates: ${esc((packet.permission_review?.approval_required_for || []).join(", ") || "—")}</p>
            ${task ? `<p class="small muted">Review task: ${esc(task.status)} · ${esc(task.owner)} · ${esc(task.id)}</p>` : `<p class="small muted">Review task: nog niet aangemaakt</p>`}
            ${task?.result ? `<p class="small ok">Review result: ${esc(task.result)}</p>` : ""}
            ${task?.verification_note ? `<p class="small muted">Verification: ${esc(task.verification_note)}</p>` : ""}
            <p class="small notice">Review only · no approval granted · status unchanged · execution allowed: ${packet.execution_allowed ? "ja" : "nee"}</p>
          </div>
        `;
      }).join("") || `<div class="item"><p class="small muted">Geen review packets beschikbaar.</p></div>`;

      document.getElementById("toolRegistry").innerHTML = (state.tool_manifests || []).map(item => {
        let manifest = {};
        try { manifest = JSON.parse(item.manifest_json || "{}"); } catch (_) {}
        const gh = manifest.github_metadata || {};
        const license = gh.license?.spdx_id || gh.license?.name || "—";
        return `
          <div class="item">
            <div class="item-head">
              <div>
                <h3>${esc(item.name)} · ${esc(item.status)}</h3>
                <p class="small">${esc(item.purpose || "Geen purpose gezet.")}</p>
              </div>
              <span class="tag">${esc(item.source_type)} · ${esc(item.risk_level)}</span>
            </div>
            <p class="small muted">Bron: ${item.source_url ? `<a href="${esc(item.source_url)}" target="_blank" rel="noreferrer">${esc(item.source_url)}</a>` : "—"}</p>
            <p class="small muted">Read: ${esc((manifest.read_scopes || []).join(", ") || "—")}</p>
            <p class="small muted">Write: ${esc((manifest.write_scopes || []).join(", ") || "—")}</p>
            <p class="small muted">Score: ${esc(item.candidate_score?.score ?? "—")}/100 · Advies: ${esc(item.candidate_score?.recommendation || "—")} · Bewijs: ${esc(item.candidate_score?.evidence_level || "—")}</p>
            ${gh.full_name ? `<p class="small muted">GitHub: ${esc(gh.full_name)} · ⭐ ${esc(gh.stargazers_count || 0)} · forks ${esc(gh.forks_count || 0)} · pushed ${esc(gh.pushed_at || "—")} · license ${esc(license)} · ${gh.archived ? "archived" : esc(gh.refresh_status || "fresh")}</p>` : `<p class="small muted">GitHub metadata: nog niet opgehaald</p>`}
            <p class="small muted">Env: ${esc((manifest.required_env_keys || []).join(", ") || "geen")} · Kosten: ${esc(item.cost_profile)} · Resource: ${esc(item.resource_profile)}</p>
            <p class="small muted">Approval nodig voor: ${esc((manifest.approval_required_for || []).join(", ") || "—")}</p>
            <p class="small muted">Forbidden: ${esc((manifest.forbidden_actions || []).join(", ") || "—")}</p>
            <p class="small muted">Next: ${esc((item.candidate_score?.next_actions || []).join(", ") || "—")}</p>
            ${item.candidate_score?.blockers?.length ? `<p class="small notice">Blockers: ${esc(item.candidate_score.blockers.join(", "))}</p>` : ""}
            <div style="height:10px"></div>
            <button type="button" onclick="scoreToolCandidate('${esc(item.tool_id)}')">Score opnieuw</button>
            ${String(item.source_url || "").includes("github.com/") ? `<button type="button" onclick="refreshGithubCandidate('${esc(item.tool_id)}')">GitHub refresh</button>` : ""}
            ${item.source_type === "mcp_server" ? `<button type="button" onclick="createMcpIntake('${esc(item.tool_id)}')">Maak MCP intake</button>` : ""}
          </div>
        `;
      }).join("") || `<div class="item"><p class="small muted">Nog geen tools geregistreerd.</p></div>`;

      document.getElementById("toolPermissionChecks").innerHTML = (state.tool_permission_checks || []).slice(0, 12).map(item => `
        <div class="item">
          <div class="item-head">
            <div>
              <h3>${esc(item.tool_id)} · ${esc(item.decision)}</h3>
              <p class="small">${esc(item.action_type)} · ${esc(item.requested_scope)}</p>
            </div>
            <span class="tag">${esc(item.risk_level)}</span>
          </div>
          <p class="small muted">${esc(item.reason)}</p>
          <p class="small muted">${esc(item.created_at)} · gate: ${esc(item.required_gate || "geen")} · approval: ${esc(item.approval_id || "—")}</p>
        </div>
      `).join("") || `<div class="item"><p class="small muted">Nog geen permission checks.</p></div>`;

      const evalLatest = state.routing_eval_latest_run || {};
      const evalImpact = evalLatest.impact || {};
      const evalCaseSummary = state.routing_eval_case_summary || {};
      document.getElementById("routingEvalSummary").innerHTML = `
        <div class="item">
          <div class="item-head">
            <div>
              <h3>Eval cases ${esc(evalCaseSummary.active || 0)} active · ${esc(evalCaseSummary.total || 0)} total</h3>
              <p class="small">Latest release: ${esc(evalLatest.release_label || "not recorded")}</p>
            </div>
            <span class="tag">${esc(evalLatest.passed ?? "—")}/${esc(evalLatest.total ?? "—")}</span>
          </div>
          <p class="small muted">Accuracy: ${esc(evalLatest.accuracy ?? "—")} · Safety failures: ${esc(evalLatest.safety_failures ?? "—")} · Safety OK: ${Number(evalLatest.safety_ok ?? 1) ? "yes" : "no"}</p>
          <p class="small muted">Impact: ${esc(evalImpact.summary || "No release comparison yet.")}</p>
        </div>
      `;

      document.getElementById("routingDecisions").innerHTML = (state.routing_decisions || []).map(item => {
        let detail = {};
        try { detail = JSON.parse(item.decision_json || "{}"); } catch (_) {}
        const routeDetail = detail.model_route || {};
        const routeWarning = routeDetail.cost_warning || {};
        const estimate = routeDetail.estimated_cost || {};
        const expected = detail.expected_output || {};
        const band = detail.value_band || {};
        const executionPath = detail.execution_path || {};
        const retrievedContext = detail.retrieved_context || {};
        const evidence = item.decision_evidence || {};
        const outcome = item.outcome || evidence.outcome || detail.outcome || {};
        const feedback = item.feedback_summary || {};
        const feedbackCounts = feedback.counts || {};
        const scoreInputs = detail.value_score_inputs?.components || {};
        const scoreReason = Object.entries(scoreInputs).map(([key, value]) => `${key}: ${value.points ?? 0}`).join(" · ");
        const contextRefs = (retrievedContext.source_refs || []).map(ref => ref.source_ref || ref.source || ref.id).filter(Boolean).join(", ");
        const feedbackReason = Object.entries(feedbackCounts).filter(([, count]) => Number(count) > 0).map(([key, count]) => `${key}: ${count}`).join(" · ");
        return `
          <div class="item">
            <div class="item-head">
              <div>
                <h3>${esc(item.route)} · ${esc(item.intent)}</h3>
                <p class="small">${esc(item.input_text_redacted)}</p>
              </div>
              <span class="tag">${esc(item.model_route)} · ${esc(item.model)}</span>
            </div>
            <p class="small muted">Risico: ${esc(item.risk_level)} · Complexiteit: ${esc(item.complexity)} · Waarde: ${esc(item.value_score)} · Band: ${esc(band.label || band.handling || "—")} · Confidence: ${esc(Number(item.confidence || 0).toFixed(2))}</p>
            <p class="small muted">Approval: ${Number(item.approval_required) ? "ja" : "nee"} · Effect: ${esc(item.external_effect)} · Statusadvies: ${esc(item.recommended_task_status || "none")}</p>
            <p class="small muted">Evidence: ${esc(evidence.evidence_ref || `routing_decisions:${item.id}`)} · Outcome: ${esc(outcome.status || "recorded")} · ${esc(outcome.summary || "Decision recorded.")}</p>
            <p class="small muted">Feedback: ${esc(feedbackReason || "nog geen")} · Latest: ${esc(feedback.latest?.feedback_type || "—")}</p>
            <p class="small muted">Execution path: ${esc(executionPath.type || "—")} · Next: ${esc(executionPath.next_step || "—")} · Agent: ${esc(executionPath.agent_role || "—")}</p>
            <p class="small muted">Value reason: ${esc(band.reason || "—")}</p>
            <p class="small muted">Score inputs: ${esc(scoreReason || "—")}</p>
            ${retrievedContext.applied ? `<p class="small muted">Memory context: ${esc(retrievedContext.match_count || 0)} match(es) · relevance ${esc(retrievedContext.relevance_score ?? "—")} · refs: ${esc(contextRefs || "—")}</p>` : ""}
            <p class="small muted">Tools: ${esc((detail.required_tools || []).join(", ") || "geen")} · Verwachte output: ${esc(expected.type || "—")}</p>
            ${detail.clarification_required ? `<p class="small attention">Clarification: ${esc((detail.clarification_questions || []).join(" "))}</p>` : ""}
            <p class="small muted">Reden: ${esc((detail.reasons || []).join(" "))}</p>
            <p class="small muted">Model reason: ${esc(routeDetail.user_visible_reason || item.model_reason || "—")} · Estimate: ${esc(estimate.currency || "USD")} ${esc(estimate.estimated_min ?? "—")}-${esc(estimate.estimated_max ?? "—")}</p>
            ${renderModelRouteDecision(routeDetail)}
            ${routeWarning.required ? `<p class="small attention">${esc(routeWarning.message || "Premium/expensive route requires cost review.")}</p>` : ""}
            <div style="height:10px"></div>
            <button type="button" onclick="proposeOrchestration('${esc(item.id)}')">Maak proposal</button>
            <button type="button" onclick="markDecisionFeedback('${esc(item.id)}', 'useful')">Useful</button>
            <button type="button" onclick="markDecisionFeedback('${esc(item.id)}', 'wrong')">Wrong</button>
            <button type="button" onclick="markDecisionFeedback('${esc(item.id)}', 'risky')">Risky</button>
            <button type="button" onclick="markDecisionFeedback('${esc(item.id)}', 'low_value')">Low-value</button>
            <button type="button" onclick="promoteDecisionToEvalCase('${esc(item.id)}')">Eval case</button>
          </div>
        `;
      }).join("");

      document.getElementById("plannerPreviews").innerHTML = (state.planner_previews || []).map(item => {
        let preview = {};
        try { preview = JSON.parse(item.preview_json || "{}"); } catch (_) {}
        return `
          <div class="item">
            <div class="item-head">
              <div>
                <h3>${esc(item.decision)} · ${esc(preview.policy || "preview")}</h3>
                <p class="small">${esc(preview.request || "Sample planner preview")}</p>
              </div>
              <span class="tag">${Number(item.execution_allowed) ? "exec allowed" : "preview only"}</span>
            </div>
            <p class="small muted">Events: ${esc(preview.input_summary?.event_count ?? "—")} · mails: ${esc(preview.input_summary?.email_count ?? "—")} · conflicts: ${esc((preview.conflicts || []).length)} · free slots: ${esc((preview.free_slots || []).length)} · proposals: ${esc((preview.proposals || []).length)}</p>
            <p class="small muted">External calls: ${Number(item.external_calls_made) ? "ja" : "nee"} · accounts connected: ${Number(item.accounts_connected) ? "ja" : "nee"} · writes: ${Number(item.write_allowed_now) ? "ja" : "nee"} · secrets read: ${Number(item.secret_values_read) ? "ja" : "nee"}</p>
            ${preview.free_slots?.[0] ? `<p class="small ok">Eerste vrij slot: ${esc(preview.free_slots[0].start)} → ${esc(preview.free_slots[0].end)}</p>` : `<p class="small notice">Geen vrij slot gevonden in sample horizon.</p>`}
            ${preview.conflicts?.length ? `<p class="small notice">Conflict: ${esc(preview.conflicts.map(c => `${c.titles?.join(" ↔ ")} (${c.overlap_start})`).join("; "))}</p>` : ""}
            ${preview.proposals?.length ? `<p class="small muted">Proposal: ${esc(preview.proposals.map(p => `${p.title} ${p.start} → ${p.end}`).join("; "))}</p>` : ""}
            <p class="small notice">Denied: ${esc((preview.denied_actions || []).join(", ") || "external actions")}</p>
          </div>
        `;
      }).join("") || `<div class="item"><p class="small muted">Nog geen planner previews.</p></div>`;

      const retrievalMetrics = state.memory_retrieval_metrics || {};
      document.getElementById("memoryRetrievalQueries").innerHTML = `
        <div class="item">
          <p class="small muted">V1 metrics: ${esc(retrievalMetrics.query_count || 0)} query(s) · success ${esc(Number(retrievalMetrics.success_rate || 0).toFixed(2))} · avg latency ${esc(retrievalMetrics.average_latency_ms || 0)}ms · avg relevance ${esc(Number(retrievalMetrics.average_relevance_score || 0).toFixed(2))}</p>
        </div>
        ${(state.memory_retrieval_queries || []).map(item => `
          <div class="item">
            <div class="item-head">
              <div>
                <h3>${esc(item.scope)} · ${esc(item.answer_status)}</h3>
                <p class="small">${esc(item.query_redacted)}</p>
              </div>
              <span class="tag">${esc(Number(item.confidence || 0).toFixed(2))} confidence</span>
            </div>
            <p class="small">${esc(item.answer || "")}</p>
            <p class="small muted">Latency: ${esc(item.latency_ms)}ms · relevance: ${esc(Number(item.relevance_score || 0).toFixed(2))} · matches: ${esc(item.match_count)} · memory/source: ${esc(item.memory_match_count)}/${esc(item.source_match_count)}</p>
            <p class="small muted">Sources: ${esc((item.source_refs || []).map(ref => ref.source_ref || ref.source || ref.id).filter(Boolean).join(", ") || "—")}</p>
            <p class="small muted">Graph entries: ${esc((item.related_graph_entries || []).map(entry => entry.relationship_type || entry.entity_type || entry.kind).slice(0, 8).join(", ") || "—")}</p>
            ${Number(item.conflict_count || 0) ? `<p class="small notice">Conflicting memories marked: ${esc((item.conflicts || []).map(conflict => `${conflict.memory_id}: ${conflict.conflict_note || conflict.conflict_status}`).join("; "))}</p>` : ""}
          </div>
        `).join("")}
      `;

      document.getElementById("memoryItems").innerHTML = (state.memory_items || []).map(item => `
        <div class="item">
          <div class="item-head">
            <div>
              <h3>${esc(item.memory_type)} · ${esc(item.status)}</h3>
              <p class="small">${esc(item.content)}</p>
            </div>
            <span class="tag">${esc(item.sensitivity)} · ${esc(item.privacy_level)}</span>
          </div>
          <p class="small muted">Source: ${esc(item.source || "—")} · confidence: ${esc(Number(item.confidence || 0).toFixed(2))} · expiry: ${esc(item.expires_at || "geen")}</p>
          <p class="small muted">Provenance: ${esc(item.provenance?.source || item.source || "—")} · created: ${esc(item.created_at || "—")} · updated: ${esc(item.updated_at || "—")}</p>
          <p class="small muted">Graph entities: ${esc((item.graph_entities || []).join(", ") || "—")} · correction of: ${esc(item.correction_of || "—")}</p>
          ${item.has_conflicts ? `<p class="small notice">Conflict: ${esc(item.conflict_note || "marked as conflicting")} · with ${esc((item.conflict_memory_ids || []).join(", ") || "unknown memory")}</p>` : ""}
          ${item.review_note ? `<p class="small muted">Review/correction note: ${esc(item.review_note)}</p>` : ""}
          <p class="small notice">Memory is lokaal en zichtbaar. Candidate/long-term/sensitive items worden niet stil als context gebruikt zonder review.</p>
          ${!["deleted", "scrubbed"].includes(item.status) ? `
            <div style="height:10px"></div>
            <div style="display:flex; gap:8px; flex-wrap:wrap">
              <button type="button" onclick="updateMemoryStatus('${esc(item.id)}', 'active')">Activeer</button>
              <button type="button" onclick="updateMemoryStatus('${esc(item.id)}', 'rejected')">Reject</button>
              <button type="button" onclick="lowerMemoryConfidence('${esc(item.id)}', ${Number(item.confidence || 0)})">Confidence omlaag</button>
              <button type="button" onclick="deleteMemory('${esc(item.id)}')">Vergeet</button>
              <button type="button" onclick="scrubMemory('${esc(item.id)}')">Scrub</button>
            </div>
          ` : `<p class="small muted">Terminal: ${esc(item.deleted_at || "—")} · content scrubbed</p>`}
        </div>
      `).join("") || `<div class="item"><p class="small muted">Nog geen memory items.</p></div>`;

      document.getElementById("memoryGraphEdges").innerHTML = (state.memory_graph_edges || []).map(edge => `
        <div class="item">
          <div class="item-head">
            <div>
              <h3>${esc(edge.subject)} — ${esc(edge.predicate)} — ${esc(edge.object)}</h3>
              <p class="small">Type: ${esc(edge.relationship_type || "related_to")} · Memory: ${esc(edge.source_memory_id)} · Source: ${esc(edge.source || "—")}</p>
            </div>
            <span class="tag">${esc(edge.status)} · ${esc(Number(edge.confidence || 0).toFixed(2))}</span>
          </div>
        </div>
      `).join("") || `<div class="item"><p class="small muted">Nog geen graph edges.</p></div>`;

      document.getElementById("phases").innerHTML = state.phases.map(phase => `
        <div class="item">
          <div class="item-head">
            <div>
              <h3>${esc(phase.title)}</h3>
              <p class="small">${esc(phase.goal)}</p>
            </div>
            <span class="tag">${esc(phase.status)}</span>
          </div>
        </div>
      `).join("");

      document.getElementById("tasks").innerHTML = state.tasks.map(task => renderTaskDetailCard(task)).join("");

      document.getElementById("approvals").innerHTML = state.approvals.map(item => `
        <div class="item">
          <div class="item-head">
            <h3>${esc(item.title)}</h3>
            <span class="tag">${esc(item.status)}</span>
          </div>
          <p class="small">${esc(item.reason)}</p>
          <p class="small muted">Expected change: ${esc(item.expected_change || item.summary || "—")}</p>
          <p class="small muted">Risico: ${esc(item.risk_class || item.risk_level || "medium")} · Scope: ${esc(item.permissions || "—")} · Kosten: ${esc(item.cost_estimate || "—")}</p>
          <p class="small muted">Rollback: ${esc(item.rollback_plan || "—")}</p>
          <p class="small muted">Failure mode: ${esc(item.failure_mode || "—")}</p>
          ${item.status === "pending" ? `
            <div style="height:10px"></div>
            <div style="display:flex; gap:8px; flex-wrap:wrap">
              <button type="button" onclick="decide('${esc(item.id)}', 'approved')">Goedkeuren</button>
              <button type="button" onclick="decide('${esc(item.id)}', 'expired')">Expire</button>
              <button type="button" onclick="decide('${esc(item.id)}', 'rejected')">Afwijzen</button>
            </div>
          ` : item.status === "approved" ? `
            <p class="small ok">Goedgekeurd: klaar om eenmalig te consumeren voor voortzetting.</p>
            <div style="height:10px"></div>
            <div style="display:flex; gap:8px; flex-wrap:wrap">
              <button type="button" onclick="continueAfterApproval('${esc(item.id)}')">Continue after approval</button>
              <button type="button" onclick="decide('${esc(item.id)}', 'rejected')">Afwijzen</button>
            </div>
          ` : `<p class="small muted">Besloten: ${esc(item.decided_at || item.consumed_at || "onbekend")}</p>`}
          ${renderTransparency(item.transparency)}
        </div>
      `).join("");

      const keySelect = document.getElementById("secretKey");
      const previous = keySelect.value;
      keySelect.innerHTML = state.required_env.map(item => `<option value="${esc(item.key)}">${esc(item.key)}</option>`).join("");
      if ([...keySelect.options].some(o => o.value === previous)) keySelect.value = previous;

      document.getElementById("envList").innerHTML = state.required_env.map(item => `
        <div class="item">
          <div class="item-head">
            <h3>${esc(item.key)}</h3>
            <span class="${item.present ? "ok" : "notice"}">${item.present ? "aanwezig" : "ontbreekt"}</span>
          </div>
          <p class="small">${esc(item.purpose)}</p>
        </div>
      `).join("");

      document.getElementById("rules").textContent = state.engineering_rules.map(r => `- ${r}`).join("\\n");

      document.getElementById("auditLog").innerHTML = (state.audit_events || []).map(event => `
        <div class="item">
          <div class="item-head">
            <div>
              <h3>#${esc(event.sequence)} · ${esc(event.event_type)}</h3>
              <p class="small">${esc(event.summary)}</p>
            </div>
            <span class="tag">${esc(event.risk_level)}</span>
          </div>
          <p class="small muted">${esc(event.timestamp)} · ${esc(event.actor_type)}:${esc(event.actor_id)}</p>
          <p class="small muted">hash ${esc((event.event_hash || "").slice(0, 12))} · prev ${esc((event.prev_hash || "").slice(0, 12))}</p>
        </div>
      `).join("");

      document.getElementById("sourceRecords").innerHTML = (state.source_records || []).map(item => {
        const view = item.default_view || item.transparency?.default_view || {};
        const attention = view.risk_or_attention_signals || [];
        return `
          <div class="item">
            <div class="item-head">
              <div>
                <h3>${esc(item.title || item.id)} · ${esc(item.status)}</h3>
                <p class="small">${esc(view.final_result || item.content_excerpt || "Geen excerpt beschikbaar.")}</p>
              </div>
              <span class="tag">${esc(item.source_type)} · ${esc(item.content_bytes || 0)} bytes</span>
            </div>
            <p class="small muted">Ref: ${esc(item.source_ref || "—")} · hash: ${esc((item.content_hash || "").slice(0, 16) || "—")} · updated: ${esc(item.updated_at || "—")}</p>
            ${attention.length ? `<p class="small notice">Attention: ${esc(attention.join(" · "))}</p>` : ""}
            ${renderTransparency(item.transparency)}
          </div>
        `;
      }).join("") || `<div class="item"><p class="small muted">Nog geen source records.</p></div>`;

      document.getElementById("orchestrationProposals").innerHTML = (state.orchestration_proposals || []).map(item => {
        let proposal = {};
        try { proposal = JSON.parse(item.proposal_json || "{}"); } catch (_) {}
        const tasks = proposal.proposed_tasks || [];
        const approvals = proposal.proposed_approvals || [];
        const band = proposal.value_band || {};
        return `
          <div class="item">
            <div class="item-head">
              <div>
                <h3>${esc(item.route)} · ${esc(item.status)}</h3>
                <p class="small">${esc(item.summary)}</p>
              </div>
              <span class="tag">${Number(item.execution_allowed) ? "exec allowed" : "no execution"}</span>
            </div>
            <p class="small muted">Next: ${esc(item.recommended_next_step)} · value: ${esc(proposal.decision_value_score ?? "—")} · band: ${esc(band.label || band.handling || "—")} · tasks: ${tasks.length} · approvals: ${approvals.length}</p>
            ${band.reason ? `<p class="small muted">Value reason: ${esc(band.reason)}</p>` : ""}
            <p class="small muted">External calls: ${proposal.external_calls_made ? "ja" : "nee"} · secrets read: ${proposal.secret_values_read ? "ja" : "nee"}</p>
            ${item.applied_task_id ? `<p class="small ok">Task: ${esc(item.applied_task_id)}</p>` : ""}
            ${item.applied_approval_id ? `<p class="small ok">Approval: ${esc(item.applied_approval_id)}</p>` : ""}
            ${proposal.safe_response ? `<p class="small notice">${esc(proposal.safe_response)}</p>` : ""}
            ${item.status === "prepared" ? `
              <div style="height:10px"></div>
              <div style="display:flex; gap:8px; flex-wrap:wrap">
                <button type="button" onclick="applyOrchestration('${esc(item.id)}')">Apply proposal</button>
                <button type="button" onclick="rejectOrchestration('${esc(item.id)}')">Reject proposal</button>
              </div>
            ` : `<p class="small muted">Review: ${esc(item.review_note || "—")}</p>`}
          </div>
        `;
      }).join("");

      document.getElementById("agentAssignmentProposals").innerHTML = (state.agent_assignment_proposals || []).map(item => {
        let proposal = {};
        try { proposal = JSON.parse(item.proposal_json || "{}"); } catch (_) {}
        const modelRoute = proposal.model_route || {};
        return `
          <div class="item">
            <div class="item-head">
              <div>
                <h3>${esc(item.agent_role)} · ${esc(item.status)}</h3>
                <p class="small">Task: ${esc(item.task_id)} · ${esc(item.runner_kind)} · ${esc(item.execution_mode)}</p>
              </div>
              <span class="tag">${esc(item.route)} · ${esc(item.model)}</span>
            </div>
            <p class="small muted">Type: ${esc(item.task_type)} · Risk: ${esc(item.risk)} · External calls allowed: ${Number(item.external_calls_allowed) ? "ja" : "nee"} · Secrets read: ${Number(item.secret_values_read) ? "ja" : "nee"}</p>
            <p class="small muted">Shell: ${Number(item.shell_commands_allowed) ? "ja" : "nee"} · File writes: ${Number(item.file_writes_allowed) ? "ja" : "nee"}</p>
            ${renderModelRouteDecision(modelRoute)}
            <p class="small muted">Allowed: ${esc(item.allowed_actions_json)}</p>
            <p class="small muted">Forbidden: ${esc(item.forbidden_actions_json)}</p>
            ${item.applied_agent_run_id ? `<p class="small ok">Agent run: ${esc(item.applied_agent_run_id)}</p>` : ""}
            ${item.status === "prepared" ? `
              <div style="height:10px"></div>
              <div style="display:flex; gap:8px; flex-wrap:wrap">
                <button type="button" onclick="applyAgentAssignment('${esc(item.id)}')">Apply assignment</button>
                <button type="button" onclick="rejectAgentAssignment('${esc(item.id)}')">Reject assignment</button>
              </div>
            ` : `<p class="small muted">Review: ${esc(item.review_note || "—")}</p>`}
          </div>
        `;
      }).join("");

      document.getElementById("providerDryRuns").innerHTML = (state.provider_dry_runs || []).map(item => {
        let dryRun = {};
        try { dryRun = JSON.parse(item.dry_run_json || "{}"); } catch (_) {}
        return `
          <div class="item">
            <div class="item-head">
              <div>
                <h3>${esc(item.provider_id)} · ${esc(item.status)}</h3>
                <p class="small">Task: ${esc(item.task_id)} · assignment: ${esc(item.agent_assignment_proposal_id || "—")}</p>
              </div>
              <span class="tag">${Number(item.execution_allowed) ? "exec allowed" : "no execution"}</span>
            </div>
            <p class="small muted">Env required: ${esc(item.required_env_keys_json)} · missing: ${esc(item.missing_env_keys_json)}</p>
            <p class="small muted">Provider calls: ${Number(item.provider_calls_made) ? "ja" : "nee"} · install: ${Number(item.dependency_installed) ? "ja" : "nee"} · SDK imported: ${Number(item.sdk_imported) ? "ja" : "nee"} · secrets read: ${Number(item.secret_values_read) ? "ja" : "nee"}</p>
            <p class="small notice">Plan only · approval consumed: ${Number(item.approval_consumed) ? "ja" : "nee"} · shell: ${Number(item.shell_commands_allowed) ? "ja" : "nee"} · file writes: ${Number(item.file_writes_allowed) ? "ja" : "nee"}</p>
            <p class="small muted">Next: ${esc(dryRun.recommended_next_step || "—")}</p>
          </div>
        `;
      }).join("") || `<div class="item"><p class="small muted">Nog geen provider dry-runs.</p></div>`;

      document.getElementById("mcpCandidateIntakes").innerHTML = (state.mcp_candidate_intakes || []).map(item => {
        let checklist = {};
        try { checklist = JSON.parse(item.checklist_json || "{}"); } catch (_) {}
        return `
          <div class="item">
            <div class="item-head">
              <div>
                <h3>${esc(item.tool_id)} · ${esc(item.status)}</h3>
                <p class="small">${esc(checklist.name || "")}</p>
              </div>
              <span class="tag">${Number(item.execution_allowed) ? "exec allowed" : "review only"}</span>
            </div>
            <p class="small muted">Decision: ${esc(item.decision)} · manifest status unchanged: ${Number(item.status_unchanged) ? "ja" : "nee"}</p>
            <p class="small muted">Install: ${Number(item.install_allowed_now) ? "ja" : "nee"} · connect: ${Number(item.connect_allowed_now) ? "ja" : "nee"} · write: ${Number(item.write_allowed_now) ? "ja" : "nee"} · approval granted: ${Number(item.no_approval_granted) ? "nee" : "ja"}</p>
            <p class="small muted">Gates: ${esc((checklist.review_gates || []).join(", ") || "—")}</p>
            <p class="small muted">Mappings: ${esc((checklist.tool_mappings || []).length)} · unknown tool default: ${esc(checklist.default_unknown_tool_decision || "—")}</p>
          </div>
        `;
      }).join("") || `<div class="item"><p class="small muted">Nog geen MCP intakes.</p></div>`;

      document.getElementById("agentRuns").innerHTML = (state.agent_runs || []).map(run => {
        const modelRoute = run.model_route || {};
        const risk = run.risk_assessment || {};
        const cost = run.cost_estimate || {};
        const projected = cost.projected_provider_call || cost.model_choice || {};
        const warning = cost.cost_warning || modelRoute.cost_warning || {};
        const reviewer = run.reviewer_result || {};
        const inputSources = run.input_sources || [];
        return `
          <div class="item">
            <div class="item-head">
              <div>
                <h3>${esc(run.role || run.agent_role)} · ${esc(run.status)}</h3>
                <p class="small">${esc(run.result_summary || (run.output || {}).summary || "Nog geen resultaat.")}</p>
              </div>
              <span class="tag">${esc(modelRoute.route || run.route)} · ${esc(modelRoute.model || run.model)}</span>
            </div>
            <p class="small muted">Task: ${esc((run.task || {}).title || run.task_id)} · type: ${esc(run.task_type)} · agent: ${esc(run.agent_role)}</p>
            <p class="small muted">Confidence: ${esc(run.confidence ?? "0")} · cost: ${esc(cost.estimation_status || "unknown")} · projected: ${esc(projected.currency || "USD")} ${esc(projected.estimated_min ?? "—")}-${esc(projected.estimated_max ?? "—")} · next: ${esc(run.next_action || "review_agent_run")}</p>
            <p class="small muted">Model reason: ${esc(modelRoute.user_visible_reason || modelRoute.reason || "—")}</p>
            ${renderModelRouteDecision(modelRoute)}
            ${warning.required ? `<p class="small attention">${esc(warning.message || "Premium/expensive route requires cost review.")}</p>` : ""}
            <p class="small muted">Risk: ${esc(risk.risk_class || "—")} · policy: ${esc(risk.decision || "—")} · reviewer: ${esc(reviewer.status || run.review_status)}</p>
            <p class="small muted">Input sources: ${esc(inputSources.length ? inputSources.join(", ") : "—")}</p>
            <p class="small muted">Allowed: ${esc(run.allowed_actions_json)}</p>
            <p class="small muted">Forbidden: ${esc(run.forbidden_actions_json)}</p>
            ${renderTransparency(run.transparency)}
            ${run.status === "waiting_for_review" ? `
              <div style="height:10px"></div>
              <div style="display:flex; gap:8px; flex-wrap:wrap">
                <button type="button" onclick="reviewAgentRun('${esc(run.id)}', 'accepted')">Accept</button>
                <button type="button" onclick="reviewAgentRun('${esc(run.id)}', 'changes_requested')">Changes</button>
                <button type="button" onclick="reviewAgentRun('${esc(run.id)}', 'rejected')">Reject</button>
              </div>
            ` : ""}
          </div>
        `;
      }).join("");
    }

    async function refresh() {
      render(await api("/api/state"));
    }

    async function requestMorningBrief() {
      const result = document.getElementById("morningBriefResult");
      result.textContent = "Brief genereren...";
      result.className = "small";
      try {
        const data = await api("/api/morning-brief/generate", { method: "POST", body: JSON.stringify({}) });
        result.textContent = `${data.morning_brief.run_id} gegenereerd met ${(data.morning_brief.sections || []).length} secties.`;
        result.className = "small ok";
        await refresh();
      } catch (error) {
        result.textContent = error.message;
        result.className = "small danger";
      }
    }

    document.getElementById("secretForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const key = document.getElementById("secretKey").value;
      const value = document.getElementById("secretValue").value;
      const result = document.getElementById("secretResult");
      result.textContent = "Opslaan…";
      result.className = "small";
      try {
        await api("/api/secrets", { method: "POST", body: JSON.stringify({ key, value }) });
        document.getElementById("secretValue").value = "";
        result.textContent = `${key} opgeslagen in .env.local. Waarde wordt niet getoond.`;
        result.className = "small ok";
        await refresh();
      } catch (error) {
        result.textContent = error.message;
        result.className = "small danger";
      }
    });

    document.getElementById("taskForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const title = document.getElementById("taskTitle").value;
      const goal = document.getElementById("taskGoal").value;
      const value_score = Number(document.getElementById("taskValue").value || 3);
      const parent_task_id = document.getElementById("taskParent").value.trim();
      const source_refs = document.getElementById("taskSources").value.split("\\n").map(item => item.trim()).filter(Boolean);
      await api("/api/tasks", { method: "POST", body: JSON.stringify({ title, goal, priority: "P1", risk_level: "medium", value_score, parent_task_id, source_refs }) });
      document.getElementById("taskTitle").value = "";
      document.getElementById("taskGoal").value = "";
      document.getElementById("taskValue").value = "3";
      document.getElementById("taskParent").value = "";
      document.getElementById("taskSources").value = "";
      await refresh();
    });

    document.getElementById("routingForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const text = document.getElementById("routingPrompt").value;
      const expected_route = document.getElementById("routingExpected").value;
      const result = document.getElementById("routingResult");
      result.textContent = "Routeren…";
      result.className = "small";
      try {
        const data = await api("/api/routing/decide", { method: "POST", body: JSON.stringify({ text, expected_route }) });
        const route = data.decision.route;
        const model = data.decision.model_route?.model || "unknown";
        const verdict = data.eval_pass === null ? "" : (data.eval_pass ? " · eval PASS" : " · eval FAIL");
        result.textContent = `${route} · ${model}${verdict}. Geen actie uitgevoerd.`;
        result.className = data.eval_pass === false ? "small danger" : "small ok";
        await refresh();
      } catch (error) {
        result.textContent = error.message;
        result.className = "small danger";
      }
    });

    document.getElementById("shellIntentForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const text = document.getElementById("shellIntent").value.trim();
      if (!text) return;
      document.getElementById("shellNextAction").textContent = "Voorstel wordt voorbereid...";
      try {
        const data = await api("/api/orchestration/propose", { method: "POST", body: JSON.stringify({ text }) });
        document.getElementById("routingPrompt").value = text;
        document.getElementById("shellIntent").value = "";
        activeCanvasSpace = "chat";
        document.getElementById("shellNextAction").textContent = `${data.proposal.route} proposal voorbereid. Geen actie uitgevoerd.`;
        await refresh();
      } catch (error) {
        document.getElementById("shellAttention").textContent = error.message;
      }
    });

    document.getElementById("uiComposeForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const result = document.getElementById("uiComposeResult");
      result.textContent = "Compositie preview maken…";
      result.className = "small";
      try {
        const data = await api("/api/ui/compose", {
          method: "POST",
          body: JSON.stringify({
            route: document.getElementById("uiRoute").value,
            task_status: document.getElementById("uiTaskStatus").value,
            risk_level: document.getElementById("uiRisk").value,
            component_need: document.getElementById("uiComponentNeed").value,
            requires_approval: document.getElementById("uiRequiresApproval").checked,
            missing_secret: document.getElementById("uiMissingSecret").checked
          })
        });
        const c = data.composition;
        result.textContent = `${c.space} · ${c.assistant_state.label} · ${c.component_ids.join(", ")} · execution_allowed=${c.execution_allowed}.`;
        result.className = c.friction_required ? "small notice" : "small ok";
        currentState.ui_composition_preview = c;
        render(currentState);
      } catch (error) {
        result.textContent = error.message;
        result.className = "small danger";
      }
    });

    document.getElementById("plannerPreviewForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const result = document.getElementById("plannerPreviewResult");
      result.textContent = "Planner preview maken…";
      result.className = "small";
      try {
        const data = await api("/api/planner/preview", {
          method: "POST",
          body: JSON.stringify({
            task_id: "task-planner-read-only-proof-of-concept",
            request: document.getElementById("plannerPreviewRequest").value,
            requested_action: document.getElementById("plannerPreviewAction").value
          })
        });
        result.textContent = `${data.preview.decision}: ${data.preview.proposals.length} proposal(s), ${data.preview.conflicts.length} conflict(en), ${data.preview.free_slots.length} vrije slot(s). Geen externe actie uitgevoerd.`;
        result.className = data.preview.approval_required ? "small notice" : "small ok";
        await refresh();
      } catch (error) {
        result.textContent = error.message;
        result.className = "small danger";
      }
    });

    document.getElementById("memoryForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const result = document.getElementById("memoryResult");
      result.textContent = "Memory candidate maken…";
      result.className = "small";
      try {
        const payload = {
          content: document.getElementById("memoryContent").value,
          memory_type: document.getElementById("memoryType").value,
          source: document.getElementById("memorySource").value,
          confidence: Number(document.getElementById("memoryConfidence").value || 0.5),
          sensitivity: document.getElementById("memorySensitivity").value,
          privacy_level: document.getElementById("memoryPrivacy").value,
          expires_at: document.getElementById("memoryExpiry").value,
          review_note: document.getElementById("memoryReviewNote").value,
          graph_entities: document.getElementById("memoryEntities").value.split(",").map(item => item.trim()).filter(Boolean)
        };
        const data = await api("/api/memory", { method: "POST", body: JSON.stringify(payload) });
        result.textContent = `${data.id} aangemaakt als review-first memory. Geen externe opslag.`;
        result.className = "small ok";
        document.getElementById("memoryContent").value = "";
        document.getElementById("memorySource").value = "";
        document.getElementById("memoryEntities").value = "";
        document.getElementById("memoryReviewNote").value = "";
        await refresh();
      } catch (error) {
        result.textContent = error.message;
        result.className = "small danger";
      }
    });

    document.getElementById("memoryRetrievalForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const result = document.getElementById("memoryRetrievalResult");
      result.textContent = "Bronnen en memory ophalen…";
      result.className = "small";
      try {
        const data = await api("/api/memory/retrieve", {
          method: "POST",
          body: JSON.stringify({
            query: document.getElementById("memoryRetrievalQuery").value,
            scope: document.getElementById("memoryRetrievalScope").value,
            limit: Number(document.getElementById("memoryRetrievalLimit").value || 5)
          })
        });
        result.textContent = `${data.retrieval.answer_status}: ${data.retrieval.metrics.match_count} match(es), ${data.retrieval.metrics.latency_ms}ms, relevance ${Number(data.retrieval.metrics.relevance_score || 0).toFixed(2)}.`;
        result.className = data.retrieval.metrics.match_count ? "small ok" : "small notice";
        await refresh();
      } catch (error) {
        result.textContent = error.message;
        result.className = "small danger";
      }
    });

    function fillToolCandidate() {
      document.getElementById("toolManifestJson").value = JSON.stringify({
        tool_id: "github-mcp-candidate",
        name: "GitHub MCP Server",
        source_type: "mcp_server",
        source_url: "https://github.com/github/github-mcp-server",
        purpose: "GitHub repositories, issues en pull requests read-first koppelen zonder zelf een GitHub toolstack te bouwen.",
        owner: "Leon",
        status: "candidate",
        risk_level: "medium",
        read_scopes: ["repo:metadata", "repo:issues", "repo:pull_requests"],
        write_scopes: ["repo:issues", "repo:pull_requests"],
        required_env_keys: ["GITHUB_TOKEN"],
        cost_profile: "external API quota; no direct spend expected",
        resource_profile: "low",
        external_effects: ["github_api_read", "github_api_write"],
        approval_required_for: ["write", "connect", "install"],
        allowed_without_approval: ["read"],
        forbidden_actions: ["read_raw_secret", "secret_value:*", "repo:delete", "repo:admin"],
        maintenance_status: "candidate_from_user_plan",
        sandbox_required: true,
        notes: "Niet installeren of koppelen zonder approval; eerst repo/security review."
      }, null, 2);
    }
    window.fillToolCandidate = fillToolCandidate;

    document.getElementById("toolManifestForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const result = document.getElementById("toolManifestResult");
      result.textContent = "Registreren…";
      result.className = "small";
      try {
        const manifest = JSON.parse(document.getElementById("toolManifestJson").value || "{}");
        const data = await api("/api/tool-registry/propose", { method: "POST", body: JSON.stringify(manifest) });
        result.textContent = `${data.tool_id} geregistreerd als ${data.status}. Geen tool uitgevoerd.`;
        result.className = "small ok";
        await refresh();
      } catch (error) {
        result.textContent = error.message;
        result.className = "small danger";
      }
    });

    document.getElementById("toolCheckForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const result = document.getElementById("toolCheckResult");
      result.textContent = "Checken…";
      result.className = "small";
      try {
        const data = await api("/api/tool-permissions/check", {
          method: "POST",
          body: JSON.stringify({
            tool_id: document.getElementById("toolCheckId").value,
            action_type: document.getElementById("toolCheckAction").value,
            requested_scope: document.getElementById("toolCheckScope").value,
            approval_id: document.getElementById("toolCheckApproval").value
          })
        });
        result.textContent = `${data.check.decision}: ${data.check.reason}`;
        result.className = data.check.allowed ? "small ok" : "small notice";
        await refresh();
      } catch (error) {
        result.textContent = error.message;
        result.className = "small danger";
      }
    });

    async function scoreToolCandidate(toolId) {
      const result = document.getElementById("toolCheckResult");
      result.textContent = "Scoren…";
      result.className = "small";
      try {
        const data = await api("/api/tool-registry/score", { method: "POST", body: JSON.stringify({ tool_id: toolId }) });
        result.textContent = `${toolId}: ${data.score.score}/100 · ${data.score.recommendation} · ${data.score.evidence_level}`;
        result.className = "small ok";
      } catch (error) {
        result.textContent = error.message;
        result.className = "small danger";
      }
    }
    window.scoreToolCandidate = scoreToolCandidate;

    async function refreshGithubCandidate(toolId) {
      const result = document.getElementById("toolManifestResult");
      result.textContent = "GitHub metadata ophalen…";
      result.className = "small";
      try {
        const data = await api("/api/tool-registry/github-refresh", { method: "POST", body: JSON.stringify({ tool_id: toolId }) });
        const first = data.results?.[0] || {};
        result.textContent = `${toolId}: ${first.ok ? "fresh" : first.error || "error"} · ${first.score?.score ?? "—"}/100. Geen install of account gebruikt.`;
        result.className = first.ok ? "small ok" : "small notice";
        await refresh();
      } catch (error) {
        result.textContent = error.message;
        result.className = "small danger";
      }
    }
    window.refreshGithubCandidate = refreshGithubCandidate;

    async function refreshGithubCandidates() {
      const result = document.getElementById("toolManifestResult");
      result.textContent = "GitHub metadata voor candidates ophalen…";
      result.className = "small";
      try {
        const data = await api("/api/tool-registry/github-refresh", { method: "POST", body: JSON.stringify({ max_items: 8 }) });
        const ok = (data.results || []).filter(item => item.ok).length;
        result.textContent = `${ok}/${(data.results || []).length} GitHub candidates ververst${data.stopped_for_rate_limit ? " · gestopt door rate-limit" : ""}. Geen install of account gebruikt.`;
        result.className = data.stopped_for_rate_limit ? "small notice" : "small ok";
        await refresh();
      } catch (error) {
        result.textContent = error.message;
        result.className = "small danger";
      }
    }
    window.refreshGithubCandidates = refreshGithubCandidates;

    async function createToolReviewTasks() {
      const result = document.getElementById("toolReviewTaskResult");
      result.textContent = "Review-taken aanmaken…";
      result.className = "small";
      try {
        const data = await api("/api/tool-registry/create-review-tasks", { method: "POST", body: JSON.stringify({}) });
        result.textContent = `${data.created.length} review-taak/taken gemaakt, ${data.skipped.length} overgeslagen. Geen approval of uitvoering gestart.`;
        result.className = "small ok";
        await refresh();
      } catch (error) {
        result.textContent = error.message;
        result.className = "small danger";
      }
    }
    window.createToolReviewTasks = createToolReviewTasks;

    async function decide(id, choice) {
      await api("/api/decision", { method: "POST", body: JSON.stringify({ id, choice }) });
      await refresh();
    }
    window.decide = decide;

    async function continueAfterApproval(id) {
      const evidence = prompt("Waarvoor wordt deze approval nu eenmalig geconsumeerd?") || "User approved proposal and requested continuation.";
      await api("/api/approval/continue", { method: "POST", body: JSON.stringify({ id, evidence }) });
      await refresh();
    }
    window.continueAfterApproval = continueAfterApproval;

    async function proposeOrchestration(routingDecisionId) {
      await api("/api/orchestration/propose", { method: "POST", body: JSON.stringify({ routing_decision_id: routingDecisionId }) });
      await refresh();
    }
    window.proposeOrchestration = proposeOrchestration;

    async function markDecisionFeedback(routingDecisionId, feedbackType) {
      await api("/api/routing/feedback", { method: "POST", body: JSON.stringify({ routing_decision_id: routingDecisionId, feedback_type: feedbackType }) });
      await refresh();
    }
    window.markDecisionFeedback = markDecisionFeedback;

    async function promoteDecisionToEvalCase(routingDecisionId) {
      const expected_route = prompt("Expected route for this eval regression?") || "";
      if (!expected_route.trim()) return;
      const reason = prompt("Why was this routing decision wrong or unsafe?") || "";
      await api("/api/routing/eval-case", { method: "POST", body: JSON.stringify({ routing_decision_id: routingDecisionId, expected_route, reason }) });
      await refresh();
    }
    window.promoteDecisionToEvalCase = promoteDecisionToEvalCase;

    async function runRoutingEval() {
      const release_label = prompt("Release label for this eval run?") || "working-tree";
      await api("/api/routing/eval", { method: "POST", body: JSON.stringify({ release_label, record_run: true }) });
      await refresh();
    }
    window.runRoutingEval = runRoutingEval;

    async function applyOrchestration(id) {
      const review_note = prompt("Waarom apply je dit proposal?") || "";
      await api("/api/orchestration/apply", { method: "POST", body: JSON.stringify({ id, review_note }) });
      await refresh();
    }
    window.applyOrchestration = applyOrchestration;

    async function rejectOrchestration(id) {
      const review_note = prompt("Waarom reject je dit proposal?") || "";
      await api("/api/orchestration/reject", { method: "POST", body: JSON.stringify({ id, review_note }) });
      await refresh();
    }
    window.rejectOrchestration = rejectOrchestration;

    async function setTaskStatus(id, status) {
      const payload = { id, status };
      if (status === "blocked") {
        payload.blocked_reason = prompt("Waarom is deze taak geblokkeerd?") || "";
      }
      if (status === "done") {
        payload.result = prompt("Resultaat / wat is opgeleverd?") || "";
        payload.verification_note = prompt("Verificatiebewijs / command output?") || "";
      }
      if (status === "rejected") {
        payload.review_note = prompt("Waarom afgewezen?") || "";
      }
      if (status === "planned") {
        payload.reopen = confirm("Als deze taak terminal was, expliciet heropenen?");
      }
      await api("/api/tasks/status", { method: "POST", body: JSON.stringify(payload) });
      await refresh();
    }
    window.setTaskStatus = setTaskStatus;

    async function updateMemoryStatus(id, status) {
      const payload = { id, status };
      if (status === "active") {
        payload.review_note = prompt("Review note voor active memory (verplicht bij sensitive/long-term)") || "";
      }
      if (status === "rejected") {
        payload.review_note = prompt("Waarom reject je deze memory?") || "Rejected from dashboard";
      }
      await api("/api/memory/update", { method: "POST", body: JSON.stringify(payload) });
      await refresh();
    }
    window.updateMemoryStatus = updateMemoryStatus;

    async function lowerMemoryConfidence(id, currentConfidence) {
      const next = Math.max(0, Math.min(1, Number(prompt("Nieuwe confidence 0-1", String(Math.max(0, currentConfidence - 0.2))) || currentConfidence)));
      await api("/api/memory/update", { method: "POST", body: JSON.stringify({ id, confidence: next, review_note: "Confidence adjusted by user from dashboard" }) });
      await refresh();
    }
    window.lowerMemoryConfidence = lowerMemoryConfidence;

    async function deleteMemory(id) {
      const reason = prompt("Waarom moet Leon dit vergeten?") || "User requested memory deletion";
      await api("/api/memory/delete", { method: "POST", body: JSON.stringify({ id, reason }) });
      await refresh();
    }
    window.deleteMemory = deleteMemory;

    async function scrubMemory(id) {
      const reason = prompt("Waarom moet Leon deze memory volledig scrubben?") || "User requested memory scrub";
      await api("/api/memory/scrub", { method: "POST", body: JSON.stringify({ id, reason }) });
      await refresh();
    }
    window.scrubMemory = scrubMemory;

    async function proposeAgentAssignment(taskId) {
      await api("/api/agent-assignments/propose", {
        method: "POST",
        body: JSON.stringify({ task_id: taskId })
      });
      await refresh();
    }
    window.proposeAgentAssignment = proposeAgentAssignment;

    async function createProviderDryRun(taskId) {
      await api("/api/provider-adapters/openai-agents-sdk/dry-run", {
        method: "POST",
        body: JSON.stringify({ task_id: taskId })
      });
      await refresh();
    }
    window.createProviderDryRun = createProviderDryRun;

    async function createMcpIntake(toolId) {
      await api("/api/mcp-candidates/intake", {
        method: "POST",
        body: JSON.stringify({ tool_id: toolId })
      });
      await refresh();
    }
    window.createMcpIntake = createMcpIntake;

    async function applyAgentAssignment(id) {
      const review_note = prompt("Waarom apply je deze assignment?") || "";
      await api("/api/agent-assignments/apply", {
        method: "POST",
        body: JSON.stringify({ id, review_note })
      });
      await refresh();
    }
    window.applyAgentAssignment = applyAgentAssignment;

    async function rejectAgentAssignment(id) {
      const review_note = prompt("Waarom reject je deze assignment?") || "";
      await api("/api/agent-assignments/reject", {
        method: "POST",
        body: JSON.stringify({ id, review_note })
      });
      await refresh();
    }
    window.rejectAgentAssignment = rejectAgentAssignment;

    async function reviewAgentRun(id, reviewStatus) {
      const reviewNote = prompt("Review note vereist") || "";
      await api("/api/agent-runs/review", {
        method: "POST",
        body: JSON.stringify({ id, review_status: reviewStatus, review_note: reviewNote })
      });
      await refresh();
    }
    window.reviewAgentRun = reviewAgentRun;

    function openTechnicalInspectSurfaces() {
      const node = document.getElementById("technicalInspectSurfaces");
      if (!node) return;
      node.open = true;
      node.scrollIntoView({ behavior: motionConfig().reduced ? "auto" : "smooth", block: "start" });
    }
    window.openTechnicalInspectSurfaces = openTechnicalInspectSurfaces;

    document.querySelectorAll(".dock button[data-space]").forEach(button => {
      button.addEventListener("click", () => {
        setCanvasSpace(button.dataset.space);
      });
    });
    document.querySelectorAll(".dock button[data-dock-action]").forEach(button => {
      button.addEventListener("click", () => {
        handleDockAction(button).catch(error => {
          document.getElementById("shellAttention").textContent = error.message;
        });
      });
    });
    document.querySelectorAll("[data-expand-card]").forEach(node => {
      node.addEventListener("click", () => openDetailWindow(node));
      node.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openDetailWindow(node);
        }
      });
    });
    document.getElementById("detailClose")?.addEventListener("click", closeDetailWindow);
    document.getElementById("detailBackdrop")?.addEventListener("click", event => {
      if (event.target?.id === "detailBackdrop") closeDetailWindow();
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && !document.getElementById("detailBackdrop")?.hidden) closeDetailWindow();
    });

    refresh().catch(error => {
      document.getElementById("runStatus").textContent = error.message;
      document.getElementById("runDot").className = "dot risk";
    });
  </script>
</body>
</html>
"""


def render_login(message: str = "") -> str:
    safe_message = html.escape(message)
    message_html = f"<p class='error'>{safe_message}</p>" if safe_message else ""
    return f"""<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Leon Control Plane — Login</title>
  <style>
    :root {{ color-scheme: dark; --bg:#090b10; --panel:rgba(255,255,255,.09); --line:rgba(255,255,255,.14); --text:#f4f7fb; --muted:#a8b3c7; --blue:#62a8ff; --red:#fb7185; }}
    body {{ margin:0; min-height:100vh; display:grid; place-items:center; background:radial-gradient(circle at 30% 0%, rgba(98,168,255,.18), transparent 34rem), var(--bg); color:var(--text); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ width:min(480px, calc(100vw - 32px)); background:var(--panel); border:1px solid var(--line); border-radius:24px; padding:24px; box-shadow:0 24px 80px rgba(0,0,0,.3); }}
    h1 {{ margin:0 0 8px; letter-spacing:-.04em; }}
    p {{ color:var(--muted); line-height:1.45; }}
    input, button {{ width:100%; box-sizing:border-box; border-radius:14px; border:1px solid var(--line); background:rgba(255,255,255,.08); color:var(--text); padding:12px; font:inherit; }}
    button {{ margin-top:12px; background:rgba(98,168,255,.18); border-color:rgba(98,168,255,.4); cursor:pointer; }}
    .error {{ color:var(--red); }}
    code {{ color:var(--text); }}
  </style>
</head>
<body>
  <main>
    <h1>Leon Control Plane</h1>
    <p>Remote dashboard access vereist een lokaal dashboard-token.</p>
    {message_html}
    <form method="post" action="/api/login">
      <input type="password" name="token" autocomplete="current-password" placeholder="LEON_DASHBOARD_TOKEN" autofocus />
      <button type="submit">Login</button>
    </form>
    <p>Token nog niet ingesteld? Run lokaal: <code>./scripts/leon-dashboard-token</code></p>
  </main>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "LeonControlPlane/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        message = redact_text(format % args)
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), message))

    def _send_json(self, data: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(redact_value(data), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self, target: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("location", target)
        self.send_header("content-length", "0")
        self.end_headers()

    def _send_login_cookie(self, token: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("location", "/")
        self.send_header(
            "set-cookie",
            f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Secure",
        )
        self.send_header("content-length", "0")
        self.end_headers()

    def _read_raw_body(self, max_length: int = 64_000) -> bytes:
        length = int(self.headers.get("content-length", "0"))
        if length > max_length:
            raise ValueError("Request body too large")
        return self.rfile.read(length) if length else b""

    def _read_body(self, *, allow_secret_values: bool = False) -> dict[str, Any]:
        raw = self._read_raw_body().decode("utf-8") or "{}"
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("JSON object expected")
        if not allow_secret_values:
            try:
                assert_no_secrets(f"request body for {self.path}", data)
            except SecretScanError as exc:
                STORE.record_secret_scan_failure(
                    surface=f"ingestion:{self.path}",
                    label=exc.label,
                    finding_kinds=exc.result.kinds,
                    finding_count=exc.result.total,
                    actor_type="system",
                    actor_id="http-ingestion",
                )
                raise
        return data

    def _auth_required(self) -> bool:
        mode = auth_mode()
        if mode in {"off", "disabled"}:
            return False
        if mode == "required":
            return True
        return not is_local_host_header(self.headers.get("host", ""))

    def _authorized(self) -> bool:
        if not self._auth_required():
            return True
        token = dashboard_token()
        if not token:
            return False
        auth_header = self.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            candidate = auth_header.split(" ", 1)[1].strip()
            if hmac.compare_digest(candidate, token):
                return True
        cookie = SimpleCookie(self.headers.get("cookie", ""))
        if SESSION_COOKIE in cookie and hmac.compare_digest(cookie[SESSION_COOKIE].value, token):
            return True
        return False

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        if self.path.startswith("/api/"):
            status = HTTPStatus.SERVICE_UNAVAILABLE if not dashboard_token() else HTTPStatus.UNAUTHORIZED
            error = "Dashboard token is not configured" if not dashboard_token() else "Unauthorized"
            self._send_json({"error": error}, status)
            return False
        message = "Token is nog niet geconfigureerd." if not dashboard_token() else ""
        self._send_html(render_login(message), HTTPStatus.UNAUTHORIZED)
        return False

    def do_GET(self) -> None:
        if self.path == "/login":
            self._send_html(render_login())
            return
        if not self._require_auth():
            return
        try:
            work_response = work_request(STORE, method="GET", path=self.path)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if work_response is not None:
            self._send_json(work_response)
            return
        if self.path == "/" or self.path == "/dashboard":
            self._send_html(render_dashboard())
            return
        if self.path == "/api/state":
            self._send_json(state_for_client())
            return
        if self.path == "/api/tool-registry/adoption-shortlist":
            state = state_for_client()
            self._send_json({"ok": True, "shortlist": state.get("tool_adoption_shortlist", {})})
            return
        if self.path == "/api/tool-registry/review-packets":
            state = state_for_client()
            self._send_json({"ok": True, "review_packets": state.get("tool_review_packets", {})})
            return
        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            if self.path == "/api/login":
                self._handle_login()
                return
            if not self._require_auth():
                return
            if self.path in {"/api/work/jobs", "/api/work/control"}:
                self._send_json(work_request(STORE, method="POST", path=self.path, body=self._read_body()))
                return
            if self.path == "/api/secrets":
                self._handle_secret()
                return
            if self.path == "/api/decision":
                self._handle_decision()
                return
            if self.path == "/api/approval/consume":
                self._handle_approval_consume()
                return
            if self.path == "/api/approval/continue":
                self._handle_approval_continue()
                return
            if self.path == "/api/tasks":
                self._handle_task_create()
                return
            if self.path == "/api/tasks/status":
                self._handle_task_status()
                return
            if self.path == "/api/audit/validate":
                self._send_json({"ok": True, "valid": STORE.validate_audit_hash_chain()})
                return
            if self.path == "/api/routing/decide":
                self._handle_routing_decide()
                return
            if self.path == "/api/routing/eval":
                self._handle_routing_eval()
                return
            if self.path == "/api/routing/eval-case":
                self._handle_routing_eval_case()
                return
            if self.path == "/api/routing/feedback":
                self._handle_routing_feedback()
                return
            if self.path in {"/api/tool-registry/propose", "/api/tools/register"}:
                self._handle_tool_manifest_register()
                return
            if self.path == "/api/tool-registry/score":
                self._handle_tool_manifest_score()
                return
            if self.path == "/api/tool-registry/github-refresh":
                self._handle_tool_github_refresh()
                return
            if self.path == "/api/tool-registry/create-review-tasks":
                self._handle_tool_review_tasks_create()
                return
            if self.path in {"/api/tool-permissions/check", "/api/tools/check"}:
                self._handle_tool_permission_check()
                return
            if self.path in {"/api/connectors/register", "/api/connector-registry/register"}:
                self._handle_connector_manifest_register()
                return
            if self.path in {"/api/connector-permissions/check", "/api/connectors/check"}:
                self._handle_connector_permission_check()
                return
            if self.path in {"/api/connectors/read-context", "/api/connectors/ingest-read"}:
                self._handle_connector_read_context()
                return
            if self.path == "/api/orchestration/propose":
                self._handle_orchestration_propose()
                return
            if self.path == "/api/orchestration/apply":
                self._handle_orchestration_apply()
                return
            if self.path == "/api/orchestration/reject":
                self._handle_orchestration_reject()
                return
            if self.path == "/api/agent-assignments/propose":
                self._handle_agent_assignment_propose()
                return
            if self.path == "/api/agent-assignments/apply":
                self._handle_agent_assignment_apply()
                return
            if self.path == "/api/agent-assignments/reject":
                self._handle_agent_assignment_reject()
                return
            if self.path == "/api/provider-adapters/openai-agents-sdk/dry-run":
                self._handle_openai_agents_provider_dry_run()
                return
            if self.path == "/api/mcp-candidates/intake":
                self._handle_mcp_candidate_intake()
                return
            if self.path == "/api/planner/preview":
                self._handle_planner_preview()
                return
            if self.path == "/api/ui/compose":
                self._handle_ui_compose()
                return
            if self.path == "/api/memory":
                self._handle_memory_create()
                return
            if self.path in {"/api/memory/retrieve", "/api/memory/search"}:
                self._handle_memory_retrieve()
                return
            if self.path == "/api/memory/update":
                self._handle_memory_update()
                return
            if self.path == "/api/memory/delete":
                self._handle_memory_delete()
                return
            if self.path == "/api/memory/scrub":
                self._handle_memory_scrub()
                return
            if self.path == "/api/memory/graph-edge":
                self._handle_memory_graph_edge()
                return
            if self.path == "/api/sources/ingest":
                self._handle_source_ingest()
                return
            if self.path == "/api/sources/delete":
                self._handle_source_delete()
                return
            if self.path == "/api/sources/scrub":
                self._handle_source_scrub()
                return
            if self.path == "/api/night-queue/run":
                self._handle_night_queue_run()
                return
            if self.path == "/api/morning-brief/generate":
                self._handle_morning_brief_generate()
                return
            if self.path == "/api/agent-runs/mock":
                self._handle_agent_run_mock()
                return
            if self.path == "/api/agent-runs/review":
                self._handle_agent_run_review()
                return
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def _handle_login(self) -> None:
        token = dashboard_token()
        if not token:
            self._send_html(render_login("Token is nog niet geconfigureerd."), HTTPStatus.SERVICE_UNAVAILABLE)
            return
        content_type = self.headers.get("content-type", "")
        raw = self._read_raw_body().decode("utf-8")
        if "application/json" in content_type:
            data = json.loads(raw or "{}")
            candidate = str(data.get("token", ""))
        else:
            candidate = parse_qs(raw).get("token", [""])[0]
        if not hmac.compare_digest(candidate, token):
            self._send_html(render_login("Ongeldige token."), HTTPStatus.UNAUTHORIZED)
            return
        self._send_login_cookie(token)

    def _handle_secret(self) -> None:
        data = self._read_body(allow_secret_values=True)
        key = str(data.get("key", "")).strip()
        value = str(data.get("value", ""))
        state = load_state()
        allowed = {item["key"] for item in state.get("required_env", [])}
        if key not in allowed:
            raise ValueError("This env key is not registered in the control plane")
        upsert_env_value(key, value)
        STORE.record_secret_updated(key)
        self._send_json({"ok": True, "key": key})

    def _handle_decision(self) -> None:
        data = self._read_body()
        decision_id = str(data.get("id", "")).strip()
        choice = str(data.get("choice", "")).strip()
        note = str(data.get("note", "")).strip()
        if not decision_id or choice not in {"approved", "rejected", "expired", "deferred"}:
            raise ValueError("Expected id and choice approved/rejected/expired")
        STORE.update_approval(decision_id, choice, note)
        self._send_json({"ok": True})

    def _handle_approval_consume(self) -> None:
        data = self._read_body()
        approval_id = str(data.get("id", "")).strip()
        evidence = str(data.get("evidence", "")).strip()
        if not approval_id:
            raise ValueError("Expected approval id")
        STORE.consume_approval(approval_id, evidence=evidence)
        self._send_json({"ok": True})

    def _handle_approval_continue(self) -> None:
        data = self._read_body()
        approval_id = str(data.get("id", "")).strip()
        evidence = str(data.get("evidence") or "User approved proposal and requested continuation.").strip()
        if not approval_id:
            raise ValueError("Expected approval id")
        result = STORE.continue_task_after_approval(approval_id, evidence=evidence)
        self._send_json({"ok": True, **result})

    def _handle_task_create(self) -> None:
        data = self._read_body()
        task_id = STORE.create_task(
            title=str(data.get("title", "")),
            goal=str(data.get("goal", "")),
            phase_id=str(data.get("phase_id") or "") or None,
            owner=str(data.get("owner") or "Codex"),
            status=str(data.get("status") or "new"),
            priority=str(data.get("priority") or "P1"),
            risk_level=str(data.get("risk_level") or "medium"),
            approval_required=bool(data.get("approval_required", False)),
            acceptance_criteria=str(data.get("acceptance_criteria") or ""),
            value_score=int(data.get("value_score") if data.get("value_score") is not None else 3),
            source_refs=data.get("source_refs"),
            parent_task_id=str(data.get("parent_task_id") or "") or None,
        )
        self._send_json({"ok": True, "id": task_id}, HTTPStatus.CREATED)

    def _handle_task_status(self) -> None:
        data = self._read_body()
        task_id = str(data.get("id", "")).strip()
        status = str(data.get("status", "")).strip()
        if not task_id or not status:
            raise ValueError("Expected task id and status")
        STORE.update_task_status(
            task_id,
            status,
            blocked_reason=str(data.get("blocked_reason") or ""),
            result=str(data.get("result") or ""),
            verification_note=str(data.get("verification_note") or ""),
            review_note=str(data.get("review_note") or ""),
            approval_id=str(data.get("approval_id") or "") or None,
            secret_key=str(data.get("secret_key") or "") or None,
            reopen=bool(data.get("reopen", False)),
        )
        self._send_json({"ok": True})

    def _classify_request_with_context(self, data: dict[str, Any], text: str) -> dict[str, Any]:
        memory_context = None
        if bool(data.get("use_memory_context", True)):
            try:
                memory_context = STORE.retrieve_memory(
                    text,
                    scope=str(data.get("memory_scope") or "context"),
                    limit=int(data.get("memory_limit") or 5),
                    actor_type="system",
                    actor_id="decision-memory-context",
                )
            except SecretScanError:
                memory_context = {
                    "answer_status": "skipped_secret_like_query",
                    "confidence": 0,
                    "source_refs": [],
                    "related_graph_entries": [],
                    "conflicts": [],
                    "metrics": {"match_count": 0, "relevance_score": 0},
                }
        return classify_user_request(
            text,
            budget_mode=str(data.get("budget_mode") or "balanced"),
            privacy=str(data.get("privacy") or "normal"),
            local_gpu_ready=bool(data.get("local_gpu_ready", False)),
            local_route_status=str(data.get("local_route_status") or ""),
            local_latency_ms=data.get("local_latency_ms"),
            memory_context=memory_context,
        )

    def _handle_routing_decide(self) -> None:
        data = self._read_body()
        text = str(data.get("text", "")).strip()
        expected_route = str(data.get("expected_route", "")).strip() or None
        decision = self._classify_request_with_context(data, text)
        if decision["route"] not in {
            "direct_answer",
            "clarification_required",
            "quick_tool_use",
            "memory_retrieval",
            "shell_agent_flow",
            "research_agent",
            "task_queue",
            "approval_required",
            "refuse_redirect",
        }:
            raise ValueError("Invalid route emitted by Decision Layer")
        decision_id = STORE.record_routing_decision(decision)
        decision["id"] = decision_id
        eval_pass = None if expected_route is None else decision["route"] == expected_route
        self._send_json({"ok": True, "decision": decision, "eval_pass": eval_pass}, HTTPStatus.CREATED)

    def _handle_routing_eval(self) -> None:
        data = self._read_body()
        release_label = str(data.get("release_label") or data.get("release") or "working-tree").strip() or "working-tree"
        cases = [*load_eval_cases(), *STORE.active_routing_eval_cases()]
        summary = evaluate_cases(cases, release_label=release_label)
        if bool(data.get("record_run", True)):
            run = STORE.record_routing_eval_run(
                summary,
                release_label=release_label,
                actor_type="system",
                actor_id="routing-eval-api",
            )
            summary = run["summary"]
        self._send_json(summary, HTTPStatus.OK if summary["ok"] else HTTPStatus.BAD_REQUEST)

    def _handle_routing_eval_case(self) -> None:
        data = self._read_body()
        routing_decision_id = str(data.get("routing_decision_id") or data.get("id") or "").strip()
        expected_route = str(data.get("expected_route") or "").strip()
        if not routing_decision_id or not expected_route:
            raise ValueError("Expected routing_decision_id and expected_route")
        eval_case_id = STORE.promote_routing_failure_to_eval_case(
            routing_decision_id,
            expected_route,
            source_feedback_id=str(data.get("source_feedback_id") or "") or None,
            reason=str(data.get("reason") or data.get("note") or ""),
            actor_type="user",
            actor_id="dashboard",
        )
        self._send_json({"ok": True, "eval_case_id": eval_case_id}, HTTPStatus.CREATED)

    def _handle_routing_feedback(self) -> None:
        data = self._read_body()
        routing_decision_id = str(data.get("routing_decision_id") or data.get("id") or "").strip()
        feedback_type = str(data.get("feedback_type") or data.get("type") or "").strip()
        note = str(data.get("note") or "").strip()
        if not routing_decision_id:
            raise ValueError("Expected routing_decision_id")
        feedback_id = STORE.record_decision_feedback(
            routing_decision_id,
            feedback_type,
            note=note,
            actor_type="user",
            actor_id="dashboard",
        )
        response: dict[str, Any] = {"ok": True, "feedback_id": feedback_id}
        expected_route = str(data.get("expected_route") or "").strip()
        if bool(data.get("promote_to_eval_case", False)) or expected_route:
            if not expected_route:
                raise ValueError("expected_route is required when promoting feedback to an eval case")
            response["eval_case_id"] = STORE.promote_routing_failure_to_eval_case(
                routing_decision_id,
                expected_route,
                source_feedback_id=feedback_id,
                reason=note,
                actor_type="user",
                actor_id="dashboard",
            )
        self._send_json(response, HTTPStatus.CREATED)

    def _handle_tool_manifest_register(self) -> None:
        data = self._read_body()
        manifest = normalize_tool_manifest(data)
        if manifest["status"] != "candidate":
            raise ValueError("Tool manifest registration is candidate-only; status review/promotions require a separate gated transition.")
        tool_id = STORE.upsert_tool_manifest(manifest)
        self._send_json({"ok": True, "tool_id": tool_id, "status": manifest["status"]}, HTTPStatus.CREATED)

    def _handle_tool_manifest_score(self) -> None:
        data = self._read_body()
        tool_id = str(data.get("tool_id") or "").strip()
        if not tool_id:
            raise ValueError("Expected tool_id")
        manifest = STORE.get_tool_manifest(tool_id)
        score = score_tool_candidate(manifest)
        self._send_json({"ok": True, "score": score})

    def _handle_tool_github_refresh(self) -> None:
        data = self._read_body()
        tool_id = str(data.get("tool_id") or "").strip()
        max_items = min(10, max(1, int(data.get("max_items") or 8)))
        manifests: list[dict[str, Any]] = []
        if tool_id:
            manifests = [STORE.get_tool_manifest(tool_id)]
        else:
            state = STORE.get_state()
            for item in state.get("tool_manifests", []):
                manifest = json.loads(item.get("manifest_json") or "{}")
                if "github.com/" in str(manifest.get("source_url") or ""):
                    manifests.append(manifest)
                if len(manifests) >= max_items:
                    break

        results: list[dict[str, Any]] = []
        stopped = False
        for manifest in manifests:
            result = refresh_manifest_github_metadata(manifest)
            safe_result = {
                "tool_id": result.get("tool_id"),
                "ok": bool(result.get("ok")),
                "status": result.get("status", 0),
                "error": result.get("error", ""),
                "metadata": result.get("metadata", {}),
            }
            if result.get("ok"):
                STORE.upsert_tool_manifest(
                    result["manifest"],
                    actor_type="system",
                    actor_id="github-metadata-refresh",
                )
                safe_result["score"] = score_tool_candidate(result["manifest"])
            else:
                failed_manifest = dict(result.get("manifest") or manifest)
                previous = dict(failed_manifest.get("github_metadata") or {})
                failed_manifest["github_metadata"] = {
                    **previous,
                    **dict(result.get("metadata") or {}),
                    "refresh_status": result.get("error") or "error",
                    "last_error_status": result.get("status", 0),
                    "fetched_at": now_iso(),
                }
                STORE.upsert_tool_manifest(
                    failed_manifest,
                    actor_type="system",
                    actor_id="github-metadata-refresh",
                )
                safe_result["score"] = score_tool_candidate(failed_manifest)
            results.append(safe_result)
            if result.get("error") == "rate_limited":
                stopped = True
                break
        self._send_json({"ok": True, "results": results, "stopped_for_rate_limit": stopped}, HTTPStatus.CREATED)

    def _handle_tool_review_tasks_create(self) -> None:
        state = state_for_client()
        packets = list((state.get("tool_review_packets") or {}).get("packets") or [])
        existing_titles = {str(task.get("title") or "") for task in state.get("tasks", [])}
        created: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []
        for packet in packets:
            title = str(packet.get("recommended_task_title") or "").strip()
            if not title:
                continue
            if title in existing_titles:
                skipped.append({"title": title, "reason": "already_exists"})
                continue
            task_id = STORE.create_task(
                title=title,
                goal=str(packet.get("recommended_task_goal") or packet.get("summary") or ""),
                phase_id="phase-5",
                owner="Research Agent",
                status="new",
                priority="P1",
                risk_level="low",
                approval_required=False,
                acceptance_criteria=str(packet.get("acceptance_criteria") or ""),
                actor_type="system",
                actor_id="tool-review-packet",
            )
            STORE.update_task_status(task_id, "planned", actor_type="system", actor_id="tool-review-packet")
            created.append({"id": task_id, "title": title})
            existing_titles.add(title)
        self._send_json(
            {
                "ok": True,
                "created": created,
                "skipped": skipped,
                "policy": "local_review_tasks_only_no_execution_no_approval",
            },
            HTTPStatus.CREATED,
        )

    def _handle_tool_permission_check(self) -> None:
        data = self._read_body()
        tool_id = str(data.get("tool_id") or "").strip()
        if not tool_id:
            raise ValueError("Expected tool_id")
        manifest = STORE.get_tool_manifest(tool_id)
        approval_id = str(data.get("approval_id") or "").strip() or None
        approval_status = STORE.get_approval_status(approval_id)
        check = classify_tool_action(
            manifest,
            action_type=str(data.get("action_type") or "").strip(),
            requested_scope=str(data.get("requested_scope") or "").strip(),
            present_env_keys=parse_env_keys(),
            approval_id=approval_id,
            approval_status=approval_status,
        )
        check_id = STORE.record_tool_permission_check(check)
        check["id"] = check_id
        self._send_json({"ok": True, "check": check}, HTTPStatus.CREATED)

    def _handle_connector_manifest_register(self) -> None:
        data = self._read_body()
        manifest = normalize_connector_manifest(data)
        connector_id = STORE.upsert_connector_manifest(manifest)
        self._send_json({"ok": True, "connector_id": connector_id, "status": manifest["status"]}, HTTPStatus.CREATED)

    def _handle_connector_permission_check(self) -> None:
        data = self._read_body()
        connector_id = str(data.get("connector_id") or "").strip()
        if not connector_id:
            raise ValueError("Expected connector_id")
        manifest = STORE.get_connector_manifest(connector_id)
        approval_id = str(data.get("approval_id") or "").strip() or None
        approval_status = STORE.get_approval_status(approval_id)
        check = classify_connector_action(
            manifest,
            action_type=str(data.get("action_type") or "").strip(),
            requested_scope=str(data.get("requested_scope") or "").strip(),
            present_env_keys=parse_env_keys(),
            approval_id=approval_id,
            approval_status=approval_status,
        )
        check_id = STORE.record_connector_permission_check(check)
        check["id"] = check_id
        self._send_json({"ok": True, "check": check}, HTTPStatus.CREATED)

    def _handle_connector_read_context(self) -> None:
        data = self._read_body()
        result = STORE.ingest_connector_read_context(
            connector_id=str(data.get("connector_id") or "").strip(),
            requested_scope=str(data.get("requested_scope") or "").strip(),
            source_ref=str(data.get("source_ref") or "").strip(),
            title=str(data.get("title") or "").strip(),
            content=str(data.get("content") or "").strip(),
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
            present_env_keys=parse_env_keys(),
            approval_id=str(data.get("approval_id") or "").strip() or None,
            actor_type="system",
            actor_id="connector-read-api",
        )
        self._send_json({"ok": True, **result}, HTTPStatus.CREATED)

    def _handle_orchestration_propose(self) -> None:
        data = self._read_body()
        routing_decision_id = str(data.get("routing_decision_id") or "").strip()
        if routing_decision_id:
            decision = STORE.get_routing_decision(routing_decision_id)
        else:
            text = str(data.get("text") or "").strip()
            if not text:
                raise ValueError("Expected routing_decision_id or text")
            decision = self._classify_request_with_context(data, text)
            routing_decision_id = STORE.record_routing_decision(decision)
            decision["id"] = routing_decision_id
        proposal = build_orchestration_proposal(decision=decision, routing_decision_id=routing_decision_id)
        proposal_id = STORE.create_orchestration_proposal(proposal)
        proposal["proposal_id"] = proposal_id
        self._send_json({"ok": True, "proposal": proposal}, HTTPStatus.CREATED)

    def _handle_orchestration_apply(self) -> None:
        data = self._read_body()
        proposal_id = str(data.get("id") or "").strip()
        review_note = str(data.get("review_note") or "").strip()
        if not proposal_id:
            raise ValueError("Expected orchestration proposal id")
        result = STORE.apply_orchestration_proposal(proposal_id, review_note=review_note)
        self._send_json({"ok": True, **result})

    def _handle_orchestration_reject(self) -> None:
        data = self._read_body()
        proposal_id = str(data.get("id") or "").strip()
        review_note = str(data.get("review_note") or "").strip()
        if not proposal_id:
            raise ValueError("Expected orchestration proposal id")
        STORE.reject_orchestration_proposal(proposal_id, review_note=review_note)
        self._send_json({"ok": True})

    def _handle_agent_assignment_propose(self) -> None:
        data = self._read_body()
        task_id = str(data.get("task_id") or "").strip()
        if not task_id:
            raise ValueError("Expected task_id")
        task = STORE.get_task(task_id)
        proposal = build_agent_assignment_proposal(
            task=task,
            agent_role=str(data.get("agent_role") or "Mock Builder Agent"),
            runner_kind=str(data.get("runner_kind") or "local_mock"),
            task_type=str(data.get("task_type") or "") or None,
            complexity=str(data.get("complexity") or "") or None,
            privacy=str(data.get("privacy") or "normal"),
            budget_mode=str(data.get("budget_mode") or "balanced"),
            local_gpu_ready=bool(data.get("local_gpu_ready", False)),
            local_route_status=str(data.get("local_route_status") or ""),
            local_latency_ms=data.get("local_latency_ms"),
        )
        proposal_id = STORE.create_agent_assignment_proposal(proposal)
        proposal["proposal_id"] = proposal_id
        self._send_json({"ok": True, "proposal": proposal}, HTTPStatus.CREATED)

    def _handle_agent_assignment_apply(self) -> None:
        data = self._read_body()
        proposal_id = str(data.get("id") or "").strip()
        review_note = str(data.get("review_note") or "").strip()
        if not proposal_id:
            raise ValueError("Expected agent assignment proposal id")
        result = STORE.apply_agent_assignment_proposal(proposal_id, review_note=review_note)
        self._send_json({"ok": True, **result})

    def _handle_agent_assignment_reject(self) -> None:
        data = self._read_body()
        proposal_id = str(data.get("id") or "").strip()
        review_note = str(data.get("review_note") or "").strip()
        if not proposal_id:
            raise ValueError("Expected agent assignment proposal id")
        STORE.reject_agent_assignment_proposal(proposal_id, review_note=review_note)
        self._send_json({"ok": True})

    def _handle_openai_agents_provider_dry_run(self) -> None:
        data = self._read_body()
        proposal_id = str(data.get("agent_assignment_proposal_id") or data.get("proposal_id") or "").strip()
        task_id = str(data.get("task_id") or "").strip()
        assignment = None
        if proposal_id:
            assignment = STORE.get_agent_assignment_proposal(proposal_id)
            task = STORE.get_task(str(assignment["task_id"]))
        else:
            if not task_id:
                raise ValueError("Expected task_id or agent_assignment_proposal_id")
            task = STORE.get_task(task_id)
        dry_run = build_openai_agents_sdk_dry_run_plan(
            task=task,
            assignment_proposal=assignment,
            present_env_keys=parse_env_keys(),
        )
        dry_run_id = STORE.create_provider_dry_run(dry_run)
        dry_run["id"] = dry_run_id
        self._send_json(
            {
                "ok": True,
                "dry_run": dry_run,
                "policy": "plan_only_no_sdk_import_no_install_no_provider_call_no_secret_value_read",
            },
            HTTPStatus.CREATED,
        )

    def _handle_mcp_candidate_intake(self) -> None:
        data = self._read_body()
        tool_id = str(data.get("tool_id") or "").strip()
        if not tool_id:
            raise ValueError("Expected tool_id")
        manifest = STORE.get_tool_manifest(tool_id)
        checklist = build_mcp_candidate_intake(
            manifest=manifest,
            tool_mappings=list(data.get("tool_mappings") or []),
            reviewer_note=str(data.get("reviewer_note") or ""),
        )
        intake_id = STORE.create_mcp_candidate_intake(checklist)
        checklist["id"] = intake_id
        self._send_json(
            {
                "ok": True,
                "intake": checklist,
                "policy": "review_only_no_install_no_connect_no_approval_no_status_promotion",
            },
            HTTPStatus.CREATED,
        )

    def _handle_planner_preview(self) -> None:
        data = self._read_body()
        preview = build_planner_preview(data)
        preview_id = STORE.create_planner_preview(
            preview,
            task_id=str(data.get("task_id") or "") or None,
            actor_type="system",
            actor_id="planner-preview",
        )
        preview["id"] = preview_id
        self._send_json(
            {
                "ok": True,
                "preview": preview,
                "policy": "sample_data_preview_only_no_mcp_install_no_account_connect_no_external_write_no_secret_read",
            },
            HTTPStatus.CREATED,
        )

    def _handle_ui_compose(self) -> None:
        data = self._read_body()
        preview = compose_ui(
            route=str(data.get("route") or "direct_answer"),
            task_status=str(data.get("task_status") or ""),
            risk_level=str(data.get("risk_level") or "low"),
            requires_approval=bool(data.get("requires_approval", False)),
            missing_secret=bool(data.get("missing_secret", False)),
            component_need=str(data.get("component_need") or ""),
            compact=bool(data.get("compact", False)),
        )
        registered_missing_components = []
        if preview.get("missing_component_protocol"):
            for record in preview.get("missing_component_records") or []:
                if not isinstance(record, dict):
                    continue
                registered_missing_components.append(
                    STORE.register_missing_component_need(
                        requested_component=str(record.get("requested_component") or ""),
                        requested_capability=str(record.get("requested_capability") or ""),
                        route=str(record.get("route") or preview.get("route") or ""),
                        space=str(record.get("space") or preview.get("space") or ""),
                        task_status=str(record.get("task_status") or preview.get("task_status") or ""),
                        risk_level=str(record.get("risk_level") or preview.get("risk_level") or "medium"),
                        fallback_component_ids=record.get("fallback_component_ids") or preview.get("component_ids") or [],
                        context={
                            "source": "api_ui_compose",
                            "composition": preview,
                            "requested_body_keys": sorted(data.keys()),
                        },
                        source_ref=f"ui_compose:{preview.get('route') or 'unknown'}",
                        actor_type="user",
                        actor_id="dashboard-ui-compose",
                    )
                )
        self._send_json({
            "ok": True,
            "composition": preview,
            "registered_missing_components": registered_missing_components,
            "policy": "preview_only_no_execution_no_component_promotion",
        })

    def _handle_memory_create(self) -> None:
        data = self._read_body()
        memory_id = STORE.create_memory_item(data, actor_type="user", actor_id="dashboard-memory")
        self._send_json({"ok": True, "id": memory_id}, HTTPStatus.CREATED)

    def _handle_memory_retrieve(self) -> None:
        data = self._read_body()
        result = STORE.retrieve_memory(
            str(data.get("query") or data.get("question") or ""),
            scope=str(data.get("scope") or "context"),
            limit=int(data.get("limit") or 5),
            actor_type="user",
            actor_id="dashboard-memory-retrieval",
        )
        self._send_json({"ok": True, "retrieval": result})

    def _handle_memory_update(self) -> None:
        data = self._read_body()
        memory_id = str(data.get("id") or "").strip()
        updates = dict(data)
        updates.pop("id", None)
        STORE.update_memory_item(memory_id, updates, actor_type="user", actor_id="dashboard-memory")
        self._send_json({"ok": True})

    def _handle_memory_delete(self) -> None:
        data = self._read_body()
        memory_id = str(data.get("id") or "").strip()
        reason = str(data.get("reason") or "User requested memory deletion").strip()
        STORE.delete_memory_item(memory_id, reason=reason, actor_type="user", actor_id="dashboard-memory")
        self._send_json({"ok": True})

    def _handle_memory_scrub(self) -> None:
        data = self._read_body()
        memory_id = str(data.get("id") or "").strip()
        reason = str(data.get("reason") or "User requested memory scrub").strip()
        STORE.scrub_memory_item(memory_id, reason=reason, actor_type="user", actor_id="dashboard-memory")
        self._send_json({"ok": True})

    def _handle_memory_graph_edge(self) -> None:
        data = self._read_body()
        edge_id = STORE.create_memory_graph_edge(data, actor_type="user", actor_id="dashboard-memory")
        self._send_json({"ok": True, "id": edge_id}, HTTPStatus.CREATED)

    def _handle_source_ingest(self) -> None:
        data = self._read_body()
        mode = str(data.get("mode") or "").strip() or ("record" if data.get("content") else "local_file")
        if mode == "project_knowledge":
            source_refs = data.get("source_refs")
            if source_refs is not None and not isinstance(source_refs, list):
                raise ValueError("source_refs must be a list")
            result = STORE.ingest_project_knowledge(
                source_refs=source_refs,
                include_tasks=bool(data.get("include_tasks", True)),
                include_previous_runs=bool(data.get("include_previous_runs", True)),
                actor_type="user",
                actor_id="dashboard-source-ingestion",
            )
            self._send_json({"ok": True, **result}, HTTPStatus.CREATED)
            return
        if mode == "local_file":
            source_id = STORE.ingest_local_file(
                str(data.get("source_ref") or data.get("path") or ""),
                source_type=str(data.get("source_type") or "") or None,
                title=str(data.get("title") or "") or None,
                actor_type="user",
                actor_id="dashboard-source-ingestion",
            )
        elif mode == "task":
            source_id = STORE.ingest_task_source(
                str(data.get("task_id") or data.get("source_ref") or ""),
                actor_type="user",
                actor_id="dashboard-source-ingestion",
            )
        elif mode == "leon_run":
            source_id = STORE.ingest_leon_run_source(
                str(data.get("run_id") or data.get("source_ref") or ""),
                actor_type="user",
                actor_id="dashboard-source-ingestion",
            )
        elif mode == "record":
            source_id = STORE.ingest_source_record(
                data,
                block_on_secret=bool(data.get("block_on_secret", True)),
                actor_type="user",
                actor_id="dashboard-source-ingestion",
            )
        else:
            raise ValueError("invalid source ingestion mode")
        self._send_json({"ok": True, "id": source_id}, HTTPStatus.CREATED)

    def _handle_source_delete(self) -> None:
        data = self._read_body()
        source_id = str(data.get("id") or "").strip()
        reason = str(data.get("reason") or "User requested source index deletion").strip()
        STORE.delete_source_record(source_id, reason=reason, actor_type="user", actor_id="dashboard-source-ingestion")
        self._send_json({"ok": True})

    def _handle_source_scrub(self) -> None:
        data = self._read_body()
        source_id = str(data.get("id") or "").strip()
        reason = str(data.get("reason") or "User requested source index scrub").strip()
        STORE.scrub_source_record(source_id, reason=reason, actor_type="user", actor_id="dashboard-source-ingestion")
        self._send_json({"ok": True})

    def _handle_night_queue_run(self) -> None:
        data = self._read_body()
        allowed_risk_classes = data.get("allowed_risk_classes")
        if allowed_risk_classes is None:
            allowed_risk_classes = DEFAULT_ALLOWED_RISK_CLASSES
        if not isinstance(allowed_risk_classes, list):
            raise ValueError("allowed_risk_classes must be a list")
        requested_actions = data.get("requested_actions")
        if requested_actions is not None and not isinstance(requested_actions, list):
            raise ValueError("requested_actions must be a list")
        result = NightQueueScheduler(STORE).run_once(
            allowed_risk_classes=[str(item) for item in allowed_risk_classes],
            requested_actions=[str(item) for item in requested_actions] if requested_actions else None,
            budget_mode=str(data.get("budget_mode") or "economy"),
            local_gpu_ready=bool(data.get("local_gpu_ready", False)),
        )
        self._send_json({"ok": True, "night_queue_run": result}, HTTPStatus.CREATED)

    def _handle_morning_brief_generate(self) -> None:
        data = self._read_body()
        run_id = str(data.get("run_id") or "").strip() or None
        brief = STORE.generate_morning_brief_for_night_run(run_id)
        self._send_json({"ok": True, "morning_brief": brief}, HTTPStatus.CREATED)

    def _handle_agent_run_mock(self) -> None:
        data = self._read_body()
        task_id = str(data.get("task_id", "")).strip()
        if not task_id:
            raise ValueError("Expected task_id")
        result = RUNNER.run(
            task_id=task_id,
            agent_role=str(data.get("agent_role") or "Mock Builder Agent"),
            task_type=str(data.get("task_type") or "documentation"),
            complexity=str(data.get("complexity") or "medium"),
            risk=str(data.get("risk") or "medium"),
            privacy=str(data.get("privacy") or "normal"),
            budget_mode=str(data.get("budget_mode") or "balanced"),
            local_gpu_ready=bool(data.get("local_gpu_ready", False)),
            local_route_status=str(data.get("local_route_status") or ""),
            local_latency_ms=data.get("local_latency_ms"),
        )
        self._send_json({"ok": True, "agent_run": result}, HTTPStatus.CREATED)

    def _handle_agent_run_review(self) -> None:
        data = self._read_body()
        run_id = str(data.get("id", "")).strip()
        review_status = str(data.get("review_status", "")).strip()
        review_note = str(data.get("review_note", "")).strip()
        if not run_id:
            raise ValueError("Expected agent run id")
        STORE.review_agent_run(run_id, review_status=review_status, review_note=review_note)
        self._send_json({"ok": True})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Leon AI Assistant local control-plane dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args(argv)

    if args.host not in {"127.0.0.1", "localhost"}:
        print("Refusing to bind non-localhost without adding authentication first.", file=sys.stderr)
        return 2

    STORE.initialize()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Leon control plane running at http://{args.host}:{args.port}")
    print(f"Local env file: {ENV_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Leon control plane.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
