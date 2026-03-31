from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.parse
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


_LOCAL_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0"}


def is_local_host(host: str) -> bool:
    return str(host or "").strip().lower() in _LOCAL_HOSTS


def parse_host_port_from_url(url: str, *, default_port: int = 18711) -> tuple[str, int] | None:
    try:
        parsed = urllib.parse.urlparse(str(url))
    except Exception:
        return None
    host = str(parsed.hostname or "").strip()
    if not host:
        return None
    try:
        port = int(parsed.port or default_port)
    except Exception:
        port = int(default_port)
    return host, port


def resolve_chatgptrest_api_host_port(
    *,
    base_url: str | None = None,
    env: Mapping[str, str] | None = None,
    default_host: str = "127.0.0.1",
    default_port: int = 18711,
) -> tuple[str, int]:
    env_map = env or os.environ
    raw_base = (str(base_url or env_map.get("CHATGPTREST_BASE_URL") or "").strip() or None)
    if raw_base:
        parsed = parse_host_port_from_url(raw_base, default_port=default_port)
        if parsed is not None:
            return parsed

    host = str(env_map.get("CHATGPTREST_HOST") or default_host).strip() or default_host
    port_raw = str(env_map.get("CHATGPTREST_PORT") or default_port).strip() or str(default_port)
    try:
        port = int(port_raw)
    except Exception:
        port = int(default_port)
    return host, port


def port_open(host: str, port: int, *, timeout_seconds: float = 0.2) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(float(timeout_seconds))
        try:
            return sock.connect_ex((str(host), int(port))) == 0
        finally:
            sock.close()
    except Exception:
        return False


def preferred_api_python_bin(*, repo_root: Path, fallback_python: str | None = None) -> Path:
    venv_bin = Path(repo_root) / ".venv" / "bin" / "python"
    venv_bin = venv_bin.resolve(strict=False)
    try:
        if venv_bin.exists():
            return venv_bin
    except Exception:
        pass
    return Path(str(fallback_python or sys.executable))


def start_local_api(
    *,
    repo_root: Path,
    host: str,
    port: int,
    action_log: Path,
    out_log: Path | None = None,
    wait_seconds: float = 0.0,
    fallback_python: str | None = None,
    python_bin: str | Path | None = None,
    probe_host: str | None = None,
    probe_timeout_seconds: float = 0.2,
    port_open_fn: Callable[[str, int], bool] | None = None,
    time_fn: Callable[[], float] | None = None,
    sleep_fn: Callable[[float], Any] | None = None,
    timestamp_fn: Callable[[], str] | None = None,
    env: Mapping[str, str] | None = None,
    action_label: str = "autostart api",
) -> tuple[bool, dict[str, Any]]:
    repo_root = Path(repo_root)
    action_log = Path(action_log)
    out_log = Path(out_log) if out_log is not None else (repo_root / "logs" / "chatgptrest_api.log").resolve()
    host_value = str(host).strip()
    port_value = int(port)
    probe_host_value = str(probe_host or ("127.0.0.1" if host_value == "0.0.0.0" else host_value)).strip()
    check_port = port_open_fn or (
        lambda current_host, current_port: port_open(
            current_host,
            current_port,
            timeout_seconds=probe_timeout_seconds,
        )
    )
    now = time_fn or time.time
    sleep = sleep_fn or time.sleep
    timestamp = timestamp_fn or (lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    if check_port(probe_host_value, port_value):
        return True, {
            "skipped": True,
            "reason": "api port already open",
            "host": host_value,
            "port": port_value,
            "probe_host": probe_host_value,
        }
    if not is_local_host(host_value):
        return False, {
            "error": "non-local host; refusing to autostart api",
            "host": host_value,
            "port": port_value,
        }

    python_path = Path(python_bin) if python_bin is not None else preferred_api_python_bin(
        repo_root=repo_root,
        fallback_python=fallback_python,
    )
    cmd = [
        str(python_path),
        "-m",
        "chatgptrest.api.app",
        "--host",
        host_value,
        "--port",
        str(port_value),
    ]
    proc: subprocess.Popen[Any] | None = None
    started_at = now()
    action_log.parent.mkdir(parents=True, exist_ok=True)
    out_log.parent.mkdir(parents=True, exist_ok=True)
    env_obj = dict(os.environ if env is None else env)
    env_obj["PYTHONUNBUFFERED"] = "1"

    try:
        with action_log.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp()}] {action_label}: {' '.join(cmd)}\n")
            f.flush()
        with out_log.open("a", encoding="utf-8") as out:
            proc = subprocess.Popen(
                cmd,
                cwd=str(repo_root),
                env=env_obj,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        meta: dict[str, Any] = {
            "started": True,
            "pid": (proc.pid if proc is not None else None),
            "host": host_value,
            "port": port_value,
            "probe_host": probe_host_value,
            "elapsed_ms": int(round((now() - started_at) * 1000)),
            "action_log": str(action_log),
            "out_log": str(out_log),
        }
        if wait_seconds <= 0:
            return True, meta

        deadline = now() + float(max(1.0, wait_seconds))
        while now() < deadline:
            if check_port(probe_host_value, port_value):
                meta["elapsed_ms"] = int(round((now() - started_at) * 1000))
                return True, meta
            if proc is not None:
                rc = proc.poll()
                if rc is not None:
                    meta["started"] = False
                    meta["returncode"] = int(rc)
                    meta["elapsed_ms"] = int(round((now() - started_at) * 1000))
                    return False, meta
            sleep(0.25)

        meta["started"] = False
        meta["error"] = "api did not open port in time"
        meta["elapsed_ms"] = int(round((now() - started_at) * 1000))
        return False, meta
    except Exception as exc:
        return False, {
            "started": False,
            "host": host_value,
            "port": port_value,
            "probe_host": probe_host_value,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "elapsed_ms": int(round((now() - started_at) * 1000)),
            "action_log": str(action_log),
            "out_log": str(out_log),
        }
