#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _run(cmd: list[str], *, timeout_seconds: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=max(1.0, float(timeout_seconds)),
    )


def _pid_alive(pid_file: Path) -> bool:
    try:
        raw = pid_file.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return False
    if not raw:
        return False
    try:
        pid = int(raw)
    except Exception:
        return False
    if pid <= 1:
        return False
    try:
        os.kill(pid, 0)
    except Exception:
        return False
    return True


def _port_open(host: str, port: int, *, timeout_seconds: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=max(0.2, float(timeout_seconds))):
            return True
    except Exception:
        return False


def _http_ok(url: str, *, timeout_seconds: float = 2.0) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": "chatgptrest-viewer-watchdog/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=max(0.2, float(timeout_seconds))) as resp:
            code = int(getattr(resp, "status", 0) or 0)
            return 200 <= code < 400
    except urllib.error.HTTPError as exc:
        return 200 <= int(getattr(exc, "code", 0) or 0) < 400
    except Exception:
        return False


def _detect_novnc_bind_host(run_dir: Path, *, default_host: str) -> str:
    env_host = str(os.environ.get("VIEWER_NOVNC_BIND_HOST") or "").strip()
    if env_host:
        return env_host
    host_file = run_dir / "novnc_bind_host.txt"
    try:
        text = host_file.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        text = ""
    return text or default_host


def _probe_host_for_bind_host(host: str) -> str:
    h = str(host or "").strip().lower()
    if h in {"0.0.0.0", "::", "[::]", "::0"}:
        return "127.0.0.1"
    return str(host or "").strip() or "127.0.0.1"


def _collect_viewer_status(*, repo_root: Path, status_timeout_seconds: float = 15.0) -> dict[str, Any]:
    del status_timeout_seconds  # kept for API compatibility / future extension.

    run_dir = repo_root / ".run" / "viewer"
    vnc_port = int(str(os.environ.get("VIEWER_VNC_PORT") or "5902") or 5902)
    novnc_port = int(str(os.environ.get("VIEWER_NOVNC_PORT") or "6082") or 6082)
    novnc_host = _detect_novnc_bind_host(run_dir, default_host="127.0.0.1")
    novnc_probe_host = _probe_host_for_bind_host(novnc_host)

    chrome_pid_file = run_dir / "chrome.pid"
    x11vnc_pid_file = run_dir / "x11vnc.pid"
    websockify_pid_file = run_dir / "websockify.pid"

    viewer_chrome_running = _pid_alive(chrome_pid_file)
    x11vnc_running = _pid_alive(x11vnc_pid_file)
    websockify_running = _pid_alive(websockify_pid_file)

    vnc_listening = _port_open("127.0.0.1", vnc_port)
    novnc_listening = _port_open(novnc_probe_host, novnc_port)
    novnc_http_ok = _http_ok(f"http://{novnc_probe_host}:{novnc_port}/vnc.html")

    return {
        "repo_root": str(repo_root),
        "viewer_run_dir": str(run_dir),
        "viewer_vnc_port": int(vnc_port),
        "viewer_novnc_port": int(novnc_port),
        "viewer_novnc_bind_host": novnc_host,
        "viewer_novnc_probe_host": novnc_probe_host,
        "chrome_pid_file": str(chrome_pid_file),
        "x11vnc_pid_file": str(x11vnc_pid_file),
        "websockify_pid_file": str(websockify_pid_file),
        "viewer_chrome_running": bool(viewer_chrome_running),
        "x11vnc_running": bool(x11vnc_running),
        "websockify_running": bool(websockify_running),
        "vnc_listening": bool(vnc_listening),
        "novnc_listening": bool(novnc_listening),
        "novnc_http_ok": bool(novnc_http_ok),
    }


def _viewer_health(status: dict[str, Any]) -> dict[str, Any]:
    novnc_listening = bool(status.get("novnc_listening"))
    vnc_listening = bool(status.get("vnc_listening"))
    novnc_http_ok = bool(status.get("novnc_http_ok"))
    chrome_running = bool(status.get("viewer_chrome_running"))
    ok = bool(novnc_listening and vnc_listening and novnc_http_ok and chrome_running)
    return {
        "ok": ok,
        "novnc_listening": novnc_listening,
        "vnc_listening": vnc_listening,
        "novnc_http_ok": novnc_http_ok,
        "viewer_chrome_running": chrome_running,
    }


def _chrome_diag(
    *,
    repo_root: Path,
    max_lines: int,
    gpu_exit15_threshold: int,
) -> dict[str, Any]:
    path = repo_root / ".run" / "viewer" / "chrome.log"
    out: dict[str, Any] = {
        "log_path": str(path),
        "log_exists": path.exists(),
        "max_lines": int(max_lines),
        "gpu_exit15_threshold": int(gpu_exit15_threshold),
        "gpu_exit15_count_recent": 0,
        "gpu_exit15_unhealthy": False,
    }
    if not path.exists():
        return out
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:  # noqa: BLE001
        out["read_error_type"] = type(exc).__name__
        out["read_error"] = str(exc)
        return out
    max_n = max(1, int(max_lines))
    recent = lines[-max_n:]
    sig = "GPU process exited unexpectedly: exit_code=15"
    count = sum(1 for line in recent if sig in str(line))
    threshold = max(1, int(gpu_exit15_threshold))
    out["gpu_exit15_count_recent"] = int(count)
    out["gpu_exit15_unhealthy"] = bool(count >= threshold)
    return out


