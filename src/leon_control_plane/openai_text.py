"""Bounded Responses transport. No SDK retries, redirects, tools or implicit context."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import http.client
import json
import os
from pathlib import Path

from leon_control_plane.model_policy import choose_route
from leon_control_plane.secret_scanner import assert_no_secrets, redact_text

MODEL = "gpt-5.6-luna"
KIND = "openai_text"
MAX_INPUT_BYTES = 4096
MAX_OUTPUT_TOKENS = 1024
PRICE_VALID_UNTIL = date(2026, 10, 7)


class ModelPreflightError(ValueError):
    """Fixed local reason codes; never carries provider content or secret values."""


def positive_int(value, label, maximum=1_000_000_000):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"Invalid {label}")
    return value


@dataclass(frozen=True)
class OpenAIConfig:
    enabled: bool = False
    api_key: str = field(default="", repr=False)
    daily_microusd: int = 0
    total_microusd: int = 0

    @classmethod
    def from_env(cls, *, env_file: Path | None = None):
        keys = {"OPENAI_API_KEY", "LEON_OPENAI_ENABLED", "LEON_OPENAI_DAILY_MICROUSD", "LEON_OPENAI_TOTAL_MICROUSD"}
        values = {}
        if env_file is not None:
            try:
                if env_file.is_symlink():
                    raise ValueError()
                with env_file.open("r", encoding="utf-8-sig") as handle:
                    content = handle.read(65537)
                if len(content) > 65536:
                    raise ValueError()
                for line in content.splitlines():
                    key, separator, value = line.partition("=")
                    if separator and key.strip() in keys:
                        value = value.strip()
                        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                            value = value[1:-1]
                        values[key.strip()] = value
            except (OSError, ValueError):
                raise ModelPreflightError("openai_env_file_unavailable") from None
        values.update({key: os.environ[key] for key in keys if key in os.environ})
        def number(name):
            try:
                return int(values.get(name, "0"))
            except ValueError:
                return 0
        return cls(values.get("LEON_OPENAI_ENABLED") == "1",
                   values.get("OPENAI_API_KEY", ""),
                   number("LEON_OPENAI_DAILY_MICROUSD"), number("LEON_OPENAI_TOTAL_MICROUSD"))

    def validate(self):
        if not self.enabled:
            raise ModelPreflightError("openai_disabled")
        if not self.api_key or any(c.isspace() for c in self.api_key):
            raise ModelPreflightError("openai_credentials_missing")
        try:
            positive_int(self.daily_microusd, "daily budget")
            positive_int(self.total_microusd, "total budget")
        except ValueError:
            raise ModelPreflightError("openai_budget_not_configured") from None
        if date.today() > PRICE_VALID_UNTIL:
            raise ModelPreflightError("openai_tariff_review_required")


def request_payload(prompt, max_output_tokens):
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode("utf-8")) > MAX_INPUT_BYTES:
        raise ValueError("Expected 1..4096 UTF-8 bytes of explicitly shared text")
    assert_no_secrets("Shared text", prompt)
    positive_int(max_output_tokens, "output limit", MAX_OUTPUT_TOKENS)
    route = choose_route(task_type="classification", complexity="low", risk="low", budget_mode="economy")
    if (route["provider"], route["route"], route["model"]) != ("openai", "cheap", MODEL) or route["approval_required"]:
        raise ValueError("Configured cheap model requires a new execution/pricing review")
    return {"model": MODEL, "input": prompt, "max_output_tokens": max_output_tokens,
            "reasoning": {"effort": "low"}, "store": False, "stream": False,
            "tools": [], "tool_choice": "none", "truncation": "disabled", "service_tier": "default"}


def cost_microusd(input_tokens, output_tokens):
    # Integer arithmetic, rounded UP. Input includes worst-case cache writes;
    # output includes reasoning. Never mistake the router's estimate for usage.
    return (input_tokens * 250 + output_tokens * 1200 + 999) // 1000


def reservation(payload):
    return cost_microusd(len(payload["input"].encode("utf-8")) + 1024, payload["max_output_tokens"])


def send_response(payload, api_key):
    """Exactly one HTTP attempt; exceptions must not escape into logs/results."""
    conn = http.client.HTTPSConnection("api.openai.com", timeout=20)
    try:
        conn.request("POST", "/v1/responses", json.dumps(payload).encode("utf-8"),
                     {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        response = conn.getresponse()
        raw = response.read(262145)
        if response.status != 200 or len(raw) > 262144:
            raise ValueError("Provider outcome could not be verified")
        return json.loads(raw)
    finally:
        conn.close()


def parse_usage(data, payload):
    """Validate final usage separately from answer content; never a billing invoice."""
    if not isinstance(data, dict) or data.get("model") != MODEL:
        raise ValueError("Unexpected response model")
    if data.get("status") not in {"completed", "incomplete"} or data.get("error"):
        raise ValueError("Unverified provider status")
    usage = data.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("Missing provider usage")
    counts = [usage.get("input_tokens"), usage.get("output_tokens")]
    if any(type(count) is not int or count < 0 for count in counts):
        raise ValueError("Invalid provider usage")
    if counts[0] > len(payload["input"].encode("utf-8")) + 1024 or counts[1] > payload["max_output_tokens"]:
        raise ValueError("Provider usage exceeded approved envelope")
    return {"model": MODEL, "provider_status": data["status"],
            "input_tokens": counts[0], "output_tokens": counts[1],
            "accounted_microusd": cost_microusd(*counts)}


def parse_response(data, payload):
    usage = parse_usage(data, payload)
    chunks, refusal = [], False
    if not isinstance(data.get("output"), list):
        raise ValueError("Missing output")
    for item in data["output"]:
        if item.get("type") == "reasoning":
            continue
        if item.get("type") != "message" or item.get("role") != "assistant":
            raise ValueError("Unexpected tool or output item")
        for part in item.get("content", []):
            if part.get("type") == "refusal":
                refusal = True
            elif part.get("type") == "output_text" and isinstance(part.get("text"), str):
                chunks.append(part["text"])
            else:
                raise ValueError("Unexpected message content")
    text = redact_text("\n".join(chunks))
    if len(text.encode("utf-8")) > 65536:
        raise ValueError("Oversized output text")
    complete = data["status"] == "completed" and bool(text) and not refusal
    return {"ok": complete, "step": "model", "text": text,
            "reason": "" if complete else "refused_or_incomplete", **usage,
            "provider_calls_made": True, "billing_basis": "conservative_usage_not_invoice"}
