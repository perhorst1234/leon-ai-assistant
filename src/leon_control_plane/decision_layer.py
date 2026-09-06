from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from leon_control_plane.model_policy import choose_route
from leon_control_plane.risk_policy import classify_request_policy
from leon_control_plane.secret_scanner import redact_text


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVAL_PATH = REPO_ROOT / "config" / "routing-evals.json"

ROUTES = {
    "direct_answer",
    "clarification_required",
    "quick_tool_use",
    "memory_retrieval",
    "shell_agent_flow",
    "research_agent",
    "task_queue",
    "approval_required",
    "refuse_redirect",
}
GATED_ROUTES = {"approval_required", "refuse_redirect"}

TOKEN_RE = re.compile(r"[a-z0-9_./:-]+")

@dataclass(frozen=True)
class SignalSet:
    name: str
    phrases: tuple[str, ...]
    tokens: tuple[str, ...] = ()


SIGNALS = [
    SignalSet(
        "refuse_unsafe",
        (
            "bypass captcha",
            "omzeil captcha",
            "captcha omzeilen",
            "evade detection",
            "detectie ontwijken",
            "stealth scrape",
            "scrape zonder rate limit",
            "hack account",
            "phishing",
            "malware",
            "keylogger",
            "ddos",
            "dox",
            "geef me iemands wachtwoord",
            "wachtwoord uit de env",
            "password from env",
            "secret exfiltration",
            "stuur spam",
            "send spam",
            "rm -rf",
            "home directory",
            "credential stealer",
            "scrape agressief",
            "scrape aggressive",
        ),
    ),
    SignalSet(
        "money_or_purchase",
        (
            "koop ",
            "buy ",
            "betaal",
            "pay ",
            "bied ",
            "place bid",
            "trade ",
            "withdraw",
            "bank",
            "paypal",
            "crypto sturen",
            "ticket kopen",
            "buy it",
            "koop het",
        ),
    ),
    SignalSet(
        "external_write",
        (
            "stuur email",
            "stuur deze mail",
            "stuur mail",
            "stuur het",
            "send email",
            "send it",
            "mail versturen",
            "post dit",
            "publiceer",
            "publish",
            "publish it",
            "create pull request",
            "merge pull request",
            "push naar",
            "delete ",
            "delete it",
            "verwijder ",
            "verwijder dat",
            "restart server",
            "herstart server",
            "herstart mijn server",
            "wijzig dns",
            "change dns",
            "firewall",
            "koppel account",
            "koppel mijn",
            "connect account",
            "maak afspraak",
            "create calendar event",
            "calendar events",
            "agenda afspraak maken",
        ),
    ),
    SignalSet(
        "install_or_infra",
        (
            "installeer",
            "install ",
            "docker run",
            "apt install",
            "pip install",
            "npm install",
            "driver installeren",
            "cuda installeren",
            "model downloaden",
            "download model",
            "download een groot lokaal model",
            "gpu job",
            "install it",
            "installeer het",
        ),
    ),
    SignalSet(
        "research",
        (
            "onderzoek",
            "research",
            "vergelijk",
            "compare",
            "beste aanpak",
            "best approach",
            "bronnen",
            "sources",
            "github repo",
            "mcp server",
            "literature",
            "marktonderzoek",
        ),
    ),
    SignalSet(
        "queue",
        (
            "vannacht",
            "later",
            "morgen",
            "monitor",
            "blijf kijken",
            "ochtendrapport",
            "nightly",
            "schedule this",
            "plan elke week",
            "elke week",
            "wacht tot",
            "zet in queue",
            "task queue",
        ),
    ),
    SignalSet(
        "quick_read_tool",
        (
            "check mijn",
            "lees mijn",
            "status van",
            "wat staat er in",
            "calendar read",
            "agenda lezen",
            "weer",
            "weather",
            "zoek in bestanden",
            "git status",
            "nieuwe lokale task",
            "lokale task",
            "open approvals",
            "audit hash-chain",
            "openai_api_key aanwezig",
        ),
    ),
    SignalSet(
        "memory_retrieval",
        (
            "zoek in memory",
            "zoek in geheugen",
            "gebruik memory",
            "gebruik geheugen",
            "haal uit memory",
            "haal uit geheugen",
            "wat weet je nog over",
            "wat weet leon nog over",
            "wat heb je onthouden over",
            "remembered context",
            "retrieve memory",
            "memory retrieval",
        ),
    ),
    SignalSet(
        "coding",
        (
            "bouw",
            "build",
            "debug",
            "fix",
            "maak script",
            "tool maken",
            "api endpoint",
            "test schrijven",
        ),
    ),
    SignalSet(
        "simple_answer",
        (
            "leg uit",
            "explain",
            "samenvat",
            "summarize",
            "wat is",
            "hoe werkt",
            "schrijf een korte",
        ),
    ),
]


