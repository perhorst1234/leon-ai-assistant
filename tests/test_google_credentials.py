import json
import os
from pathlib import Path

import pytest

from leon_control_plane.google_credentials import GoogleCredentialFileError, GoogleCredentialFileProvider


def write_secret(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def test_access_token_file_is_strict_and_redacted(tmp_path):
    path = tmp_path / "google.json"
    write_secret(path, {"access_token": "opaque", "granted_scopes": ["scope"]})
    provider = GoogleCredentialFileProvider(path, repository_root=tmp_path / "repo")
    credentials = provider.get_credentials()
    assert credentials.access_token == "opaque"
    assert credentials.granted_scopes == frozenset({"scope"})
    assert "opaque" not in repr(provider)
    assert "opaque" not in repr(credentials)


def test_refresh_tuple_is_supported_but_extra_or_missing_keys_are_rejected(tmp_path):
    path = tmp_path / "google.json"
    write_secret(path, {"refresh_token": "refresh", "client_id": "id", "client_secret": "secret", "granted_scopes": ["scope"]})
    assert GoogleCredentialFileProvider(path, repository_root=tmp_path / "repo").get_credentials().refresh_token == "refresh"
    write_secret(path, {"access_token": "opaque", "granted_scopes": ["scope"], "extra": "x"})
    with pytest.raises(GoogleCredentialFileError, match="invalid_schema"):
        GoogleCredentialFileProvider(path, repository_root=tmp_path / "repo").get_credentials()


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o604])
def test_file_must_be_private(tmp_path, mode):
    path = tmp_path / "google.json"
    write_secret(path, {"access_token": "opaque", "granted_scopes": ["scope"]})
    path.chmod(mode)
    with pytest.raises(GoogleCredentialFileError, match="permissions"):
        GoogleCredentialFileProvider(path, repository_root=tmp_path / "repo").get_credentials()


def test_repository_paths_and_symlinks_are_rejected(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    inside = repo / "google.json"
    write_secret(inside, {"access_token": "opaque", "granted_scopes": ["scope"]})
    with pytest.raises(GoogleCredentialFileError, match="repository_path"):
        GoogleCredentialFileProvider(inside, repository_root=repo).get_credentials()

    outside = tmp_path / "outside.json"
    write_secret(outside, {"access_token": "opaque", "granted_scopes": ["scope"]})
    link = tmp_path / "link.json"
    link.symlink_to(outside)
    with pytest.raises(GoogleCredentialFileError, match="symlink"):
        GoogleCredentialFileProvider(link, repository_root=repo).get_credentials()


def test_file_size_and_schema_are_bounded(tmp_path):
    path = tmp_path / "google.json"
    write_secret(path, {"access_token": "opaque", "granted_scopes": "scope"})
    with pytest.raises(GoogleCredentialFileError, match="invalid_scopes"):
        GoogleCredentialFileProvider(path, repository_root=tmp_path / "repo").get_credentials()
    path.write_bytes(b"{" + b'"access_token":"x"' + b",\"granted_scopes\":[\"scope\"]" + b"}" + b" " * (64 * 1024))
    path.chmod(0o600)
    with pytest.raises(GoogleCredentialFileError, match="invalid_file"):
        GoogleCredentialFileProvider(path, repository_root=tmp_path / "repo").get_credentials()
