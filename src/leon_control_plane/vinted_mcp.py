from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shutil
import subprocess
from pathlib import Path


PACKAGE = "vinted-safe-stdio"
VERSION = "1.0.0"
SDK_VERSION = "1.30.0"
SDK_INTEGRITY = "sha512-xKd8OIzlqNzcqcNumGAa6g+PW2kjD5vrpcKOnfldAUPP3j7lnqMPwlTXQm8gF+UwH72z0lqaRbjr9hqGz0eITA=="
SOURCE_MANIFEST_SHA256 = "60fdca132fc6f6ac6dcfaf8d93507fef781f0dcd21912a1be5dc31656fb94c73"
SOURCE_ARCHIVE_SHA256 = "3ba53ffeb29f5af4477ad749c14cb627291c7ad64e9c294157dd5dea2b9abfcd"
UPSTREAM_COMMIT = "460317f23a4d665bd352863f388c9d299550955a"
EXPECTED_TOOLS = ("compare_prices", "get_item", "get_seller", "get_trending", "search_items")
MANIFEST_NAME = ".leon-install-manifest.json"
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "integrations" / "shopper" / "vinted-safe"
TARGET = ROOT / ".runtime" / "mcp" / f"vinted-safe-{VERSION}"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_local_target(target: Path) -> None:
    root = ROOT.resolve()
    try:
        relative = target.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("Vinted runtime target must stay inside repository") from exc
    if not relative.parts:
        raise ValueError("Vinted runtime target must stay inside repository")
    current = root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise ValueError("Vinted runtime parent may not be a symlink")
    if root not in target.resolve(strict=False).parents:
        raise ValueError("Vinted runtime target must stay inside repository")


def _files(root: Path, *, exclude: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for base, directories, filenames in os.walk(root, followlinks=False):
        base_path = Path(base)
        for name in directories:
            if (base_path / name).is_symlink():
                raise RuntimeError("Vinted artifact contains a symlink")
        for name in filenames:
            path = base_path / name
            if path.name == exclude:
                continue
            if path.is_symlink() or not path.is_file():
                raise RuntimeError("Vinted artifact contains an unsafe file")
            result[path.relative_to(root).as_posix()] = _hash_file(path)
    if not result:
        raise RuntimeError("Vinted artifact contains no files")
    return dict(sorted(result.items()))


def _verify_source() -> None:
    manifest_path = SOURCE / "source-manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink() or manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise RuntimeError("Vinted source manifest is missing or unsafe")
    raw = manifest_path.read_bytes()
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), SOURCE_MANIFEST_SHA256):
        raise RuntimeError("Vinted source manifest integrity check failed")
    document = json.loads(raw)
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "name", "version_string", "upstream_commit", "source_archive_sha256", "files"}
        or document["version"] != 1
        or document["name"] != PACKAGE
        or document["version_string"] != VERSION
        or document["upstream_commit"] != UPSTREAM_COMMIT
        or document["source_archive_sha256"] != SOURCE_ARCHIVE_SHA256
        or not isinstance(document["files"], dict)
    ):
        raise RuntimeError("Vinted source manifest schema is invalid")
    expected = document["files"]
    current = _files(SOURCE, exclude="source-manifest.json")
    if not isinstance(expected, dict) or set(current) != set(expected) or not all(
        isinstance(expected[name], str) and hmac.compare_digest(current[name], expected[name])
        for name in current
    ):
        raise RuntimeError("Vinted source file integrity check failed")


def _verify_package_files(root: Path) -> None:
    package = json.loads((root / "package.json").read_bytes())
    lock = json.loads((root / "package-lock.json").read_bytes())
    locked_root = lock.get("packages", {}).get("")
    sdk = lock.get("packages", {}).get("node_modules/@modelcontextprotocol/sdk")
    if (
        package.get("name") != PACKAGE
        or package.get("version") != VERSION
        or package.get("main") != "dist/index.js"
        or package.get("dependencies") != {"@modelcontextprotocol/sdk": SDK_VERSION}
        or not isinstance(locked_root, dict)
        or locked_root.get("dependencies") != package["dependencies"]
        or not isinstance(sdk, dict)
        or sdk.get("version") != SDK_VERSION
        or sdk.get("integrity") != SDK_INTEGRITY
    ):
        raise RuntimeError("Vinted package lock contract differs from approved source")
    runtime = root / "dist" / "index.js"
    if not runtime.is_file() or runtime.is_symlink():
        raise RuntimeError("Vinted runtime entrypoint is missing or unsafe")


def _write_runtime_manifest(target: Path) -> None:
    document = {
        "version": 1,
        "package": PACKAGE,
        "package_version": VERSION,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "files": _files(target, exclude=MANIFEST_NAME),
    }
    temporary = target / f"{MANIFEST_NAME}.tmp"
    temporary.write_text(json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, target / MANIFEST_NAME)


def _verify_runtime_manifest(target: Path) -> None:
    path = target / MANIFEST_NAME
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise RuntimeError("Vinted runtime manifest is missing or unsafe")
    document = json.loads(path.read_bytes())
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "package", "package_version", "source_manifest_sha256", "files"}
        or document["version"] != 1
        or document["package"] != PACKAGE
        or document["package_version"] != VERSION
        or document["source_manifest_sha256"] != SOURCE_MANIFEST_SHA256
        or not isinstance(document["files"], dict)
    ):
        raise RuntimeError("Vinted runtime manifest schema is invalid")
    current = _files(target, exclude=MANIFEST_NAME)
    expected = document["files"]
    if set(current) != set(expected) or not all(
        isinstance(expected[name], str) and hmac.compare_digest(current[name], expected[name])
        for name in current
    ):
        raise RuntimeError("Vinted runtime file integrity check failed")


def verify_installation(target: Path = TARGET) -> dict[str, object]:
    _assert_local_target(target)
    if not target.is_dir() or target.is_symlink():
        raise RuntimeError("Vinted runtime is missing or unsafe")
    _verify_runtime_manifest(target)
    _verify_package_files(target)
    return {
        "installed": True,
        "version": VERSION,
        "expected_tools": list(EXPECTED_TOOLS),
        "sandbox_attested": False,
        "enabled": False,
    }


def install(*, target: Path = TARGET, npm: str = "npm") -> dict[str, object]:
    _verify_source()
    _verify_package_files(SOURCE)
    _assert_local_target(target)
    if target.exists():
        return verify_installation(target)
    executable = shutil.which(npm)
    if not executable:
        raise RuntimeError("npm is required to stage Vinted MCP")

    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(parent, 0o700)
    target.mkdir(mode=0o700)
    try:
        for relative in ("package.json", "package-lock.json", "LICENSE.md", "dist/index.js"):
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(SOURCE / relative, destination)
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.lower().startswith(("npm_", "pnpm_"))
            and key not in {"NODE_OPTIONS", "NODE_PATH", "NPM_CONFIG_USERCONFIG"}
        }
        env.update({"NPM_CONFIG_USERCONFIG": os.devnull, "NPM_CONFIG_AUDIT": "false", "NPM_CONFIG_FUND": "false"})
        subprocess.run(
            [
                executable,
                "ci",
                "--ignore-scripts",
                "--omit=dev",
                "--no-audit",
                "--no-fund",
                "--registry=https://registry.npmjs.org",
            ],
            cwd=target,
            env=env,
            check=True,
            timeout=600,
        )
        _verify_package_files(target)
        _write_runtime_manifest(target)
        return verify_installation(target)
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage or verify disabled Vinted MCP runtime")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--npm", default="npm")
    args = parser.parse_args()
    result = verify_installation() if args.verify else install(npm=args.npm)
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
