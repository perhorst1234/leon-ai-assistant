from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any, Callable

from leon_control_plane.tool_registry import normalize_tool_manifest


GITHUB_REPO_RE = re.compile(r"^https://github\.com/([^/\s]+)/([^/\s#?]+)")
GITHUB_API_VERSION = "2022-11-28"


def parse_github_repo_url(url: str) -> tuple[str, str] | None:
    match = GITHUB_REPO_RE.match(str(url or "").strip())
    if not match:
        return None
    owner = match.group(1)
    repo = match.group(2).removesuffix(".git")
    if not owner or not repo:
        return None
    return owner, repo


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def days_since(value: str, *, now: datetime | None = None) -> int | None:
    parsed = _parse_iso(value)
    if parsed is None:
        return None
    now = (now or datetime.now(UTC)).astimezone(UTC)
    return max(0, int((now - parsed).total_seconds() // 86400))


def safe_repo_metadata(repo_json: dict[str, Any], *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    license_info = repo_json.get("license") or {}
    headers = headers or {}
    pushed_at = str(repo_json.get("pushed_at") or "")
    updated_at = str(repo_json.get("updated_at") or "")
    owner = repo_json.get("owner") or {}
    full_name = str(repo_json.get("full_name") or "")
    owner_login, _, repo_name = full_name.partition("/")
    return {
        "full_name": full_name,
        "owner_login": str(owner.get("login") or owner_login),
        "repo_name": repo_name,
        "html_url": str(repo_json.get("html_url") or ""),
        "source_api_url": str(repo_json.get("url") or ""),
        "description": str(repo_json.get("description") or ""),
        "homepage": str(repo_json.get("homepage") or ""),
        "archived": bool(repo_json.get("archived", False)),
        "disabled": bool(repo_json.get("disabled", False)),
        "fork": bool(repo_json.get("fork", False)),
        "is_template": bool(repo_json.get("is_template", False)),
        "private": bool(repo_json.get("private", False)),
        "stargazers_count": int(repo_json.get("stargazers_count") or 0),
        "forks_count": int(repo_json.get("forks_count") or 0),
        "open_issues_count": int(repo_json.get("open_issues_count") or 0),
        "watchers_count": int(repo_json.get("watchers_count") or 0),
        "default_branch": str(repo_json.get("default_branch") or ""),
        "language": str(repo_json.get("language") or ""),
        "topics": [str(item) for item in (repo_json.get("topics") or [])[:20]],
        "license": {
            "key": str(license_info.get("key") or ""),
            "name": str(license_info.get("name") or ""),
            "spdx_id": str(license_info.get("spdx_id") or ""),
        },
        "created_at": str(repo_json.get("created_at") or ""),
        "updated_at": updated_at,
        "pushed_at": pushed_at,
        "pushed_days_ago": days_since(pushed_at),
        "size_kb": int(repo_json.get("size") or 0),
        "visibility": str(repo_json.get("visibility") or ""),
        "fetched_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "refresh_status": "fresh",
        "etag": headers.get("etag", ""),
        "rate_limit": {
            "limit": headers.get("x-ratelimit-limit", ""),
            "remaining": headers.get("x-ratelimit-remaining", ""),
            "reset": headers.get("x-ratelimit-reset", ""),
            "resource": headers.get("x-ratelimit-resource", ""),
        },
    }


def fetch_github_repo_metadata(
    owner: str,
    repo: str,
    *,
    etag: str = "",
    opener: Callable[[urllib.request.Request], Any] | None = None,
) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "leon-ai-assistant-control-plane",
    }
    if etag:
        headers["If-None-Match"] = etag
    request = urllib.request.Request(url, headers=headers)
    opener = opener or urllib.request.urlopen
    try:
        with opener(request) as response:
            headers = {key.lower(): value for key, value in response.headers.items()}
            payload = json.loads(response.read().decode("utf-8"))
            return {
                "ok": True,
                "status": int(getattr(response, "status", 200)),
                "metadata": safe_repo_metadata(payload, headers=headers),
                "error": "",
            }
    except urllib.error.HTTPError as exc:
        headers = {key.lower(): value for key, value in exc.headers.items()} if exc.headers else {}
        if exc.code == 304:
            return {
                "ok": True,
                "status": 304,
                "metadata": {
                    "refresh_status": "not_modified",
                    "fetched_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                    "etag": headers.get("etag", etag),
                    "rate_limit": {
                        "limit": headers.get("x-ratelimit-limit", ""),
                        "remaining": headers.get("x-ratelimit-remaining", ""),
                        "reset": headers.get("x-ratelimit-reset", ""),
                        "resource": headers.get("x-ratelimit-resource", ""),
                    },
                },
                "error": "",
            }
        reason = "rate_limited" if exc.code in {403, 429} and headers.get("x-ratelimit-remaining") == "0" else "http_error"
        return {
            "ok": False,
            "status": exc.code,
            "metadata": {
                "refresh_status": reason,
                "fetched_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "rate_limit": {
                    "limit": headers.get("x-ratelimit-limit", ""),
                    "remaining": headers.get("x-ratelimit-remaining", ""),
                    "reset": headers.get("x-ratelimit-reset", ""),
                    "resource": headers.get("x-ratelimit-resource", ""),
                }
            },
            "error": reason,
        }
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "status": 0, "metadata": {}, "error": f"fetch_failed:{type(exc).__name__}"}


def refresh_manifest_github_metadata(
    raw_manifest: dict[str, Any],
    *,
    opener: Callable[[urllib.request.Request], Any] | None = None,
) -> dict[str, Any]:
    manifest = normalize_tool_manifest(raw_manifest)
    parsed = parse_github_repo_url(manifest["source_url"])
    if parsed is None:
        return {
            "ok": False,
            "tool_id": manifest["tool_id"],
            "manifest": manifest,
            "error": "not_a_github_repository_url",
        }
    owner, repo = parsed
    previous_metadata = dict(manifest.get("github_metadata") or {})
    result = fetch_github_repo_metadata(owner, repo, etag=str(previous_metadata.get("etag") or ""), opener=opener)
    if not result["ok"]:
        return {
            "ok": False,
            "tool_id": manifest["tool_id"],
            "manifest": manifest,
            "error": result["error"],
            "status": result["status"],
            "metadata": result.get("metadata") or {},
        }

    metadata = result["metadata"]
    if result["status"] == 304:
        metadata = {**previous_metadata, **metadata}
    updated = dict(manifest)
    updated["github_metadata"] = metadata
    pushed_days = metadata.get("pushed_days_ago")
    if metadata.get("archived") or metadata.get("disabled"):
        updated["maintenance_status"] = "github_live:archived_or_disabled"
    elif isinstance(pushed_days, int) and pushed_days <= 180:
        updated["maintenance_status"] = "github_live:active_recent"
    elif isinstance(pushed_days, int) and pushed_days <= 730:
        updated["maintenance_status"] = "github_live:active_older"
    else:
        updated["maintenance_status"] = "github_live:stale_or_unknown"
    return {
        "ok": True,
        "tool_id": manifest["tool_id"],
        "manifest": updated,
        "metadata": metadata,
        "status": result["status"],
        "error": "",
    }