@dataclass
class Decision:
    input_text_redacted: str
    route: str
    intent: str
    task_type: str
    complexity: str
    risk_level: str
    risk_class: str
    policy_decision: str
    privacy_level: str
    urgency: str
    value_score: int
    value_score_inputs: dict[str, Any]
    value_band: dict[str, Any]
    retrieved_context: dict[str, Any]
    execution_path: dict[str, Any]
    approval_required: bool
    approval_reason: str
    clarification_required: bool
    clarification_questions: list[str]
    ambiguity_reasons: list[str]
    external_effect: str
    recommended_task_status: str
    estimated_duration_seconds: int
    needs_sources: bool
    requires_tool: bool
    required_tools: list[str]
    expected_output: dict[str, Any]
    confidence: float
    reasons: list[str] = field(default_factory=list)
    matched_signals: list[str] = field(default_factory=list)
    model_route: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_text_redacted": self.input_text_redacted,
            "route": self.route,
            "intent": self.intent,
            "task_type": self.task_type,
            "complexity": self.complexity,
            "risk_level": self.risk_level,
            "risk_class": self.risk_class,
            "policy_decision": self.policy_decision,
            "privacy_level": self.privacy_level,
            "urgency": self.urgency,
            "value_score": self.value_score,
            "value_score_inputs": self.value_score_inputs,
            "value_band": self.value_band,
            "retrieved_context": self.retrieved_context,
            "execution_path": self.execution_path,
            "approval_required": self.approval_required,
            "approval_reason": self.approval_reason,
            "clarification_required": self.clarification_required,
            "clarification_questions": self.clarification_questions,
            "ambiguity_reasons": self.ambiguity_reasons,
            "external_effect": self.external_effect,
            "recommended_task_status": self.recommended_task_status,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "needs_sources": self.needs_sources,
            "requires_tool": self.requires_tool,
            "required_tools": self.required_tools,
            "expected_output": self.expected_output,
            "safe_to_execute": self.policy_decision == "autonomous"
            and not self.clarification_required
            and not self.approval_required
            and self.route not in {"refuse_redirect"},
            "confidence": self.confidence,
            "reasons": self.reasons,
            "matched_signals": self.matched_signals,
            "model_route": self.model_route,
            "approval_payload": build_approval_payload(self) if self.approval_required else None,
        }


def redact_sensitive_text(text: str) -> str:
    return redact_text(text)


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def text_tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(normalize(text)))


def collect_signals(text: str) -> list[str]:
    lowered = normalize(text)
    tokens = text_tokens(lowered)
    matched: list[str] = []
    for signal in SIGNALS:
        if any(phrase in lowered for phrase in signal.phrases) or any(token in tokens for token in signal.tokens):
            matched.append(signal.name)
    return matched


def infer_complexity(text: str, matched: set[str]) -> str:
    tokens = text_tokens(text)
    if "research" in matched or "coding" in matched:
        return "medium"
    if any(token in tokens for token in {"architectuur", "architecture", "multi-agent", "security", "audit", "gpu", "cuda"}):
        return "high"
    if len(tokens) <= 8 and not matched.intersection({"money_or_purchase", "external_write", "install_or_infra"}):
        return "low"
    if len(tokens) >= 28:
        return "high"
    return "medium"


def infer_risk(matched: set[str], text: str) -> str:
    if "refuse_unsafe" in matched:
        return "high"
    if matched.intersection({"money_or_purchase", "external_write", "install_or_infra"}):
        return "high"
    lowered = normalize(text)
    if any(item in lowered for item in ("api key", "secret", "wachtwoord", "password", "persoonlijke data")):
        return "medium"
    return "low"


def infer_urgency(matched: set[str], text: str) -> str:
    lowered = normalize(text)
    if "queue" in matched:
        return "low"
    if any(item in lowered for item in ("nu", "direct", "urgent", "asap", "meteen")):
        return "high"
    return "normal"


def infer_task_type(route: str, matched: set[str], complexity: str) -> str:
    if route == "refuse_redirect":
        return "security_review"
    if route == "clarification_required":
        return "classification"
    if route == "memory_retrieval":
        return "extraction"
    if route == "shell_agent_flow":
        return "debugging" if any(signal in matched for signal in {"coding"}) and complexity != "high" else "tool_making"
    if route == "approval_required":
        return "high_value_decision"
    if "coding" in matched:
        return "tool_making"
    if route == "research_agent":
        return "routine_research" if complexity != "high" else "architecture"
    if route == "task_queue":
        return "documentation"
    return "general"


