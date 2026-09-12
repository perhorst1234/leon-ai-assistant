"""Small, bounded, read-only Firecrawl search executor.

The provider is deliberately injected so the control-plane tests never need a
network connection or a real credential.  Only Firecrawl's fixed search host
is used; callers cannot provide a URL to fetch.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from leon_control_plane.connector_registry import classify_connector_action


MAX_QUERY_CHARS = 500
MAX_RESULTS = 10
MAX_DOMAINS = 10
MAX_DOMAIN_CHARS = 253
MAX_TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 256_000
PREVIEW_TTL_SECONDS = 900
FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v2/search"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ResearchExecutorError("research_redirect_rejected")


class ResearchExecutorError(ValueError):
    """Safe, user-visible error without provider credentials or response data."""


class ResearchProvider(Protocol):
    def search(self, *, query: str, domains: list[str], limit: int, timeout_seconds: int, max_bytes: int) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ResearchRequest:
    query: str
    domains: tuple[str, ...]
    limit: int = 5
    timeout_seconds: int = 10
    max_bytes: int = 256_000

    def fingerprint(self) -> str:
        payload = {"query": self.query, "domains": list(self.domains), "limit": self.limit, "timeout_seconds": self.timeout_seconds, "max_bytes": self.max_bytes}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _domain(value: Any) -> str:
    value = str(value or "").strip().lower().rstrip(".")
    if not value or len(value) > MAX_DOMAIN_CHARS or "://" in value or "/" in value or "@" in value:
        raise ResearchExecutorError("research_invalid_domain")
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        raise ResearchExecutorError("research_invalid_domain") from None
    if value.startswith(".") or ".." in value or not all(part and part[0].isalnum() and all(ch.isalnum() or ch == "-" for ch in part) for part in value.split(".")):
        raise ResearchExecutorError("research_invalid_domain")
    return value


def _allowed(host: str, domains: list[str]) -> bool:
    return any(host == item or host.endswith("." + item) for item in domains)


def validate_https_url(value: Any, domains: list[str]) -> str:
    """Validate a source URL before it enters the result set.

    This also protects future direct-HTTP providers from redirects or private
    network targets. Firecrawl itself is called through a fixed HTTPS host.
    """
    parsed = urllib.parse.urlsplit(str(value or ""))
    host = (parsed.hostname or "").lower().rstrip(".")
    try:
        port = parsed.port
    except ValueError:
        raise ResearchExecutorError("research_unsafe_source_url") from None
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or port:
        raise ResearchExecutorError("research_unsafe_source_url")
    if not _allowed(host, domains):
        raise ResearchExecutorError("research_source_domain_not_allowed")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except OSError:
        raise ResearchExecutorError("research_source_address_unresolved") from None
    if not addresses:
        raise ResearchExecutorError("research_source_address_unresolved")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ResearchExecutorError("research_private_source_address")
    return urllib.parse.urlunsplit(("https", host, parsed.path, parsed.query, ""))


def normalize_request(data: dict[str, Any], configured_domains: list[str]) -> ResearchRequest:
    if not isinstance(data, dict):
        raise ResearchExecutorError("research_invalid_request")
    query = str(data.get("query") or "").strip()
    if not query or len(query) > MAX_QUERY_CHARS:
        raise ResearchExecutorError("research_query_limit")
    raw_domains = data.get("allowed_domains", data.get("domains", configured_domains))
    if raw_domains == []:
        raw_domains = configured_domains
    if isinstance(raw_domains, str):
        raw_domains = [part for part in raw_domains.split(",") if part.strip()]
    if not isinstance(raw_domains, list) or not raw_domains or len(raw_domains) > MAX_DOMAINS:
        raise ResearchExecutorError("research_domain_allowlist_required")
    domains = tuple(sorted({_domain(item) for item in raw_domains}))
    try:
        limit = int(data.get("max_results", data.get("limit", 5))); timeout = int(data.get("timeout_seconds", 10)); max_bytes = int(data.get("max_bytes", MAX_RESPONSE_BYTES))
    except (TypeError, ValueError):
        raise ResearchExecutorError("research_invalid_limits") from None
    if not 1 <= limit <= MAX_RESULTS or not 1 <= timeout <= MAX_TIMEOUT_SECONDS or not 1_024 <= max_bytes <= MAX_RESPONSE_BYTES:
        raise ResearchExecutorError("research_limits_exceeded")
    return ResearchRequest(query, domains, limit, timeout, max_bytes)


class FirecrawlSearchProvider:
    def __init__(self, api_key: str):
        self._api_key = api_key

    def search(self, *, query: str, domains: list[str], limit: int, timeout_seconds: int, max_bytes: int) -> dict[str, Any]:
        body = json.dumps({"query": query, "limit": limit, "sources": ["web"], "includeDomains": domains}).encode()
        request = urllib.request.Request(FIRECRAWL_SEARCH_URL, data=body, method="POST", headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"})
        try:
            opener = urllib.request.build_opener(_NoRedirect)
            with opener.open(request, timeout=timeout_seconds) as response:
                raw = response.read(max_bytes + 1)
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ResearchExecutorError("research_provider_unavailable") from None
        if len(raw) > max_bytes:
            raise ResearchExecutorError("research_response_limit")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ResearchExecutorError("research_provider_invalid_response") from None
        if not isinstance(decoded, dict) or decoded.get("success") is False:
            raise ResearchExecutorError("research_provider_error")
        return decoded


def _values(values: dict[str, str]) -> tuple[bool, str, list[str]]:
    enabled = str(values.get("RESEARCH_EXECUTOR_ENABLED", "false")).lower() in {"1", "true", "yes"}
    key = str(values.get("FIRECRAWL_API_KEY") or "")
    domains = [item.strip() for item in str(values.get("RESEARCH_ALLOWED_DOMAINS") or "").split(",") if item.strip()]
    return enabled, key, domains


def status(store: Any, values: dict[str, str]) -> dict[str, Any]:
    enabled, key, domains = _values(values)
    return {"ok": True, "enabled": enabled, "configured": bool(key), "allowlist_configured": bool(domains), "limits": {"max_query_chars": MAX_QUERY_CHARS, "max_results": MAX_RESULTS, "max_domains": MAX_DOMAINS, "max_timeout_seconds": MAX_TIMEOUT_SECONDS, "max_response_bytes": MAX_RESPONSE_BYTES}}


def _permission(store: Any, request: ResearchRequest, values: dict[str, str]) -> dict[str, Any]:
    manifest = store.get_connector_manifest("firecrawl-research")
    # The manifest remains disabled in the registry by default. The separate
    # feature flag is the deliberate local promotion gate for this executor.
    if _values(values)[0]:
        manifest = {**manifest, "status": "approved_readonly"}
    return classify_connector_action(manifest, action_type="read", requested_scope="web:search_only", present_env_keys={"FIRECRAWL_API_KEY"} if _values(values)[1] else set())


def preview(store: Any, values: dict[str, str], data: dict[str, Any]) -> dict[str, Any]:
    request = normalize_request(data, _values(values)[2])
    enabled, key, _ = _values(values)
    check = _permission(store, request, values)
    if not enabled:
        check.update(decision="denied", allowed=False, execution_allowed=False, reason="Research executor is disabled.")
    elif not key:
        check.update(decision="waiting_for_secret", allowed=False, execution_allowed=False, reason="Missing required env key: FIRECRAWL_API_KEY.")
    check["research_preview_fingerprint"] = request.fingerprint()
    check_id = store.record_connector_permission_check(check, actor_type="system", actor_id="research-preview", connector_executed=False)
    return {
        "ok": True,
        "provider": "firecrawl",
        "status": "preview_ready" if check.get("execution_allowed") else "disabled" if not enabled else "waiting_for_secret",
        "risk": check.get("risk_class", "R1"),
        "configured": bool(key),
        "execution_allowed": bool(check.get("execution_allowed")),
        "preview_fingerprint": request.fingerprint(),
        "preview_id": check_id,
        "request": {"query": request.query, "allowed_domains": list(request.domains), "max_results": request.limit, "timeout_seconds": request.timeout_seconds, "max_bytes": request.max_bytes},
        "permission_check_id": check_id,
    }


def _require_preview(store: Any, preview_id: str, fingerprint: str) -> None:
    if not preview_id:
        raise ResearchExecutorError("research_preview_required")
    preview = next(
        (item for item in store.get_state().get("connector_permission_checks", []) if item.get("id") == preview_id),
        None,
    )
    if not preview or preview.get("connector_id") != "firecrawl-research" or preview.get("decision") != "allowed":
        raise ResearchExecutorError("research_preview_invalid")
    try:
        recorded = json.loads(str(preview.get("check_json") or "{}"))
        created_at = datetime.fromisoformat(str(preview.get("created_at") or "").replace("Z", "+00:00"))
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ResearchExecutorError("research_preview_invalid") from None
    if not recorded.get("execution_allowed") or recorded.get("research_preview_fingerprint") != fingerprint:
        raise ResearchExecutorError("research_preview_mismatch")
    if (datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)).total_seconds() > PREVIEW_TTL_SECONDS:
        raise ResearchExecutorError("research_preview_expired")


def run(store: Any, values: dict[str, str], data: dict[str, Any], provider: ResearchProvider | None = None) -> dict[str, Any]:
    request = normalize_request(data, _values(values)[2])
    expected = str(data.get("preview_fingerprint", data.get("fingerprint")) or "")
    if not expected or expected != request.fingerprint():
        raise ResearchExecutorError("research_fingerprint_mismatch")
    _require_preview(store, str(data.get("preview_id") or ""), expected)
    enabled, key, _ = _values(values)
    check = _permission(store, request, values)
    if not enabled:
        check.update(decision="denied", allowed=False, execution_allowed=False, reason="Research executor is disabled.")
    elif not key:
        check.update(decision="waiting_for_secret", allowed=False, execution_allowed=False, reason="Missing required env key: FIRECRAWL_API_KEY.")
    if check.get("decision") != "allowed" or not check.get("execution_allowed"):
        check_id = store.record_connector_permission_check(check, actor_type="system", actor_id="research-run", connector_executed=False)
        raise ResearchExecutorError(f"research_permission_denied:{check.get('decision', 'denied')}:{check_id}")
    store.record_connector_permission_check(check, actor_type="system", actor_id="research-run-preflight", connector_executed=False)
    try:
        raw = (provider or FirecrawlSearchProvider(key)).search(query=request.query, domains=list(request.domains), limit=request.limit, timeout_seconds=request.timeout_seconds, max_bytes=request.max_bytes)
    except ResearchExecutorError as exc:
        failed = {**check, "audit_event_type": "connector_research_failed", "research_outcome": str(exc)}
        store.record_connector_permission_check(failed, actor_type="system", actor_id="research-run", connector_executed=True)
        raise
    except Exception:
        failed = {**check, "audit_event_type": "connector_research_failed", "research_outcome": "research_provider_unavailable"}
        store.record_connector_permission_check(failed, actor_type="system", actor_id="research-run", connector_executed=True)
        raise ResearchExecutorError("research_provider_unavailable") from None
    if not isinstance(raw, dict):
        failed = {**check, "audit_event_type": "connector_research_failed", "research_outcome": "research_provider_invalid_response"}
        store.record_connector_permission_check(failed, actor_type="system", actor_id="research-run", connector_executed=True)
        raise ResearchExecutorError("research_provider_invalid_response")
    data_block = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    rows = data_block.get("web") if isinstance(data_block.get("web"), list) else []
    results = []
    rejected_results = 0
    for row in rows[:request.limit]:
        if not isinstance(row, dict):
            rejected_results += 1
            continue
        try:
            url = validate_https_url(row.get("url"), list(request.domains))
        except ResearchExecutorError:
            rejected_results += 1
            continue
        results.append({"title": str(row.get("title") or "")[:500], "description": str(row.get("description") or "")[:1000], "url": url, "source_ref": f"firecrawl:{url}"})
    completed = {**check, "audit_event_type": "connector_research_completed", "research_outcome": "completed", "accepted_result_count": len(results), "rejected_result_count": rejected_results}
    check_id = store.record_connector_permission_check(completed, actor_type="system", actor_id="research-run", connector_executed=True)
    return {
        "ok": True,
        "status": "completed",
        "risk": check.get("risk_class", "R1"),
        "execution_allowed": True,
        "preview_fingerprint": request.fingerprint(),
        "results": results,
        "permission_check_id": check_id,
        "provider": "firecrawl",
        "credits_used": raw.get("creditsUsed"),
        "rejected_results": rejected_results,
    }


def research_request(store: Any, *, method: str, path: str, values: dict[str, str], data: dict[str, Any] | None = None, provider: ResearchProvider | None = None) -> dict[str, Any] | None:
    if path == "/api/research/status" and method == "GET": return status(store, values)
    if path == "/api/research/preview" and method == "POST": return preview(store, values, data or {})
    if path == "/api/research/run" and method == "POST": return run(store, values, data or {}, provider)
    return None
