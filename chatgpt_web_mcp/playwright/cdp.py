from __future__ import annotations

import asyncio
import os
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp import Context

from chatgpt_web_mcp.proxy import _proxy_env_for_subprocess, _without_proxy_env
from chatgpt_web_mcp.runtime.concurrency import _normalize_web_kind
from chatgpt_web_mcp.runtime.util import _coerce_error_text, _ctx_info
from chatgpt_web_mcp.env import _truthy_env


def _cdp_connect_timeout_ms() -> int:
    raw = (os.environ.get("CHATGPT_CDP_CONNECT_TIMEOUT_MS") or "").strip()
    if not raw:
        return 60_000
    try:
        return max(1_000, int(raw))
    except ValueError:
        return 60_000


def _cdp_connect_retries() -> int:
    raw = (os.environ.get("CHATGPT_CDP_CONNECT_RETRIES") or "").strip()
    if not raw:
        return 1
    try:
        return max(1, min(10, int(raw)))
    except ValueError:
        return 1


def _cdp_connect_retry_delay_seconds() -> float:
    raw = (os.environ.get("CHATGPT_CDP_CONNECT_RETRY_DELAY_SECONDS") or "").strip()
    if not raw:
        return 1.0
    try:
        return max(0.1, min(10.0, float(raw)))
    except ValueError:
        return 1.0


def _cdp_fallback_enabled(*, kind: str) -> bool:
    kind = _normalize_web_kind(kind)
    if kind == "chatgpt":
        name = "CHATGPT_CDP_FALLBACK_STORAGE_STATE"
    elif kind == "gemini":
        name = "GEMINI_CDP_FALLBACK_STORAGE_STATE"
    else:
        name = "QWEN_CDP_FALLBACK_STORAGE_STATE"
    # Default to fail-fast when CDP is configured but unavailable. Falling back to Playwright-managed
    # Chromium often triggers Cloudflare/anti-bot challenges and is not a reliable "fallback".
    return _truthy_env(name, False)


def _cdp_auto_start_enabled(*, kind: str) -> bool:
    kind = _normalize_web_kind(kind)
    if kind == "chatgpt":
        name = "CHATGPT_CDP_AUTO_START"
    elif kind == "gemini":
        name = "GEMINI_CDP_AUTO_START"
    else:
        name = "QWEN_CDP_AUTO_START"
    if kind == "gemini":
        default = _truthy_env("CHATGPT_CDP_AUTO_START", True)
    elif kind == "qwen":
        default = False
    else:
        default = True
    return _truthy_env(name, default)


def _cdp_auto_restart_enabled(*, kind: str) -> bool:
    kind = _normalize_web_kind(kind)
    if kind == "chatgpt":
        name = "CHATGPT_CDP_AUTO_RESTART"
    elif kind == "gemini":
        name = "GEMINI_CDP_AUTO_RESTART"
    else:
        name = "QWEN_CDP_AUTO_RESTART"
    if kind == "gemini":
        default = _truthy_env("CHATGPT_CDP_AUTO_RESTART", True)
    elif kind == "qwen":
        default = False
    else:
        default = True
    return _truthy_env(name, default)


def _repo_root() -> Path:
    # chatgpt_web_mcp/server.py → repo root
    return Path(__file__).resolve().parents[2]