def infer_ambiguity(text: str, matched: set[str]) -> list[str]:
    lowered = normalize(text)
    plain = re.sub(r"[^\w\s]", "", lowered, flags=re.UNICODE)
    tokens = text_tokens(text).union(set(plain.split()))
    ambiguous_phrases = {
        "do it",
        "do that",
        "handle this",
        "make it work",
        "run it",
        "send it",
        "delete it",
        "publish it",
        "continue",
        "ga verder",
        "doe het",
        "doe dat",
        "regel dit",
        "regel dat",
        "maak het af",
        "fix dit",
        "fix dat",
        "voer het uit",
        "stuur het",
        "verwijder dat",
        "publiceer dit",
    }
    action_tokens = {
        "do",
        "doe",
        "regel",
        "handle",
        "make",
        "run",
        "voer",
        "send",
        "stuur",
        "delete",
        "verwijder",
        "publish",
        "publiceer",
        "fix",
        "maak",
        "install",
        "installeer",
    }
    pronouns = {"it", "that", "this", "these", "those", "dit", "dat", "het", "deze", "die"}
    reasons: list[str] = []
    if lowered in ambiguous_phrases or plain in ambiguous_phrases:
        reasons.append("Request uses a vague action phrase without a concrete object, scope, or success condition.")
    if len(tokens) <= 5 and tokens.intersection(action_tokens) and tokens.intersection(pronouns):
        reasons.append("Request is too short to identify the target, context, and desired outcome.")
    return sorted(set(reasons))


def _score_item(points: int, reason: str) -> dict[str, Any]:
    return {"points": points, "reason": reason}


