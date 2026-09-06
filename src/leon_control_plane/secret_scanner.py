from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


REDACTION = "[REDACTED_SECRET]"


@dataclass(frozen=True)
class SecretPattern:
    kind: str
    pattern: re.Pattern[str]


SECRET_PATTERNS = (
    SecretPattern("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL)),
    SecretPattern("openai_api_key", re.compile(r"\bsk-(?:proj-|live-|test-)?[A-Za-z0-9_-]{12,}\b")),
    SecretPattern("stripe_key", re.compile(r"\b[rs]k_(?:live|test)_[A-Za-z0-9]{12,}\b")),
    SecretPattern("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b")),
    SecretPattern("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
    SecretPattern("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    SecretPattern("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{12,}\b")),
    SecretPattern("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    SecretPattern("bearer_token", re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._~+/=-]{8,}")),
    SecretPattern("basic_auth_url", re.compile(r"https?://[^/\s:@]{1,80}:[^/\s:@]{4,}@")),
    SecretPattern(
        "credential_assignment",
        re.compile(
            r"(?i)\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|auth[_ -]?token|token|password|passwd|credential|client[_ -]?secret|secret)"
            r"\s*[:=]\s*[\"']?[^,\s\"']{4,}"
        ),
    ),
)


@dataclass(frozen=True)
class SecretFinding:
    kind: str
    count: int


@dataclass(frozen=True)
class SecretScanResult:
    findings: tuple[SecretFinding, ...]

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)

    @property
    def total(self) -> int:
        return sum(finding.count for finding in self.findings)

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(finding.kind for finding in self.findings)


class SecretScanError(ValueError):
    def __init__(self, label: str, result: SecretScanResult):
        self.label = label
        self.result = result
        kinds = ", ".join(result.kinds) or "credential"
        super().__init__(f"{label} must not contain secret-like or credential values ({kinds})")


def scan_text(text: str) -> SecretScanResult:
    findings: list[SecretFinding] = []
    for item in SECRET_PATTERNS:
        count = len(item.pattern.findall(text or ""))
        if count:
            findings.append(SecretFinding(kind=item.kind, count=count))
    return SecretScanResult(tuple(findings))


def scan_value(value: Any) -> SecretScanResult:
    counts: dict[str, int] = {}

    def visit(item: Any) -> None:
        if isinstance(item, str):
            for finding in scan_text(item).findings:
                counts[finding.kind] = counts.get(finding.kind, 0) + finding.count
            return
        if isinstance(item, dict):
            for child in item.values():
                visit(child)
            return
        if isinstance(item, (list, tuple, set)):
            for child in item:
                visit(child)

    visit(value)
    return SecretScanResult(tuple(SecretFinding(kind=kind, count=count) for kind, count in sorted(counts.items())))


def contains_secret(value: Any) -> bool:
    return scan_value(value).has_findings


def assert_no_secrets(label: str, value: Any) -> None:
    result = scan_value(value)
    if result.has_findings:
        raise SecretScanError(label, result)


def redact_text(text: str) -> str:
    redacted = text or ""
    for item in SECRET_PATTERNS:
        redacted = item.pattern.sub(REDACTION, redacted)
    return redacted


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, set):
        return [redact_value(item) for item in sorted(value, key=str)]
    if isinstance(value, dict):
        return {str(key): redact_value(item) for key, item in value.items()}
    return value
