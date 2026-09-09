"""Small, local-only delivery helpers for Leon.

This module deliberately does not source shell files.  Environment files contain
literal KEY=value pairs and are passed directly to child processes.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Iterable

KEY_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")


def _literal_env(path: Path) -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    errors: list[str] = []
    if not path.exists():
        return values, errors
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            errors.append(f"line {number}: expected KEY=value")
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or any(char not in KEY_CHARS for char in key) or key[0].isdigit():
            errors.append(f"line {number}: invalid key")
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values, errors


@dataclass(frozen=True)
class DeliveryConfig:
    repo: Path
    runtime: Path
    env_file: Path
    db: Path
    port: int = 8765
    web_port: int = 3000

    @classmethod
    def from_env(cls, repo: Path | None = None) -> "DeliveryConfig":
        repo = (repo or Path(__file__).resolve().parents[2]).resolve()
        runtime = Path(os.environ.get("LEON_RUNTIME_DIR", repo / ".runtime"))
        if not runtime.is_absolute():
            runtime = repo / runtime
        env_file = Path(os.environ.get("LEON_ENV_FILE", repo / ".env.local"))
        if not env_file.is_absolute():
            env_file = repo / env_file
        # Runtime state belongs beside the private process/log state.  The seed
        # remains a repository input; the mutable SQLite database does not.
        db = Path(os.environ.get("LEON_DB_PATH", runtime / "control-plane.sqlite"))
        if not db.is_absolute():
            db = repo / db
        return cls(repo, runtime.resolve(), env_file.resolve(), db.resolve(),
                   int(os.environ.get("LEON_DASHBOARD_PORT", "8765")),
                   int(os.environ.get("LEON_WEB_PORT", "3000")))


def _private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(stat.S_IRWXU)


def _private_file(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _process_group_running(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _owned_process(record: dict) -> bool:
    """Require a live process to still match the command we launched."""
    command = record.get("command")
    if not isinstance(command, list) or not command:
        return False
    try:
        result = subprocess.run(["ps", "-p", str(int(record["pid"])), "-o", "command="],
                                capture_output=True, text=True, check=False)
    except (OSError, ValueError):
        return False
    actual = result.stdout.strip()
    # macOS reports the resolved interpreter path rather than sys.executable's
    # symlink.  Match the full argument list for Python module processes; it
    # includes the private database and env paths and therefore remains a
    # conservative guard against PID reuse.
    expected = command[1:] if len(command) > 2 and command[1] == "-m" else command
    return bool(actual) and all(str(part) in actual for part in expected)


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _wait_for_port(process: subprocess.Popen, port: int, timeout: float = 10.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if process.poll() is not None:
            raise RuntimeError(f"service on port {port} exited during startup")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"service on port {port} did not become ready")


def _state_path(config: DeliveryConfig) -> Path:
    return config.runtime / "processes.json"


def _read_processes(config: DeliveryConfig) -> dict:
    try:
        return json.loads(_state_path(config).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return {"processes": []}


def _write_processes(config: DeliveryConfig, processes: list[dict]) -> None:
    _private_dir(config.runtime)
    path = _state_path(config)
    path.write_text(json.dumps({"processes": processes}, indent=2) + "\n", encoding="utf-8")
    _private_file(path)


def setup(config: DeliveryConfig, *, install: bool = True) -> list[str]:
    """Prepare private directories and only create missing dependencies."""
    _private_dir(config.runtime)
    _private_dir(config.runtime / "logs")
    _private_dir(config.runtime / "backups")
    config.db.parent.mkdir(parents=True, exist_ok=True)
    if not config.env_file.exists():
        config.env_file.parent.mkdir(parents=True, exist_ok=True)
        config.env_file.write_text(
            "# Private literal environment for Leon; never source this file.\n"
            f"LEON_DASHBOARD_AUTH_MODE=required\n"
            f"LEON_DASHBOARD_TOKEN={secrets.token_urlsafe(32)}\n"
            f"LEON_DASHBOARD_PORT={config.port}\n"
            f"LEON_DB_PATH={config.db}\n",
            encoding="utf-8")
        _private_file(config.env_file)
    messages = [f"runtime={config.runtime}", f"env_file={config.env_file}"]
    py = shutil.which("python3") or sys.executable
    if sys.version_info < (3, 12):
        raise RuntimeError("Python 3.12 or newer is required")
    if not shutil.which("node"):
        raise RuntimeError("Node.js 22.13 or newer is required")
    if install and not (config.repo / ".venv").exists():
        subprocess.run([py, "-m", "venv", str(config.repo / ".venv")], cwd=config.repo, check=True)
        messages.append("created .venv")
    if install and not (config.repo / "apps" / "web" / "node_modules").exists():
        subprocess.run(["npm", "ci", "--ignore-scripts"], cwd=config.repo / "apps" / "web", check=True)
        messages.append("installed web dependencies")
    return messages


def start(config: DeliveryConfig) -> list[int]:
    existing = [int(item["pid"]) for item in _read_processes(config).get("processes", [])
                if _running(int(item["pid"])) and _owned_process(item)]
    if existing:
        raise RuntimeError("Leon is already running")
    for name, port in (("backend", config.port), ("web", config.web_port)):
        if not _port_available(port):
            raise RuntimeError(f"{name} port {port} is already in use")
    values, errors = _literal_env(config.env_file)
    if errors:
        raise RuntimeError("invalid environment file: " + "; ".join(errors))
    values.update(os.environ)
    values.update({"PYTHONPATH": str(config.repo / "src"), "LEON_DASHBOARD_PORT": str(config.port)})
    values["LEON_DB_PATH"] = str(config.db)
    values["LEON_BACKEND_URL"] = f"http://127.0.0.1:{config.port}"
    _private_dir(config.runtime / "logs")
    commands = [
        ("backend", [sys.executable, "-m", "leon_control_plane.server", "--host", "127.0.0.1", "--port", str(config.port), "--db", str(config.db), "--seed", str(config.repo / "state" / "control-plane.seed.json"), "--env-file", str(config.env_file)], config.port),
        ("worker", [sys.executable, "-m", "leon_control_plane.local_worker", "--db", str(config.db), "--seed", str(config.repo / "state" / "control-plane.seed.json"), "--env-file", str(config.env_file)], None),
        ("web", ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(config.web_port), "--strictPort"], config.web_port),
    ]
    records: list[dict] = []
    handles = []
    try:
        for name, command, readiness_port in commands:
            log = (config.runtime / "logs" / f"{name}.log").open("ab")
            handles.append(log)
            process_env = dict(values)
            process_env["LEON_ENV_FILE"] = str(config.env_file)
            process = subprocess.Popen(command, cwd=config.repo if name != "web" else config.repo / "apps" / "web",
                                       env=process_env, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            records.append({"name": name, "pid": process.pid, "command": command, "started": time.time()})
            if readiness_port is not None:
                _wait_for_port(process, readiness_port)
            elif process.poll() is not None:
                raise RuntimeError(f"{name} exited during startup")
    except Exception:
        for record in records:
            try:
                os.killpg(int(record["pid"]), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        for handle in handles:
            handle.close()
        _write_processes(config, [])
        raise
    for handle in handles:
        handle.close()
    _write_processes(config, records)
    return [record["pid"] for record in records]


def stop(config: DeliveryConfig, timeout: float = 8.0) -> int:
    records = _read_processes(config).get("processes", [])
    pids = [int(record["pid"]) for record in records
            if _running(int(record["pid"])) and _owned_process(record)]
    for pid in pids:
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    end = time.monotonic() + timeout
    while time.monotonic() < end and any(_process_group_running(pid) for pid in pids):
        time.sleep(0.1)
    for pid in pids:
        if _process_group_running(pid):
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
    _write_processes(config, [])
    return len(pids)


def _version(command: str) -> tuple[int, ...] | None:
    path = shutil.which(command)
    if not path:
        return None
    result = subprocess.run([path, "--version"], capture_output=True, text=True, check=False)
    text = result.stdout.strip().lstrip("v")
    try:
        return tuple(int(item) for item in text.split(".")[:3])
    except ValueError:
        return None


def doctor(config: DeliveryConfig) -> tuple[bool, list[str]]:
    checks: list[tuple[bool, str]] = []
    checks.append((sys.version_info >= (3, 12), f"python={sys.version_info.major}.{sys.version_info.minor}"))
    node = _version("node")
    checks.append((node is not None and node >= (22, 13), f"node={'.'.join(map(str, node)) if node else 'missing'}"))
    checks.append((config.env_file.exists(), f"env_file={'present' if config.env_file.exists() else 'missing'}"))
    values, errors = _literal_env(config.env_file)
    checks.append((not errors, "env_syntax=ok" if not errors else "env_syntax=invalid"))
    checks.append((values.get("LEON_DASHBOARD_AUTH_MODE", "required").lower() == "required", "auth_mode=" + values.get("LEON_DASHBOARD_AUTH_MODE", "required")))
    checks.append((bool(values.get("LEON_DASHBOARD_TOKEN")), "dashboard_token=" + ("configured" if values.get("LEON_DASHBOARD_TOKEN") else "missing")))
    checks.append((config.runtime.exists() and bool(os.stat(config.runtime).st_mode & stat.S_IRWXU), f"runtime={'present' if config.runtime.exists() else 'missing'}"))
    checks.append(((config.repo / "apps" / "web" / "node_modules").exists(), "web_dependencies=" + ("present" if (config.repo / "apps" / "web" / "node_modules").exists() else "missing")))
    live = [item["name"] for item in _read_processes(config).get("processes", [])
            if _running(int(item["pid"])) and _owned_process(item)]
    checks.append((True, "services=" + (",".join(live) if live else "stopped")))
    return all(ok for ok, _ in checks), [label for _, label in checks]


def backup(config: DeliveryConfig, destination: Path, *, force: bool = False) -> Path:
    destination = destination.resolve()
    if destination.exists() and not force:
        raise FileExistsError(f"refusing to overwrite {destination}; pass --force")
    if not config.db.exists():
        raise FileNotFoundError(config.db)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    if temporary.exists():
        temporary.unlink()
    source = sqlite3.connect(f"file:{config.db}?mode=ro", uri=True)
    target = sqlite3.connect(temporary)
    try:
        source.backup(target)
        result = target.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError("backup integrity check failed")
        target.commit()
    finally:
        target.close(); source.close()
    _private_file(temporary)
    if destination.exists() and force:
        destination.unlink()
    os.replace(temporary, destination)
    _private_file(destination)
    return destination


def restore(config: DeliveryConfig, source_path: Path, *, force: bool = False) -> Path:
    source_path = source_path.resolve()
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    if config.db.exists() and not force:
        raise FileExistsError(f"refusing to overwrite {config.db}; pass --force")
    config.db.parent.mkdir(parents=True, exist_ok=True)
    temporary = config.db.with_name(f".{config.db.name}.restore-{os.getpid()}")
    if temporary.exists():
        temporary.unlink()
    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    target = sqlite3.connect(temporary)
    try:
        source.backup(target)
        result = target.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError("backup integrity check failed")
        target.commit()
    finally:
        target.close(); source.close()
    _private_file(temporary)
    if config.db.exists() and force:
        config.db.unlink()
    os.replace(temporary, config.db)
    _private_file(config.db)
    return config.db


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local-only Leon setup and delivery tools")
    parser.add_argument("--repo", type=Path, default=None)
    sub = parser.add_subparsers(dest="action", required=True)
    setup_parser = sub.add_parser("setup")
    setup_parser.add_argument("--no-install", action="store_true")
    for name in ("start", "stop", "doctor"):
        sub.add_parser(name)
    for name in ("backup", "restore"):
        command = sub.add_parser(name)
        command.add_argument("path", type=Path)
        command.add_argument("--force", action="store_true")
    # Thin scripts place their action first; accept --repo there as well.
    for command in sub.choices.values():
        command.add_argument("--repo", type=Path, default=argparse.SUPPRESS)
    args = parser.parse_args(list(argv) if argv is not None else None)
    config = DeliveryConfig.from_env(args.repo)
    try:
        if args.action == "setup":
            print("\n".join(setup(config, install=not args.no_install)))
        elif args.action == "start":
            print("started pids=" + ",".join(map(str, start(config))))
        elif args.action == "stop":
            print(f"stopped={stop(config)}")
        elif args.action == "doctor":
            ok, checks = doctor(config)
            print("\n".join(checks))
            return 0 if ok else 1
        elif args.action == "backup":
            print(backup(config, args.path, force=args.force))
        elif args.action == "restore":
            print(restore(config, args.path, force=args.force))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"delivery error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
