from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


PACKAGE = "marktplaats-mcp"
VERSION = "0.1.1"
SOURCE_INTEGRITY = "sha256:429eb3393bad0e7b8200cb946548a00a7f5e6e77454e49683c219bb2b2d3d0a7"
MANIFEST_NAME = ".leon-install-manifest.json"
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
EXPECTED_TOOLS = (
    "check_new_listings",
    "get_listing_details",
    "get_seller_profile",
    "list_categories",
    "search_listings",
)
ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "integrations" / "shopper" / "marktplaats" / "requirements.lock"
TARGET = ROOT / ".runtime" / "mcp" / f"marktplaats-{VERSION}"


def _python_in(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _server_in(venv: Path) -> Path:
    return venv / ("Scripts/marktplaats-mcp.exe" if os.name == "nt" else "bin/marktplaats-mcp")


def _assert_private_local_target(target: Path) -> None:
    root = ROOT.resolve()
    try:
        relative = target.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("Marktplaats runtime target must stay inside repository") from exc
    if not relative.parts:
        raise ValueError("Marktplaats runtime target must stay inside repository")
    current = root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise ValueError("Marktplaats runtime parent may not be a symlink")
    resolved = target.resolve(strict=False)
    if resolved == root or root not in resolved.parents:
        raise ValueError("Marktplaats runtime target must stay inside repository")


def _site_packages(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Lib" / "site-packages"
    return venv / "lib" / "python3.13" / "site-packages"


def _installed_version(venv: Path) -> str:
    matches = [
        distribution
        for distribution in importlib.metadata.distributions(path=[str(_site_packages(venv))])
        if (distribution.metadata.get("Name") or "").lower().replace("_", "-") == PACKAGE
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one installed {PACKAGE} distribution")
    return matches[0].version


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_manifest(target: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for base, directories, filenames in os.walk(target, followlinks=False):
        base_path = Path(base)
        for name in directories:
            if (base_path / name).is_symlink():
                raise RuntimeError("Marktplaats runtime contains a symlink")
        for name in filenames:
            path = base_path / name
            if path.name == MANIFEST_NAME:
                continue
            if path.is_symlink() or not path.is_file():
                raise RuntimeError("Marktplaats runtime contains an unsafe file")
            files[path.relative_to(target).as_posix()] = _hash_file(path)
    if not files:
        raise RuntimeError("Marktplaats runtime contains no files")
    return dict(sorted(files.items()))


def _write_manifest(target: Path) -> None:
    document = {
        "version": 1,
        "package": PACKAGE,
        "package_version": VERSION,
        "source_integrity": SOURCE_INTEGRITY,
        "files": _file_manifest(target),
    }
    destination = target / MANIFEST_NAME
    temporary = target / f"{MANIFEST_NAME}.tmp"
    temporary.write_text(json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, destination)


def _verify_manifest(target: Path) -> None:
    path = target / MANIFEST_NAME
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise RuntimeError("Marktplaats runtime manifest is missing or unsafe")
    document = json.loads(path.read_bytes())
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "package", "package_version", "source_integrity", "files"}
        or document["version"] != 1
        or document["package"] != PACKAGE
        or document["package_version"] != VERSION
        or document["source_integrity"] != SOURCE_INTEGRITY
        or not isinstance(document["files"], dict)
    ):
        raise RuntimeError("Marktplaats runtime manifest schema is invalid")
    current = _file_manifest(target)
    expected = document["files"]
    if set(current) != set(expected) or not all(
        isinstance(expected[name], str) and hmac.compare_digest(current[name], expected[name])
        for name in current
    ):
        raise RuntimeError("Marktplaats runtime file integrity check failed")


def verify_installation(target: Path = TARGET) -> dict[str, object]:
    _assert_private_local_target(target)
    if not target.is_dir() or target.is_symlink():
        raise RuntimeError("Marktplaats MCP runtime is missing or unsafe")
    _verify_manifest(target)
    version = _installed_version(target)
    if version != VERSION:
        raise RuntimeError(f"Unexpected {PACKAGE} version: {version}")
    server = _server_in(target)
    if not server.is_file() or server.is_symlink():
        raise RuntimeError("Marktplaats MCP executable is missing or unsafe")
    return {
        "installed": True,
        "version": version,
        "expected_tools": list(EXPECTED_TOOLS),
        "sandbox_attested": False,
        "enabled": False,
    }


def install(target: Path = TARGET) -> dict[str, object]:
    if sys.version_info[:2] != (3, 13):
        raise RuntimeError("Pinned Marktplaats runtime requires Python 3.13")
    if not LOCK.is_file():
        raise RuntimeError("Pinned Marktplaats requirements lock is missing")
    _assert_private_local_target(target)
    if target.exists():
        return verify_installation(target)

    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(parent, 0o700)
    target.mkdir(mode=0o700)
    try:
        subprocess.run([sys.executable, "-m", "venv", "--copies", str(target)], check=True, timeout=60)
        env = {
            **{
                key: value
                for key, value in os.environ.items()
                if not key.startswith(("PIP_", "UV_")) and key not in {"PYTHONHOME", "PYTHONPATH"}
            },
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INPUT": "1",
        }
        subprocess.run(
            [
                str(_python_in(target)),
                "-m",
                "pip",
                "install",
                "--quiet",
                "--no-cache-dir",
                "--require-hashes",
                "--only-binary=:all:",
                "--index-url=https://pypi.org/simple",
                "-r",
                str(LOCK),
            ],
            check=True,
            env=env,
            timeout=600,
        )
        if _installed_version(target) != VERSION:
            raise RuntimeError("Installed Marktplaats MCP version differs from lock")
        _write_manifest(target)
        return verify_installation(target)
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Install or verify isolated read-only Marktplaats MCP")
    parser.add_argument("--verify", action="store_true", help="verify existing runtime without installing")
    args = parser.parse_args()
    result = verify_installation() if args.verify else install()
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