def _chrome_start_script_path() -> Path:
    raw = (os.environ.get("CHATGPT_CHROME_START_SCRIPT") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return _repo_root() / "ops" / "chrome_start.sh"


def _chrome_stop_script_path() -> Path:
    raw = (os.environ.get("CHATGPT_CHROME_STOP_SCRIPT") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return _repo_root() / "ops" / "chrome_stop.sh"


def _chrome_start_script_path_for_kind(kind: str) -> Path:
    if kind == "qwen":
        raw = (os.environ.get("QWEN_CHROME_START_SCRIPT") or "").strip()
        if raw:
            return Path(raw).expanduser()
        return _repo_root() / "ops" / "qwen_chrome_start.sh"
    return _chrome_start_script_path()


def _chrome_stop_script_path_for_kind(kind: str) -> Path:
    if kind == "qwen":
        raw = (os.environ.get("QWEN_CHROME_STOP_SCRIPT") or "").strip()
        if raw:
            return Path(raw).expanduser()
        return _repo_root() / "ops" / "qwen_chrome_stop.sh"
    return _chrome_stop_script_path()


def _cdp_host_port(cdp_url: str) -> tuple[str, int] | None:
    try:
        parsed = urlparse(str(cdp_url or "").strip())
    except Exception:
        return None
    host = (parsed.hostname or "").strip()
    port = parsed.port
    if not host or not port:
        return None
    return host, int(port)


def _is_localhost_host(host: str) -> bool:
    h = (host or "").strip().lower()
    return h in {"127.0.0.1", "localhost", "::1"}


def _port_open(host: str, port: int, *, timeout_seconds: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=float(timeout_seconds)):
            return True
    except Exception:
        return False


_CDP_AUTOSTART_LOCK: asyncio.Lock | None = None


def _cdp_autostart_lock() -> asyncio.Lock:
    global _CDP_AUTOSTART_LOCK
    if _CDP_AUTOSTART_LOCK is None:
        _CDP_AUTOSTART_LOCK = asyncio.Lock()
    return _CDP_AUTOSTART_LOCK


async def _ensure_local_cdp_chrome_running(*, kind: str, cdp_url: str | None, ctx: Context | None) -> bool:
    if not cdp_url or not _cdp_auto_start_enabled(kind=kind):
        return False
    host_port = _cdp_host_port(cdp_url)
    if host_port is None:
        return False
    host, port = host_port
    if not _is_localhost_host(host):
        return False
    if _port_open(host, port):
        return True

    async with _cdp_autostart_lock():
        if _port_open(host, port):
            return True
        script = _chrome_start_script_path_for_kind(kind)
        if not script.exists():
            await _ctx_info(ctx, f"CDP {host}:{port} is down, but chrome start script is missing: {script}")
            return False
        await _ctx_info(ctx, f"CDP {host}:{port} is down; starting Chrome via {script} …")

        def _run() -> subprocess.CompletedProcess[str]:
            env = dict(os.environ)
            env.update(_proxy_env_for_subprocess())
            return subprocess.run(
                ["bash", str(script)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

        proc = await asyncio.to_thread(_run)
        if proc.returncode != 0:
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()
            msg = f"Failed to start Chrome for CDP ({host}:{port}). Exit code: {proc.returncode}."
            if out:
                msg += f" stdout: {_coerce_error_text(out, limit=800)}"
            if err:
                msg += f" stderr: {_coerce_error_text(err, limit=800)}"
            await _ctx_info(ctx, msg)
            return False
        return _port_open(host, port, timeout_seconds=0.5)


async def _restart_local_cdp_chrome(*, kind: str, cdp_url: str | None, ctx: Context | None) -> bool:
    if not cdp_url or not _cdp_auto_restart_enabled(kind=kind):
        return False
    host_port = _cdp_host_port(cdp_url)
    if host_port is None:
        return False
    host, port = host_port
    if not _is_localhost_host(host):
        return False

    async with _cdp_autostart_lock():
        stop_script = _chrome_stop_script_path_for_kind(kind)
        start_script = _chrome_start_script_path_for_kind(kind)
        if not start_script.exists():
            await _ctx_info(ctx, f"Cannot restart Chrome; start script is missing: {start_script}")
            return False
        if stop_script.exists():
            await _ctx_info(ctx, f"Restarting Chrome via {stop_script} …")
            env = dict(os.environ)
            env.update(_proxy_env_for_subprocess())
            stop_proc = await asyncio.to_thread(
                subprocess.run,
                ["bash", str(stop_script)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            if stop_proc.returncode != 0:
                out = (stop_proc.stdout or "").strip()
                err = (stop_proc.stderr or "").strip()
                msg = f"Chrome stop script exited non-zero ({stop_proc.returncode})."
                if out:
                    msg += f" stdout: {_coerce_error_text(out, limit=800)}"
                if err:
                    msg += f" stderr: {_coerce_error_text(err, limit=800)}"
                await _ctx_info(ctx, msg)

        await _ctx_info(ctx, f"Starting Chrome via {start_script} …")

        def _run_start() -> subprocess.CompletedProcess[str]:
            env = dict(os.environ)
            env.update(_proxy_env_for_subprocess())
            return subprocess.run(
                ["bash", str(start_script)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

        proc = await asyncio.to_thread(_run_start)
        if proc.returncode != 0:
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()
            msg = f"Failed to (re)start Chrome for CDP ({host}:{port}). Exit code: {proc.returncode}."
            if out:
                msg += f" stdout: {_coerce_error_text(out, limit=800)}"
            if err:
                msg += f" stderr: {_coerce_error_text(err, limit=800)}"
            await _ctx_info(ctx, msg)
            return False
        return _port_open(host, port, timeout_seconds=0.5)


async def _cdp_ws_url_from_http_endpoint(cdp_url: str, *, ctx: Context | None) -> str | None:
    base = str(cdp_url or "").strip().rstrip("/")
    if not base:
        return None
    url = f"{base}/json/version"

    def _op() -> str | None:
        try:
            with httpx.Client(timeout=5.0, follow_redirects=True, trust_env=False) as client:
                resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        ws = data.get("webSocketDebuggerUrl")
        if isinstance(ws, str) and ws.strip():
            return ws.strip()
        return None

    ws = await asyncio.to_thread(_op)
    if ws:
        await _ctx_info(ctx, f"Resolved CDP websocket endpoint: {ws}")
    return ws


def _http_endpoint_from_cdp_ws_url(ws_url: str) -> str | None:
    raw = str(ws_url or "").strip()
    if not raw:
        return None
    lower = raw.lower()
    if not (lower.startswith("ws://") or lower.startswith("wss://")):
        return None
    try:
        parsed = urlparse(raw)
    except Exception:
        return None
    scheme = str(parsed.scheme or "").lower()
    if scheme not in {"ws", "wss"}:
        return None
    if not parsed.netloc:
        return None
    http_scheme = "http" if scheme == "ws" else "https"
    return f"{http_scheme}://{parsed.netloc}"


async def _connect_over_cdp_resilient(p, cdp_url: str, *, ctx: Context | None):
    """Connect to Chrome via CDP, preferring the websocket debugger URL."""
    raw = str(cdp_url or "").strip()
    if not raw:
        raise ValueError("cdp_url is required")
    retries = _cdp_connect_retries()
    retry_delay = _cdp_connect_retry_delay_seconds()
    timeout_ms = _cdp_connect_timeout_ms()
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            if raw.startswith(("ws://", "wss://")):
                with _without_proxy_env():
                    try:
                        browser = await p.chromium.connect_over_cdp(raw, timeout=timeout_ms)
                        if browser is None:
                            raise RuntimeError("connect_over_cdp returned null browser")
                        return browser
                    except Exception as direct_error:
                        # Chrome restarts change the browser websocket path (`/devtools/browser/<id>`). If the caller
                        # provided a stale ws url, fall back to resolving the current websocket via the HTTP endpoint.
                        base = _http_endpoint_from_cdp_ws_url(raw)
                        if base:
                            ws = await _cdp_ws_url_from_http_endpoint(base, ctx=ctx)
                            if ws and ws != raw:
                                try:
                                    with _without_proxy_env():
                                        browser = await p.chromium.connect_over_cdp(ws, timeout=timeout_ms)
                                        if browser is None:
                                            raise RuntimeError("connect_over_cdp returned null browser")
                                        return browser
                                except Exception as resolved_error:
                                    raise resolved_error from direct_error
                        raise

            ws = await _cdp_ws_url_from_http_endpoint(raw, ctx=ctx)
            if ws:
                with _without_proxy_env():
                    browser = await p.chromium.connect_over_cdp(ws, timeout=timeout_ms)
                    if browser is None:
                        raise RuntimeError("connect_over_cdp returned null browser")
                    return browser

            # Best-effort: fall back to the raw HTTP endpoint.
            with _without_proxy_env():
                browser = await p.chromium.connect_over_cdp(raw, timeout=timeout_ms)
                if browser is None:
                    raise RuntimeError("connect_over_cdp returned null browser")
                return browser
        except Exception as exc:
            last_error = exc
            if attempt >= retries:
                raise
            await _ctx_info(
                ctx,
                f"CDP connect transient failure ({attempt}/{retries}): {type(exc).__name__}: {_coerce_error_text(str(exc), limit=220)}; retrying in {retry_delay:.1f}s",
            )
            await asyncio.sleep(retry_delay)

    if last_error is not None:
        raise last_error
    raise RuntimeError("CDP connect failed without a specific error")