def _pick_restart_mode(health: dict[str, Any]) -> str:
    # If noVNC/VNC path is down, recover full chain; if only Chrome is gone, restart Chrome only.
    if bool(health.get("gpu_exit15_unhealthy")):
        return "--full"
    if (not health["novnc_listening"]) or (not health["vnc_listening"]) or (not health["novnc_http_ok"]):
        return "--full"
    if not health["viewer_chrome_running"]:
        return "--chrome-only"
    return "--chrome-only"


def _safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)


def _env_float(name: str, default: float) -> float:
    raw = str(os.environ.get(name, "")).strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _env_int(name: str, default: int) -> int:
    raw = str(os.environ.get(name, "")).strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ChatgptREST viewer watchdog (detect + optional auto-heal).")
    mode_group = ap.add_mutually_exclusive_group()
    mode_group.add_argument("--heal", action="store_true", help="auto-heal unhealthy viewer (default)")
    mode_group.add_argument("--check", action="store_true", help="check only, do not restart")
    ap.add_argument(
        "--status-timeout-seconds",
        type=float,
        default=_env_float("CHATGPTREST_VIEWER_WATCHDOG_STATUS_TIMEOUT_SECONDS", 15.0),
    )
    ap.add_argument(
        "--sleep-after-restart-seconds",
        type=float,
        default=_env_float("CHATGPTREST_VIEWER_WATCHDOG_SLEEP_AFTER_RESTART_SECONDS", 1.0),
    )
    ap.add_argument(
        "--max-heal-attempts",
        type=int,
        default=_env_int("CHATGPTREST_VIEWER_WATCHDOG_MAX_HEAL_ATTEMPTS", 2),
    )
    ap.add_argument(
        "--gpu-exit15-threshold",
        type=int,
        default=_env_int("CHATGPTREST_VIEWER_WATCHDOG_GPU_EXIT15_THRESHOLD", 3),
    )
    ap.add_argument(
        "--chrome-log-lines",
        type=int,
        default=_env_int("CHATGPTREST_VIEWER_WATCHDOG_CHROME_LOG_LINES", 200),
    )
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    args = ap.parse_args(argv)

    heal = bool(args.heal or (not args.check))
    repo_root = Path(str(args.repo_root)).expanduser().resolve()
    restart_script = repo_root / "ops" / "viewer_restart.sh"

    result: dict[str, Any] = {
        "ok": False,
        "heal_mode": bool(heal),
        "repo_root": str(repo_root),
        "actions": [],
    }

    if not restart_script.exists():
        result["error_type"] = "RestartScriptNotFound"
        result["error"] = f"restart script not found: {restart_script}"
        print(_safe_json(result))
        return 2

    try:
        status = _collect_viewer_status(repo_root=repo_root, status_timeout_seconds=float(args.status_timeout_seconds))
    except Exception as exc:  # noqa: BLE001
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)
        print(_safe_json(result))
        return 2

    result["before"] = status
    health = _viewer_health(status)
    chrome_diag = _chrome_diag(
        repo_root=repo_root,
        max_lines=int(args.chrome_log_lines),
        gpu_exit15_threshold=int(args.gpu_exit15_threshold),
    )
    result["chrome_diag"] = chrome_diag
    if bool(chrome_diag.get("gpu_exit15_unhealthy")):
        # Even when ports are healthy, repeated GPU exit_code=15 often correlates with a
        # broken viewer tab on the VNC side; force a full chain restart.
        health = dict(health)
        health["ok"] = False
        health["gpu_exit15_unhealthy"] = True
    result["before_health"] = health
    if health["ok"]:
        result["ok"] = True
        result["message"] = "viewer healthy"
        print(_safe_json(result))
        return 0

    if not heal:
        result["message"] = "viewer unhealthy (check-only)"
        print(_safe_json(result))
        return 2

    attempts = max(1, int(args.max_heal_attempts))
    for idx in range(attempts):
        mode = _pick_restart_mode(health)
        action: dict[str, Any] = {"attempt": idx + 1, "mode": mode}
        proc = _run(["bash", str(restart_script), mode], timeout_seconds=120.0)
        action["restart_rc"] = int(proc.returncode)
        action["restart_stdout"] = (proc.stdout or "")[-1200:]
        action["restart_stderr"] = (proc.stderr or "")[-1200:]
        result["actions"].append(action)

        if proc.returncode != 0:
            continue

        time.sleep(max(0.2, float(args.sleep_after_restart_seconds)))
        try:
            status = _collect_viewer_status(repo_root=repo_root, status_timeout_seconds=float(args.status_timeout_seconds))
        except Exception as exc:  # noqa: BLE001
            action["status_error_type"] = type(exc).__name__
            action["status_error"] = str(exc)
            continue
        health = _viewer_health(status)
        action["after_health"] = health
        result["after"] = status
        result["after_health"] = health
        if health["ok"]:
            result["ok"] = True
            result["message"] = "viewer healed"
            print(_safe_json(result))
            return 0

    result["message"] = "viewer unhealthy after heal attempts"
    if "after_health" not in result:
        result["after_health"] = health
    print(_safe_json(result))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
