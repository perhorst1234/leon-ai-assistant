"""Bounded, read-only operating system status for the Leon dashboard.

The monitor deliberately uses only standard-library probes.  It never accepts a
command or path from an HTTP request and reports unavailable values explicitly.
"""
from __future__ import annotations

import ctypes
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Callable

from leon_control_plane.connector_registry import classify_connector_action


def _unavailable(reason: str) -> dict[str, Any]:
    return {"value": None, "status": "unavailable", "reason": reason}


def _darwin_boot_time() -> float | None:
    """Read Darwin kern.boottime through libc without launching a process."""
    if platform.system() != "Darwin":
        return None

    class Timeval(ctypes.Structure):
        _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_int)]

    try:
        value = Timeval()
        size = ctypes.c_size_t(ctypes.sizeof(value))
        libc = ctypes.CDLL(None, use_errno=True)
        sysctl = libc.sysctlbyname
        sysctl.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t]
        sysctl.restype = ctypes.c_int
        if sysctl(b"kern.boottime", ctypes.byref(value), ctypes.byref(size), None, 0) != 0:
            return None
        return float(value.tv_sec) + float(value.tv_usec) / 1_000_000
    except (AttributeError, OSError, TypeError, ValueError):
        return None


class ServerMonitor:
    """Collect a small snapshot; ``probe`` makes platform tests deterministic."""

    def __init__(self, *, paths: tuple[tuple[str, Path], ...] = (), probe: Any = None) -> None:
        self.paths = tuple(paths)
        self.probe = probe

    def _get(self, name: str, fallback: Callable[[], Any]) -> Any:
        if self.probe is not None and hasattr(self.probe, name):
            value = getattr(self.probe, name)
            return value() if callable(value) else value
        return fallback()

    def _uptime(self) -> Any:
        try:
            raw = Path("/proc/uptime").read_text(encoding="ascii", errors="strict").split()[0]
            return round(float(raw), 1)
        except (OSError, ValueError, IndexError):
            boot_time = _darwin_boot_time()
            return round(max(0.0, time.time() - boot_time), 1) if boot_time is not None else None

    def _load(self) -> Any:
        try:
            return tuple(round(float(value), 2) for value in os.getloadavg())
        except (AttributeError, OSError):
            return None

    def _memory(self) -> dict[str, Any]:
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            total = int(pages) * int(page_size)
            # Available memory is intentionally Linux-only; parsing this file
            # exposes only aggregate kernel counters, never process contents.
            available = None
            meminfo = Path("/proc/meminfo")
            if meminfo.exists():
                for line in meminfo.read_text(encoding="ascii", errors="strict").splitlines()[:80]:
                    if line.startswith("MemAvailable:"):
                        available = int(line.split()[1]) * 1024
                        break
            return {"total_bytes": total, "available_bytes": available, "status": "ok" if available is not None else "partial"}
        except (OSError, ValueError, TypeError, OverflowError):
            return {"total_bytes": None, "available_bytes": None, "status": "unavailable", "reason": "memory metrics unavailable on this platform"}

    def _disk(self) -> list[dict[str, Any]]:
        result = []
        for label, path in self.paths[:8]:
            try:
                stat = os.statvfs(path)
                total = stat.f_frsize * stat.f_blocks
                free = stat.f_frsize * stat.f_bavail
                result.append({"label": label, "total_bytes": total, "free_bytes": free, "status": "ok"})
            except (OSError, ValueError):
                result.append({"label": label, "total_bytes": None, "free_bytes": None, "status": "unavailable", "reason": "path unavailable"})
        return result

    def snapshot(self) -> dict[str, Any]:
        uptime = self._get("uptime", self._uptime)
        load = self._get("load", self._load)
        memory = self._get("memory", self._memory)
        if uptime is None:
            uptime = _unavailable("system uptime unavailable on this platform")
        else:
            uptime = {"value": uptime, "status": "ok"}
        if load is None:
            load = _unavailable("load average unavailable on this platform")
        else:
            load = {"value": list(load), "status": "ok"}
        process_ok = True
        try:
            os.kill(os.getpid(), 0)
        except OSError:
            process_ok = False
        health_status = "ok" if process_ok else "degraded"
        return {
            "ok": True,
            "enabled": True,
            "status": health_status,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "os": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "python": sys.version.split()[0]},
            "uptime": uptime,
            "load": load,
            "memory": memory,
            "disk": self._disk(),
            "process": {"running": process_ok, "status": "ok" if process_ok else "unavailable"},
            "health": {"status": health_status, "checks": {"leon_process": "ok" if process_ok else "unavailable"}},
            "permission": {"scope": "server:status_read", "read_only": True, "audit": "connector execution"},
            "bounded": True,
        }


def server_status(paths: tuple[tuple[str, Path], ...] = (), *, probe: Any = None) -> dict[str, Any]:
    return ServerMonitor(paths=paths, probe=probe).snapshot()


def server_status_request(
    store: Any, *, method: str, path: str,
    paths: tuple[tuple[str, Path], ...] = (), enabled: bool = True,
    probe: Any = None,
) -> dict[str, Any] | None:
    if method != "GET" or path != "/api/server/status":
        return None
    check = classify_connector_action(
        store.get_connector_manifest("server-monitor"),
        action_type="read", requested_scope="server:status_read",
    )
    if not enabled:
        check.update(
            decision="denied", allowed=False, execution_allowed=False,
            reason="Local server monitor is disabled.",
            audit_event_type="connector_permission_denied",
        )
        check_id = store.record_connector_permission_check(
            check, actor_type="system", actor_id="server-monitor", connector_executed=False,
        )
        return {
            "ok": True, "enabled": False, "status": "disabled",
            "permission_check_id": check_id, "bounded": True,
        }
    if check.get("decision") != "allowed" or not check.get("execution_allowed"):
        check_id = store.record_connector_permission_check(
            check, actor_type="system", actor_id="server-monitor", connector_executed=False,
        )
        raise ValueError(f"server_monitor_permission_denied:{check.get('decision', 'denied')}:{check_id}")
    result = server_status(paths, probe=probe)
    check_id = store.record_connector_permission_check(
        check, actor_type="system", actor_id="server-monitor", connector_executed=True,
    )
    result["permission_check_id"] = check_id
    return result
