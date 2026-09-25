"""Bounded loopback-only Ollama transport for the local Tesla M40."""
from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import os
from pathlib import Path
import re

from leon_control_plane.openai_text import MAX_INPUT_BYTES, MAX_OUTPUT_TOKENS, ModelPreflightError, positive_int
from leon_control_plane.secret_scanner import assert_no_secrets, redact_text


PROVIDER = "ollama"
DEFAULT_MODEL = "qwen2.5-coder:14b"
_MODEL_NAME = re.compile(r"[A-Za-z0-9._:/-]{1,128}\Z")


def _env_values(env_file: Path | None) -> dict[str, str]:
    keys = {
        "LEON_LOCAL_MODEL_ENABLED", "LEON_LOCAL_MODEL_HOST", "LEON_LOCAL_MODEL_PORT",
        "LEON_LOCAL_MODEL_NAME", "LEON_LOCAL_MODEL_NUM_CTX", "LEON_LOCAL_MODEL_TIMEOUT_SECONDS",
    }
    values: dict[str, str] = {}
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
                key = key.strip()
                if separator and key in keys:
                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                        value = value[1:-1]
                    values[key] = value
        except (OSError, ValueError):
            raise ModelPreflightError("local_model_env_file_unavailable") from None
    values.update({key: os.environ[key] for key in keys if key in os.environ})
    return values


@dataclass(frozen=True)
class LocalModelConfig:
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 11434
    model: str = DEFAULT_MODEL
    num_ctx: int = 4096
    timeout_seconds: int = 180

    @classmethod
    def from_env(cls, *, env_file: Path | None = None):
        values = _env_values(env_file)

        def number(name: str, default: int) -> int:
            try:
                return int(values.get(name, str(default)))
            except ValueError:
                return 0

        return cls(
            enabled=values.get("LEON_LOCAL_MODEL_ENABLED") == "1",
            host=values.get("LEON_LOCAL_MODEL_HOST", "127.0.0.1"),
            port=number("LEON_LOCAL_MODEL_PORT", 11434),
            model=values.get("LEON_LOCAL_MODEL_NAME", DEFAULT_MODEL),
            num_ctx=number("LEON_LOCAL_MODEL_NUM_CTX", 4096),
            timeout_seconds=number("LEON_LOCAL_MODEL_TIMEOUT_SECONDS", 180),
        )

    def validate(self):
        if not self.enabled:
            raise ModelPreflightError("local_model_disabled")
        if self.host != "127.0.0.1":
            raise ModelPreflightError("local_model_must_use_loopback")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ModelPreflightError("local_model_port_invalid")
        if not _MODEL_NAME.fullmatch(self.model):
            raise ModelPreflightError("local_model_name_invalid")
        if type(self.num_ctx) is not int or not 1024 <= self.num_ctx <= 32768:
            raise ModelPreflightError("local_model_context_invalid")
        if type(self.timeout_seconds) is not int or not 10 <= self.timeout_seconds <= 600:
            raise ModelPreflightError("local_model_timeout_invalid")


def request_payload(prompt: str, max_output_tokens: int, config: LocalModelConfig) -> dict:
    config.validate()
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode("utf-8")) > MAX_INPUT_BYTES:
        raise ValueError("Expected 1..4096 UTF-8 bytes of explicitly shared text")
    assert_no_secrets("Shared text", prompt)
    positive_int(max_output_tokens, "output limit", MAX_OUTPUT_TOKENS)
    return {
        "provider": PROVIDER,
        "model": config.model,
        "input": prompt,
        "max_output_tokens": max_output_tokens,
        "num_ctx": config.num_ctx,
    }


def send_response(payload: dict, config: LocalModelConfig) -> dict:
    """Send one bounded request to the loopback Ollama service."""
    config.validate()
    wire = {
        "model": payload["model"],
        "prompt": payload["input"],
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "num_ctx": payload["num_ctx"],
            "num_predict": payload["max_output_tokens"],
            "temperature": 0.2,
        },
    }
    conn = http.client.HTTPConnection(config.host, config.port, timeout=config.timeout_seconds)
    try:
        conn.request("POST", "/api/generate", json.dumps(wire).encode("utf-8"), {"Content-Type": "application/json"})
        response = conn.getresponse()
        raw = response.read(262145)
        if response.status != 200 or len(raw) > 262144:
            raise ValueError("Local model outcome could not be verified")
        return json.loads(raw)
    finally:
        conn.close()


def parse_response(data: dict, payload: dict) -> dict:
    if not isinstance(data, dict) or data.get("model") != payload["model"] or data.get("done") is not True:
        raise ValueError("Unexpected local model response")
    counts = [data.get("prompt_eval_count", 0), data.get("eval_count", 0)]
    if any(type(count) is not int or count < 0 for count in counts):
        raise ValueError("Invalid local model usage")
    if counts[1] > payload["max_output_tokens"]:
        raise ValueError("Local model output exceeded approved envelope")
    text = redact_text(data.get("response", "")) if isinstance(data.get("response"), str) else ""
    if len(text.encode("utf-8")) > 65536:
        raise ValueError("Oversized output text")
    complete = bool(text) and data.get("done_reason") in {"stop", "length"}
    return {
        "ok": complete,
        "step": "model",
        "text": text,
        "reason": "" if complete else "local_model_incomplete",
        "provider": PROVIDER,
        "model": payload["model"],
        "provider_status": "completed" if complete else "incomplete",
        "input_tokens": counts[0],
        "output_tokens": counts[1],
        "accounted_microusd": 0,
        "provider_calls_made": True,
        "billing_basis": "local_gpu_no_provider_charge",
    }