def summarize_retrieved_context(memory_context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(memory_context, dict):
        return {
            "applied": False,
            "query_id": "",
            "answer_status": "not_requested",
            "confidence": 0,
            "relevance_score": 0,
            "match_count": 0,
            "source_refs": [],
            "related_graph_entries": [],
            "conflicts": [],
            "influence": {
                "routing": "none",
                "prioritization_points": 0,
                "brief_generation": "available_when_brief_uses_this_context",
                "reason": "No memory or knowledge graph context was supplied.",
            },
            "provenance_required": True,
        }
    metrics = memory_context.get("metrics") if isinstance(memory_context.get("metrics"), dict) else {}
    try:
        relevance_score = float(metrics.get("relevance_score", memory_context.get("relevance_score") or 0))
    except (TypeError, ValueError):
        relevance_score = 0
    try:
        confidence = float(memory_context.get("confidence") or metrics.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0
    try:
        match_count = int(metrics.get("match_count", memory_context.get("match_count") or 0))
    except (TypeError, ValueError):
        match_count = 0
    source_refs = memory_context.get("source_refs") if isinstance(memory_context.get("source_refs"), list) else []
    related_graph_entries = (
        memory_context.get("related_graph_entries") if isinstance(memory_context.get("related_graph_entries"), list) else []
    )
    conflicts = memory_context.get("conflicts") if isinstance(memory_context.get("conflicts"), list) else []
    applied = (
        str(memory_context.get("answer_status") or "") == "answered"
        and bool(source_refs)
        and match_count > 0
        and relevance_score >= 0.12
    )
    prioritization_points = 0
    if applied:
        prioritization_points = 8
        if relevance_score >= 0.4:
            prioritization_points += 4
        if confidence >= 0.8:
            prioritization_points += 2
        if related_graph_entries:
            prioritization_points += 2
    return {
        "applied": applied,
        "query_id": str(memory_context.get("id") or ""),
        "answer_status": str(memory_context.get("answer_status") or ""),
        "confidence": round(max(0, min(confidence, 1)), 4),
        "relevance_score": round(max(0, min(relevance_score, 1)), 4),
        "match_count": match_count,
        "memory_match_count": int(metrics.get("memory_match_count") or 0),
        "source_match_count": int(metrics.get("source_match_count") or 0),
        "source_refs": source_refs[:8],
        "related_graph_entries": related_graph_entries[:10],
        "conflicts": conflicts[:5],
        "influence": {
            "routing": "eligible_for_memory_informed_route" if applied else "none",
            "prioritization_points": prioritization_points,
            "brief_generation": "eligible_for_brief_context_card" if applied else "not_used",
            "reason": (
                "Relevant memory/source context with provenance was supplied and can safely inform this decision."
                if applied
                else "Retrieved context was absent or below the relevance threshold."
            ),
        },
        "provenance_required": True,
    }


def infer_value_score_inputs(
    *,
    route: str,
    matched: set[str],
    complexity: str,
    urgency: str,
    risk: str,
    text: str,
    retrieved_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lowered = normalize(text)
    goal_relevance = {
        "direct_answer": 26,
        "clarification_required": 12,
        "quick_tool_use": 30,
        "memory_retrieval": 32,
        "shell_agent_flow": 36,
        "research_agent": 34,
        "task_queue": 30,
        "approval_required": 36,
        "refuse_redirect": 0,
    }.get(route, 18)
    expected_time_saved = {
        "direct_answer": 18,
        "clarification_required": 6,
        "quick_tool_use": 22,
        "memory_retrieval": 24,
        "shell_agent_flow": 30,
        "research_agent": 26,
        "task_queue": 20,
        "approval_required": 28,
        "refuse_redirect": 0,
    }.get(route, 12)
    reuse_or_learning = {
        "direct_answer": 8,
        "clarification_required": 0,
        "quick_tool_use": 12,
        "memory_retrieval": 16,
        "shell_agent_flow": 22,
        "research_agent": 18,
        "task_queue": 14,
        "approval_required": 16,
        "refuse_redirect": 0,
    }.get(route, 6)
    if "coding" in matched:
        reuse_or_learning += 8
        expected_time_saved += 6
    if complexity == "high":
        expected_time_saved += 4
        reuse_or_learning += 4
    urgency_points = 0 if route == "refuse_redirect" else {"high": 12, "normal": 6, "low": 2}.get(urgency, 6)
    risk_penalty = {"low": 0, "medium": -8, "high": -24}.get(risk, -8)
    cost_penalty = 0
    if route == "research_agent":
        cost_penalty -= 4
    if "install_or_infra" in matched or any(item in lowered for item in ("gpu", "model downloaden", "download model")):
        cost_penalty -= 12
    if "money_or_purchase" in matched:
        cost_penalty -= 10
    maintenance_penalty = 0
    if "coding" in matched or "install_or_infra" in matched:
        maintenance_penalty -= 6
    if "queue" in matched:
        maintenance_penalty -= 3
    if "external_write" in matched:
        maintenance_penalty -= 4
    components = {
        "user_goal_relevance": _score_item(goal_relevance, f"{route} route matches the user's requested outcome."),
        "expected_time_saved": _score_item(expected_time_saved, f"{route} work would save manual operator time."),
        "reuse_or_learning_value": _score_item(reuse_or_learning, f"{route} work can create reusable knowledge, task state, or repeatable process."),
        "urgency": _score_item(urgency_points, f"Urgency classified as {urgency}."),
        "risk_penalty": _score_item(risk_penalty, f"Risk classified as {risk}."),
        "cost_or_resource_penalty": _score_item(cost_penalty, "Estimated external, model, GPU, purchase, or install cost/resource load."),
        "maintenance_penalty": _score_item(maintenance_penalty, "Follow-up maintenance or operational burden implied by the request."),
    }
    if isinstance(retrieved_context, dict) and retrieved_context.get("applied"):
        points = int((retrieved_context.get("influence") or {}).get("prioritization_points") or 0)
        if points:
            components["memory_context_relevance"] = _score_item(
                points,
                "Relevant reviewed memory/source context matched the request and includes provenance.",
            )
    raw_score = sum(item["points"] for item in components.values())
    score = max(0, min(100, raw_score))
    return {
        "components": components,
        "raw_score": raw_score,
        "score": score,
        "formula": "sum additive score components; negative components are penalties",
    }


def value_band_for_score(
    *,
    score: int,
    route: str,
    risk: str,
    policy_decision: str,
    approval_required: bool,
    clarification_required: bool,
) -> dict[str, Any]:
    if score <= 24:
        band = {"id": "ignored", "min": 0, "max": 24, "handling": "ignored"}
    elif score <= 49:
        band = {"id": "queued", "min": 25, "max": 49, "handling": "queued"}
    elif score <= 69:
        band = {"id": "proposed", "min": 50, "max": 69, "handling": "proposed"}
    elif score <= 89:
        band = {"id": "executed", "min": 70, "max": 89, "handling": "executed"}
    else:
        band = {"id": "held_for_approval", "min": 90, "max": 100, "handling": "held_for_approval"}

    reason = f"Score {score} falls in {band['min']}-{band['max']}."
    handling = str(band["handling"])
    if route == "refuse_redirect":
        handling = "ignored"
        reason = "Unsafe or disallowed work is ignored/refused before task creation."
    elif clarification_required:
        handling = "proposed"
        reason = "Ambiguous work is limited to a clarification proposal regardless of score."
    elif approval_required or risk == "high" or policy_decision in {"blocked", "needs_review"}:
        handling = "held_for_approval"
        reason = "Risk policy requires review or approval before execution regardless of score."
    elif route == "task_queue":
        handling = "queued"
        reason = "Deferred or scheduled work is queued even when the score is high."
    elif handling == "executed" and route not in {"direct_answer", "quick_tool_use", "memory_retrieval"}:
        handling = "proposed"
        reason = "High-value multi-step work is proposed first because this route is not an immediate safe execution path."
    elif handling == "executed":
        reason = "High-value, low-risk work can be handled immediately by the selected safe path."

    return {
        **band,
        "handling": handling,
        "label": handling.replace("_", " "),
        "reason": reason,
    }


def infer_required_tools(route: str, matched: set[str]) -> list[str]:
    if route in {"direct_answer", "clarification_required", "refuse_redirect"}:
        return []
    tools: list[str] = []
    if route == "quick_tool_use":
        tools.append("local_read_only_control_plane_tool")
    if route == "memory_retrieval":
        tools.extend(["memory_retrieval", "source_provenance_filter"])
    if route == "shell_agent_flow":
        tools.extend(["local_workspace", "shell_agent_runner"])
    if route == "research_agent":
        tools.extend(["approved_research_tool", "source_review"])
    if route == "task_queue":
        tools.append("local_task_queue")
    if route == "approval_required":
        tools.append("approval_flow")
        if "money_or_purchase" in matched:
            tools.append("payment_or_purchase_tool_after_approval")
        if "external_write" in matched:
            tools.append("external_connector_after_approval")
        if "install_or_infra" in matched:
            tools.append("package_or_infrastructure_tool_after_approval")
    return tools


def infer_expected_output(route: str, intent: str, needs_sources: bool) -> dict[str, Any]:
    outputs = {
        "direct_answer": ("chat_answer", "A concise direct response in chat."),
        "clarification_required": ("clarification_questions", "One or more questions that identify scope, context, and desired outcome before any work is planned."),
        "quick_tool_use": ("bounded_tool_result", "A read-only local/status result with no secret values exposed."),
        "memory_retrieval": ("source_backed_memory_answer", "A memory-backed answer with provenance, conflicts, and no raw secret values."),
        "shell_agent_flow": ("reviewable_agent_plan", "A shell/agent task proposal with bounded scope, allowed actions, forbidden actions, and verification."),
        "research_agent": ("sourced_research_summary", "A sourced comparison or recommendation with assumptions and next steps."),
        "task_queue": ("queued_task_proposal", "A planned task with owner, priority, risk, and acceptance criteria."),
        "approval_required": ("approval_packet", "A reviewable approval packet with expected effect, risk, rollback, and failure mode."),
        "refuse_redirect": ("safe_refusal", "A refusal plus a safe alternative request the assistant can help with."),
    }
    output_type, description = outputs.get(route, ("classification_record", "A structured classification record."))
    return {
        "type": output_type,
        "description": description,
        "intent": intent,
        "requires_sources": needs_sources,
    }


def infer_execution_path(
    *,
    route: str,
    task_type: str,
    required_tools: list[str],
    approval_required: bool,
    clarification_required: bool,
    model_route: dict[str, Any],
) -> dict[str, Any]:
    path_by_route = {
        "direct_answer": ("local_handling", "answer_in_chat", "Handle locally in chat without a task, tool, or approval."),
        "quick_tool_use": ("local_tool", "bounded_local_tool_preview", "Use a read-only local/control-plane tool after review."),
        "memory_retrieval": ("memory_retrieval", "retrieve_memory_with_provenance", "Retrieve reviewed memory/source records and show provenance."),
        "shell_agent_flow": ("shell_agent_flow", "create_agent_task", "Create a bounded shell/agent task; do not execute it from routing."),
        "research_agent": ("agent_flow", "create_research_task", "Create a sourced research-agent task."),
        "task_queue": ("queue", "create_queued_task", "Create a deferred local queue item."),
        "approval_required": ("approval", "create_approval_gate", "Prepare a task and approval packet before any high-impact action."),
        "clarification_required": ("clarification", "ask_clarification", "Ask for missing context before planning work."),
        "refuse_redirect": ("safe_refusal", "refuse_and_redirect", "Refuse unsafe work and offer a safe alternative."),
    }
    path_type, next_step, reason = path_by_route.get(route, ("unknown", "review_only", "Unknown route; review before action."))
    return {
        "type": path_type,
        "next_step": next_step,
        "agent_role": {
            "memory_retrieval": "Memory Agent",
            "shell_agent_flow": "Code/Improvement Agent",
            "research_agent": "Research Agent",
            "task_queue": "Queue Agent",
            "approval_required": "Codex/User",
        }.get(route),
        "task_type": task_type,
        "required_tools": required_tools,
        "model_route": model_route.get("route"),
        "model": model_route.get("model"),
        "selected_runtime": model_route.get("selected_runtime"),
        "approval_required": approval_required,
        "clarification_required": clarification_required,
        "execution_allowed_now": (
            route in {"direct_answer", "quick_tool_use", "memory_retrieval"}
            and not approval_required
            and not clarification_required
        ),
        "reason": reason,
    }


def build_clarification_questions(matched: set[str]) -> list[str]:
    questions = ["What exact outcome do you want Leon to produce?"]
    if matched.intersection({"money_or_purchase", "external_write", "install_or_infra"}):
        questions.append("Which system, account, file, or external target would be affected?")
        questions.append("Should Leon only prepare a plan, or are you asking for an action that will need approval?")
    else:
        questions.append("What context or input should Leon use?")
    return questions


def classify_user_request(
    text: str,
    *,
    budget_mode: str = "balanced",
    privacy: str = "normal",
    local_gpu_ready: bool = False,
    local_route_status: str = "",
    local_latency_ms: float | int | str | None = None,
    memory_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_text = text.strip()
    if not raw_text:
        raise ValueError("Decision Layer requires non-empty text")

    matched = set(collect_signals(raw_text))
    ambiguity_reasons = infer_ambiguity(raw_text, matched)
    complexity = infer_complexity(raw_text, matched)
    urgency = infer_urgency(matched, raw_text)
    retrieved_context = summarize_retrieved_context(memory_context)
    reasons: list[str] = []

    if "refuse_unsafe" in matched:
        route = "refuse_redirect"
        intent = "unsafe_or_disallowed_request"
        reasons.append("Request contains unsafe evasion, abuse, malware, phishing, or account-compromise signals.")
    elif ambiguity_reasons:
        route = "clarification_required"
        intent = "ambiguous_request"
        reasons.append("Request is ambiguous; Leon must clarify intent, context, and desired outcome before planning work.")
    elif matched.intersection({"money_or_purchase", "external_write", "install_or_infra"}):
        route = "approval_required"
        intent = "external_or_high_risk_side_effect"
        reasons.append("Request may spend money, change external systems, install software, or write outside the local safe scope.")
    elif "queue" in matched:
        route = "task_queue"
        intent = "deferred_or_monitoring_work"
        reasons.append("Request is explicitly deferred, recurring, or suitable for a queued background task.")
    elif "memory_retrieval" in matched:
        route = "memory_retrieval"
        intent = "memory_backed_context_lookup"
        reasons.append("Request asks Leon to use reviewed memory or knowledge-graph context.")
    elif "research" in matched:
        route = "research_agent"
        intent = "research_or_comparison"
        reasons.append("Request asks for research, comparison, sources, or repo/tool evaluation.")
    elif "quick_read_tool" in matched:
        route = "quick_tool_use"
        intent = "read_only_tool_lookup"
        reasons.append("Request is a bounded read-only lookup or status check.")
    elif "coding" in matched:
        route = "shell_agent_flow"
        intent = "local_code_or_shell_agent_work"
        reasons.append("Request asks for code, debugging, script, or repo work that should become a bounded shell/agent flow.")
    else:
        route = "direct_answer"
        intent = "direct_response"
        reasons.append("Request can be handled directly without tools, background work, or side effects.")

    if retrieved_context["applied"] and route == "direct_answer":
        route = "memory_retrieval"
        intent = "memory_informed_context_lookup"
        retrieved_context["influence"]["routing"] = "direct_answer_to_memory_retrieval"
        reasons.append("Relevant reviewed memory or knowledge-graph context changed the route to source-backed retrieval.")
    elif retrieved_context["applied"]:
        retrieved_context["influence"]["routing"] = f"{route}_kept_with_memory_context"

    task_type = infer_task_type(route, matched, complexity)
    policy = classify_request_policy(route=route, matched_signals=matched, text=raw_text)
    risk = policy["coarse_risk_level"]
    approval_required = route == "approval_required" or (
        route != "clarification_required" and bool(policy["approval_required"])
    )
    value_score_inputs = infer_value_score_inputs(
        route=route,
        matched=matched,
        complexity=complexity,
        urgency=urgency,
        risk=risk,
        text=raw_text,
        retrieved_context=retrieved_context,
    )
    value_score = int(value_score_inputs["score"])
    needs_sources = route in {"research_agent", "memory_retrieval"}
    required_tools = infer_required_tools(route, matched)
    requires_tool = bool(required_tools)
    clarification_required = route == "clarification_required"
    clarification_questions = build_clarification_questions(matched) if clarification_required else []
    expected_output = infer_expected_output(route, intent, needs_sources)
    external_effect = "blocked_until_approval" if approval_required else "none"
    approval_reason = ""
    recommended_task_status = "none"
    if route == "refuse_redirect":
        external_effect = "none_refuse_and_offer_safe_alternative"
        recommended_task_status = "none"
    elif route == "clarification_required":
        external_effect = "none_clarification_only"
        recommended_task_status = "clarification_needed"
    elif route in {"memory_retrieval", "shell_agent_flow"}:
        recommended_task_status = "planned"
    elif route == "task_queue":
        recommended_task_status = "planned"
    elif route == "research_agent":
        recommended_task_status = "planned"
    elif route == "approval_required":
        approval_reason = reasons[0]
        recommended_task_status = "waiting_for_approval"
    if policy["decision"] == "blocked" and route not in {"refuse_redirect", "clarification_required"}:
        external_effect = "blocked_by_risk_policy"
        recommended_task_status = "blocked"
        approval_reason = policy["reason"]
    elif policy["decision"] == "needs_review" and route not in {"approval_required", "clarification_required"}:
        recommended_task_status = "waiting_for_approval" if policy["approval_required"] else "review"
        approval_reason = policy["reason"]
    value_band = value_band_for_score(
        score=value_score,
        route=route,
        risk=risk,
        policy_decision=str(policy["decision"]),
        approval_required=approval_required,
        clarification_required=clarification_required,
    )
    if value_band["handling"] == "ignored":
        recommended_task_status = "none"
    elif value_band["handling"] == "queued" and recommended_task_status == "none":
        recommended_task_status = "queued"
    elif value_band["handling"] == "held_for_approval" and recommended_task_status not in {"blocked", "clarification_needed"}:
        recommended_task_status = "waiting_for_approval"
    estimated_duration_seconds = {
        "direct_answer": 20,
        "clarification_required": 45,
        "quick_tool_use": 90,
        "memory_retrieval": 120,
        "shell_agent_flow": 240,
        "research_agent": 900,
        "task_queue": 300,
        "approval_required": 120,
        "refuse_redirect": 30,
    }[route]
    confidence = 0.92 if matched else 0.72
    if route in {"approval_required", "refuse_redirect"}:
        confidence = 0.95
    if clarification_required:
        confidence = 0.48

    model_route = choose_route(
        task_type=task_type,
        complexity=complexity,
        risk=risk,
        budget_mode=budget_mode,
        privacy=privacy,
        local_gpu_ready=local_gpu_ready,
        local_route_status=local_route_status,
        local_latency_ms=local_latency_ms,
    )
    if approval_required:
        model_route["approval_required"] = True
    execution_path = infer_execution_path(
        route=route,
        task_type=task_type,
        required_tools=required_tools,
        approval_required=approval_required,
        clarification_required=clarification_required,
        model_route=model_route,
    )

    decision = Decision(
        input_text_redacted=redact_sensitive_text(raw_text),
        route=route,
        intent=intent,
        task_type=task_type,
        complexity=complexity,
        risk_level=risk,
        risk_class=str(policy["risk_class"]),
        policy_decision=str(policy["decision"]),
        privacy_level=privacy,
        urgency=urgency,
        value_score=value_score,
        value_score_inputs=value_score_inputs,
        value_band=value_band,
        retrieved_context=retrieved_context,
        execution_path=execution_path,
        approval_required=approval_required,
        approval_reason=approval_reason,
        clarification_required=clarification_required,
        clarification_questions=clarification_questions,
        ambiguity_reasons=ambiguity_reasons,
        external_effect=external_effect,
        recommended_task_status=recommended_task_status,
        estimated_duration_seconds=estimated_duration_seconds,
        needs_sources=needs_sources,
        requires_tool=requires_tool,
        required_tools=required_tools,
        expected_output=expected_output,
        confidence=confidence,
        reasons=reasons,
        matched_signals=sorted(matched),
        model_route=model_route,
    )
    output = decision.to_dict()
    output["risk_policy"] = policy
    return output


def build_approval_payload(decision: Decision) -> dict[str, Any]:
    summary = decision.input_text_redacted[:120]
    external_effect = "write"
    if "money_or_purchase" in decision.matched_signals:
        external_effect = "financial"
    if "install_or_infra" in decision.matched_signals:
        external_effect = "destructive" if "verwijder" in normalize(decision.input_text_redacted) else "write"
    return {
        "action_type": "routing_gate",
        "summary": summary,
        "reason": decision.approval_reason or "High-impact action requires explicit approval before execution.",
        "affected_systems": "Unknown until a bounded execution plan is reviewed.",
        "permissions": "No execution permission granted by this routing decision.",
        "external_effect": external_effect,
        "cost_estimate": "unknown until reviewed",
        "risk_level": decision.risk_level,
        "risk_class": decision.risk_class,
        "policy_decision": decision.policy_decision,
        "expected_change": f"Prepare a bounded plan for: {summary}",
        "rollback_plan": "No action has been executed. Reject or revise the proposed execution plan.",
        "failure_mode": "If approval is rejected or expires, no action runs; the plan must be changed before retry.",
    }


def load_eval_cases(path: Path = DEFAULT_EVAL_PATH) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        cases = json.load(handle)
    if not isinstance(cases, list):
        raise ValueError("Routing eval file must contain a list")
    return cases


def routing_logic_fingerprint(cases: list[dict[str, Any]] | None = None) -> str:
    payload = {
        "routes": sorted(ROUTES),
        "signals": [
            {
                "name": signal.name,
                "phrases": list(signal.phrases),
                "tokens": list(signal.tokens),
            }
            for signal in SIGNALS
        ],
        "case_ids": [str(case.get("id") or "") for case in cases or []],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _is_safety_failure(expected_route: str, actual_route: str) -> bool:
    if expected_route == "refuse_redirect":
        return actual_route != "refuse_redirect"
    if expected_route == "approval_required":
        return actual_route not in GATED_ROUTES
    return False


def evaluate_cases(cases: list[dict[str, Any]], *, release_label: str = "working-tree") -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        text = str(case.get("input", ""))
        expected_route = str(case.get("expected_route", ""))
        decision = classify_user_request(text)
        passed = decision["route"] == expected_route
        safety_failure = _is_safety_failure(expected_route, decision["route"])
        results.append(
            {
                "case_id": case.get("id") or f"case-{index}",
                "input": text,
                "expected_route": expected_route,
                "actual_route": decision["route"],
                "passed": passed,
                "safety_failure": safety_failure,
                "risk_level": decision["risk_level"],
                "risk_class": decision["risk_class"],
                "approval_required": decision["approval_required"],
                "model_route": decision["model_route"]["route"],
                "matched_signals": decision["matched_signals"],
                "reasons": decision["reasons"],
                "source": case.get("source") or "eval",
                "misroute_note": case.get("misroute_note") or "",
            }
        )
    passed_count = sum(1 for item in results if item["passed"])
    misroute_case_count = sum(1 for item in results if item.get("source") == "misroute_regression")
    safety_cases = [item for item in results if item["expected_route"] in GATED_ROUTES]
    safety_failures = [item for item in results if item["safety_failure"]]
    route_counts: dict[str, int] = {}
    for item in results:
        route_counts[str(item["actual_route"])] = route_counts.get(str(item["actual_route"]), 0) + 1
    return {
        "ok": passed_count == len(results),
        "release_label": release_label,
        "decision_logic": {
            "logic_fingerprint": routing_logic_fingerprint(cases),
            "case_count": len(results),
        },
        "routing_quality": {
            "accuracy": round(passed_count / len(results), 4) if results else 1.0,
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "failed_case_ids": [str(item["case_id"]) for item in results if not item["passed"]],
            "actual_route_counts": route_counts,
        },
        "routing_safety": {
            "safety_case_count": len(safety_cases),
            "safety_failures": len(safety_failures),
            "safety_ok": len(safety_failures) == 0,
            "safety_failure_case_ids": [str(item["case_id"]) for item in safety_failures],
            "approval_false_negative_count": sum(
                1 for item in safety_failures if item["expected_route"] == "approval_required"
            ),
            "refusal_false_negative_count": sum(
                1 for item in safety_failures if item["expected_route"] == "refuse_redirect"
            ),
        },
        "passed": passed_count,
        "total": len(results),
        "failed": len(results) - passed_count,
        "misroute_case_count": misroute_case_count,
        "results": results,
    }
