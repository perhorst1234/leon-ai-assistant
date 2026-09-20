"""Private, file-backed Google OAuth credentials.

The file is deliberately a small user-selected secret, rather than a Google
client export.  It is read on demand so rotation does not require a restart.
"""
from __future__ import annotations

import json
import os
import stat as stat_module
from pathlib import Path
from typing import Any

from leon_control_plane.google_readonly import GoogleOAuthCredentials


MAX_FILE_BYTES = 64 * 1024
MAX_TOKEN_BYTES = 8192
MAX_ID_BYTES = 1024
MAX_SCOPES = 16
MAX_SCOPE_BYTES = 256
_ACCESS_KEYS = frozenset({"access_token", "granted_scopes"})
_REFRESH_KEYS = frozenset({"refresh_token", "client_id", "client_secret", "granted_scopes"})


class GoogleCredentialFileError(ValueError):
    """Stable, non-sensitive credential-file failure."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GoogleCredentialFileError("google_credentials_file_invalid_json")
        result[key] = value
    return result


def _check_text(value: Any, *, limit: int, code: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > limit:
        raise GoogleCredentialFileError(code)
    if any(character.isspace() for character in value):
        raise GoogleCredentialFileError(code)
    return value


def _check_scopes(value: Any) -> frozenset[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_SCOPES:
        raise GoogleCredentialFileError("google_credentials_file_invalid_scopes")
    scopes = frozenset(_check_text(item, limit=MAX_SCOPE_BYTES, code="google_credentials_file_invalid_scopes") for item in value)
    if len(scopes) != len(value):
        raise GoogleCredentialFileError("google_credentials_file_invalid_scopes")
    return scopes


def _ensure_safe_path(path: Path, repository_root: Path) -> Path:
    if not path.is_absolute():
        raise GoogleCredentialFileError("google_credentials_file_path_invalid")
    resolved_path = path.resolve(strict=False)
    if resolved_path.is_relative_to(repository_root.resolve(strict=False)):
        raise GoogleCredentialFileError("google_credentials_file_repository_path")
    if ".." in path.parts:
        raise GoogleCredentialFileError("google_credentials_file_path_invalid")
    # Reject symlink components, including the selected file itself.  This
    # keeps a user-selected path from being redirected after validation.
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            if current.is_symlink():
                raise GoogleCredentialFileError("google_credentials_file_symlink")
        except OSError:
            raise GoogleCredentialFileError("google_credentials_file_unavailable") from None
    return path


def _open_private_file(path: Path) -> int:
    required = ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW")
    if any(not hasattr(os, name) for name in required):
        raise GoogleCredentialFileError("google_credentials_file_platform_unsupported")
    directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    directory_fd = -1
    try:
        directory_fd = os.open(path.anchor, directory_flags)
        for part in path.parts[1:-1]:
            next_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        return os.open(path.name, file_flags, dir_fd=directory_fd)
    except OSError:
        raise GoogleCredentialFileError("google_credentials_file_unavailable") from None
    finally:
        if directory_fd >= 0:
            os.close(directory_fd)


def _read_private_json(path: Path, repository_root: Path) -> dict[str, Any]:
    path = _ensure_safe_path(path, repository_root)
    descriptor = _open_private_file(path)
    try:
        file_stat = os.fstat(descriptor)
        if not stat_module.S_ISREG(file_stat.st_mode) or file_stat.st_size > MAX_FILE_BYTES:
            raise GoogleCredentialFileError("google_credentials_file_invalid_file")
        if file_stat.st_uid != os.geteuid() or file_stat.st_mode & 0o077:
            raise GoogleCredentialFileError("google_credentials_file_permissions")
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = -1
            raw = handle.read(MAX_FILE_BYTES + 1)
    except OSError:
        raise GoogleCredentialFileError("google_credentials_file_unavailable") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(raw) > MAX_FILE_BYTES:
        raise GoogleCredentialFileError("google_credentials_file_invalid_file")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, GoogleCredentialFileError):
        raise GoogleCredentialFileError("google_credentials_file_invalid_json") from None
    if not isinstance(value, dict):
        raise GoogleCredentialFileError("google_credentials_file_invalid_schema")
    return value


class GoogleCredentialFileProvider:
    """Load one exact access-token or refresh-token credential tuple."""

    def __init__(self, path: str | os.PathLike[str], *, repository_root: Path | None = None) -> None:
        self.path = Path(path).expanduser()
        self.repository_root = (repository_root or Path(__file__).resolve().parents[2]).resolve(strict=False)

    def get_credentials(self) -> GoogleOAuthCredentials:
        data = _read_private_json(self.path, self.repository_root)
        keys = frozenset(data)
        if keys == _ACCESS_KEYS:
            access_token = _check_text(data["access_token"], limit=MAX_TOKEN_BYTES, code="google_credentials_file_invalid_token")
            return GoogleOAuthCredentials(access_token=access_token, granted_scopes=_check_scopes(data["granted_scopes"]))
        if keys == _REFRESH_KEYS:
            return GoogleOAuthCredentials(
                refresh_token=_check_text(data["refresh_token"], limit=MAX_TOKEN_BYTES, code="google_credentials_file_invalid_token"),
                client_id=_check_text(data["client_id"], limit=MAX_ID_BYTES, code="google_credentials_file_invalid_client"),
                client_secret=_check_text(data["client_secret"], limit=MAX_TOKEN_BYTES, code="google_credentials_file_invalid_client"),
                granted_scopes=_check_scopes(data["granted_scopes"]),
            )
        raise GoogleCredentialFileError("google_credentials_file_invalid_schema")

    def __repr__(self) -> str:
        return "<GoogleCredentialFileProvider redacted>"
