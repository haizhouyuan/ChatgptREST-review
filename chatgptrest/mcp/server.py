from __future__ import annotations

import asyncio
import inspect
import http.client
import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

from mcp.server.fastmcp import Context, FastMCP

from chatgptrest.core.control_plane import (
    parse_host_port_from_url as _parse_host_port_from_url,
    port_open as _shared_port_open,
    preferred_api_python_bin as _shared_preferred_api_python_bin,
    start_local_api as _shared_start_local_api,
)
from chatgptrest.core.db import connect as _db_connect
from chatgptrest.core.env import truthy_env as _truthy_env
from chatgptrest.core.rate_limit import try_reserve as _db_try_reserve_min_interval
from chatgptrest.core.rate_limit import try_reserve_fixed_window as _db_try_reserve_fixed_window
from chatgptrest.core.repair_jobs import (
    build_repair_autofix_params as _build_repair_autofix_params,
    build_repair_check_params as _build_repair_check_params,
    build_repair_input as _build_repair_input,
)
from chatgptrest.core.sre_jobs import (
    build_sre_fix_request_input as _build_sre_fix_request_input,
    build_sre_fix_request_params as _build_sre_fix_request_params,
)
from chatgptrest.mcp._bg_wait_config import BackgroundWaitConfig
from chatgptrest.mcp._providers import (
    detect_provider as _detect_provider,
    looks_like_chatgpt_conversation_url as _looks_like_chatgpt_conversation_url,
    looks_like_gemini_conversation_url as _looks_like_gemini_conversation_url,
    looks_like_qwen_conversation_url as _looks_like_qwen_conversation_url,
)
from chatgptrest.mcp import _answer_cache


DONEISH_STATUSES = {"completed", "error", "canceled", "blocked", "cooldown", "needs_followup"}
AUTO_REPAIR_STATUSES = {"error", "blocked", "cooldown", "needs_followup"}
AUTO_AUTOFIX_STATUSES = {"error", "cooldown"}
TERMINAL_STATUSES = {"completed", "error", "canceled"}

_NOTIFY_TASKS: dict[str, asyncio.Task[None]] = {}
_NOTIFY_LOCK = asyncio.Lock()

_BACKGROUND_WAIT_LOCK = asyncio.Lock()
_BACKGROUND_WAIT_TASKS: dict[str, asyncio.Task[None]] = {}
_BACKGROUND_WAIT_STATE: dict[str, dict[str, Any]] = {}
_BACKGROUND_WAIT_BY_JOB: dict[str, str] = {}
_BACKGROUND_WAIT_SEQ: int = 0

_AUTO_REPAIR_SUBMIT_LOCK = asyncio.Lock()
_AUTO_REPAIR_SUBMIT_TS: list[float] = []
_AUTO_AUTOFIX_SUBMIT_LOCK = asyncio.Lock()
_AUTO_AUTOFIX_SUBMIT_TS: list[float] = []
_AUTO_AUTOFIX_LAST_BY_JOB: dict[str, float] = {}
_REQUEST_ID_LOCK = threading.Lock()
_REQUEST_ID_SEQ = 0

_REPO_ROOT = Path(__file__).resolve().parents[2]
_API_AUTOSTART_LOCK = threading.Lock()
_API_AUTOSTART_LAST_TS: float = 0.0


def _qs(params: dict[str, Any]) -> str:
    clean = {k: v for k, v in params.items() if v is not None}
    return urllib.parse.urlencode(clean, doseq=True)




def _rate_limit_db_path() -> Path | None:
    if not _truthy_env("CHATGPTREST_MCP_PERSIST_RATE_LIMITS", False):
        return None
    raw = (os.environ.get("CHATGPTREST_DB_PATH") or "").strip()
    if not raw:
        raw = "state/jobdb.sqlite3"
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (_REPO_ROOT / p).resolve(strict=False)
    try:
        return p if p.exists() else None
    except Exception:
        return None


def _env(name: str, default: str) -> str:
    raw = os.environ.get(name)
    return raw.strip() if raw is not None and raw.strip() else default


def _sanitize_header_token(value: str | None, *, fallback: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raw = fallback
    out: list[str] = []
    for ch in raw:
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("-")
    clean = "".join(out).strip("-_.")
    return clean or fallback


def _client_name(default: str = "chatgptrest-mcp") -> str:
    return _sanitize_header_token(_env("CHATGPTREST_CLIENT_NAME", default), fallback=default)


def _client_instance() -> str:
    env_inst = (os.environ.get("CHATGPTREST_CLIENT_INSTANCE") or "").strip()
    if env_inst:
        return _sanitize_header_token(env_inst, fallback="chatgptrest-mcp")
    host = _sanitize_header_token(socket.gethostname(), fallback="localhost")
    return f"{host}-pid{os.getpid()}"


def _new_request_id(*, default_prefix: str) -> str:
    global _REQUEST_ID_SEQ
    prefix_raw = (os.environ.get("CHATGPTREST_REQUEST_ID_PREFIX") or "").strip() or default_prefix
    prefix = _sanitize_header_token(prefix_raw, fallback=default_prefix)
    ts_ms = int(time.time() * 1000.0)
    with _REQUEST_ID_LOCK:
        _REQUEST_ID_SEQ = (_REQUEST_ID_SEQ + 1) % 1_000_000_000
        seq = _REQUEST_ID_SEQ
    return f"{prefix}-{os.getpid()}-{ts_ms:x}-{seq:x}-{uuid.uuid4().hex[:8]}"


def _sanitize_header_text(value: str | None, *, fallback: str, max_chars: int = 200) -> str:
    raw = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if not raw:
        raw = str(fallback or "").strip()
    raw = " ".join(raw.split())
    if len(raw) > max(1, int(max_chars)):
        raw = raw[: max(1, int(max_chars))]
    return raw or fallback


def _default_cancel_reason(*, job_id: str | None = None) -> str:
    raw = (os.environ.get("CHATGPTREST_CANCEL_REASON_DEFAULT") or "").strip()
    if raw:
        return _sanitize_header_text(raw, fallback="mcp_cancel")
    jid = str(job_id or "").strip()
    if jid:
        return _sanitize_header_text(f"mcp_cancel:{jid}", fallback="mcp_cancel")
    return "mcp_cancel"


def _auto_repair_rate_limit() -> tuple[float, int]:
    window_raw = (os.environ.get("CHATGPTREST_MCP_AUTO_REPAIR_CHECK_WINDOW_SECONDS") or "").strip()
    max_raw = (os.environ.get("CHATGPTREST_MCP_AUTO_REPAIR_CHECK_MAX_PER_WINDOW") or "").strip()
    try:
        window_seconds = float(window_raw) if window_raw else 300.0
    except Exception:
        window_seconds = 300.0
    try:
        max_per_window = int(max_raw) if max_raw else 5
    except Exception:
        max_per_window = 5
    return max(0.0, window_seconds), max(0, max_per_window)


def _auto_autofix_rate_limit() -> tuple[float, int, float]:
    window_raw = (os.environ.get("CHATGPTREST_MCP_AUTO_AUTOFIX_WINDOW_SECONDS") or "").strip()
    max_raw = (os.environ.get("CHATGPTREST_MCP_AUTO_AUTOFIX_MAX_PER_WINDOW") or "").strip()
    min_raw = (os.environ.get("CHATGPTREST_MCP_AUTO_AUTOFIX_MIN_INTERVAL_SECONDS") or "").strip()
    try:
        window_seconds = float(window_raw) if window_raw else 1800.0
    except Exception:
        window_seconds = 1800.0
    try:
        max_per_window = int(max_raw) if max_raw else 3
    except Exception:
        max_per_window = 3
    try:
        min_interval_seconds = float(min_raw) if min_raw else 300.0
    except Exception:
        min_interval_seconds = 300.0
    return max(0.0, window_seconds), max(0, max_per_window), max(0.0, min_interval_seconds)


def _trim_window(ts_list: list[float], *, now: float, window_seconds: float) -> list[float]:
    win = max(0.0, float(window_seconds))
    if win <= 0:
        return []
    return [float(t) for t in ts_list if (now - float(t)) <= win]


def _fastmcp_host_port() -> tuple[str, int]:
    host = _env("FASTMCP_HOST", "127.0.0.1")
    port_raw = (os.environ.get("FASTMCP_PORT") or "").strip()
    if not port_raw:
        return host, 18712
    try:
        return host, int(port_raw)
    except ValueError:
        return host, 18712


def _fastmcp_stateless_http_default() -> bool:
    raw = (os.environ.get("FASTMCP_STATELESS_HTTP") or "").strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return True


def _base_url() -> str:
    return _env("CHATGPTREST_BASE_URL", "http://127.0.0.1:18711").rstrip("/")


def _auth_headers() -> dict[str, str]:
    client_name = _client_name("chatgptrest-mcp")
    headers: dict[str, str] = {
        "User-Agent": "chatgptrest-mcp/0.1.0",
        "X-Client-Name": client_name,
        "X-Client-Instance": _client_instance(),
        "X-Request-ID": _new_request_id(default_prefix=client_name),
    }
    token = (os.environ.get("CHATGPTREST_API_TOKEN") or "").strip()
    if not token:
        return headers
    headers["Authorization"] = f"Bearer {token}"
    return headers


def _ops_auth_headers() -> dict[str, str]:
    client_name = _client_name("chatgptrest-mcp")
    headers: dict[str, str] = {
        "User-Agent": "chatgptrest-mcp/0.1.0",
        "X-Client-Name": client_name,
        "X-Client-Instance": _client_instance(),
        "X-Request-ID": _new_request_id(default_prefix=client_name),
    }
    token = (os.environ.get("CHATGPTREST_OPS_TOKEN") or "").strip()
    if not token:
        token = (os.environ.get("CHATGPTREST_ADMIN_TOKEN") or "").strip()
    if not token:
        token = (os.environ.get("CHATGPTREST_API_TOKEN") or "").strip()
    if not token:
        return headers
    headers["Authorization"] = f"Bearer {token}"
    return headers


# Provider detection delegated to chatgptrest.mcp._providers
# _detect_provider, _looks_like_*_conversation_url imported at top.


# ── MCP HTTP failure hooks ───────────────────────────────────────────────

_MCP_FAILURE_DEDUPE: dict[str, float] = {}  # key -> last_report_ts


def _mcp_auto_report_issue_from_failure(
    *,
    failure_kind: str,
    error_type: str,
    error: str,
    url: str | None = None,
    method: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Auto-report MCP transport/HTTP failures to Issue Ledger."""
    import logging
    log = logging.getLogger("chatgptrest.mcp")
    try:
        base = _base_url()
        body: dict[str, Any] = {
            "project": "ChatgptREST",
            "title": f"MCP {failure_kind}: {error_type}",
            "kind": "mcp_transport_failure",
            "severity": "P2",
            "symptom": f"MCP failure during {method or '?'} {url or '?'}",
            "raw_error": str(error)[:4000],
            "source": "mcp_auto_report",
            "tags": ["auto", "mcp", failure_kind],
            "metadata": {
                "url": url,
                "method": method,
                **(extra or {}),
            },
        }
        resp = _http_json(
            method="POST",
            url=f"{base}/v1/issues/report",
            body=body,
            headers=_auth_headers(),
            timeout_seconds=10.0,
        )
        issue_id = resp.get("issue_id", "?")
        created = resp.get("created", False)
        log.info(
            "auto_report: issue=%s created=%s failure_kind=%s error_type=%s",
            issue_id, created, failure_kind, error_type,
        )
        return {"attempted": True, "ok": True, "issue_id": issue_id, "created": created}
    except Exception as exc:
        log.warning("auto_report failed: %s", exc, exc_info=True)
        return {"attempted": True, "ok": False, "error": str(exc)}


def _mcp_handle_http_failure(
    *,
    failure_kind: str | None,
    status_code: int | None,
    error_type: str,
    error: str,
    url: str,
    method: str,
) -> None:
    """Log HTTP failure to JSONL and optionally trigger auto-report."""
    log_enabled = _truthy_env("CHATGPTREST_MCP_FAILURE_LOG_ENABLED", False)
    autoreport_enabled = _truthy_env("CHATGPTREST_MCP_FAILURE_AUTOREPORT_ENABLED", False)
    log_path_raw = os.environ.get("CHATGPTREST_MCP_FAILURE_LOG_PATH", "").strip()

    issue_report: dict[str, Any] | None = None

    if failure_kind and autoreport_enabled:
        dedupe_seconds = 3600
        try:
            dedupe_seconds = int(os.environ.get("CHATGPTREST_MCP_FAILURE_AUTOREPORT_DEDUPE_SECONDS") or 3600)
        except Exception:
            pass
        dedupe_key = f"{failure_kind}:{error_type}"
        now = time.time()
        last_ts = _MCP_FAILURE_DEDUPE.get(dedupe_key, 0.0)
        if (now - last_ts) >= dedupe_seconds:
            _MCP_FAILURE_DEDUPE[dedupe_key] = now
            issue_report = _mcp_auto_report_issue_from_failure(
                failure_kind=failure_kind,
                error_type=error_type,
                error=error,
                url=url,
                method=method,
            )
        else:
            issue_report = {"deduped": True, "dedupe_key": dedupe_key}

        # §14: GC stale dedupe entries to prevent unbounded memory growth.
        gc_cutoff = now - dedupe_seconds * 2
        stale_keys = [k for k, ts in _MCP_FAILURE_DEDUPE.items() if ts < gc_cutoff][:100]
        for k in stale_keys:
            _MCP_FAILURE_DEDUPE.pop(k, None)

    if log_enabled and log_path_raw:
        try:
            log_path = Path(log_path_raw)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "ts": time.time(),
                "failure_kind": failure_kind,
                "status_code": status_code,
                "error_type": error_type,
                "error": error[:800],
                "url": url,
                "method": method,
            }
            if issue_report is not None:
                entry["issue_report"] = issue_report
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

def _http_json(
    *,
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 60.0,
    enable_failure_hooks: bool = True,
) -> dict[str, Any]:
    parsed_url = urllib.parse.urlparse(str(url))
    disable_proxy = str(parsed_url.hostname or "").strip().lower() in {"127.0.0.1", "localhost"}
    hdrs = dict(headers or {})
    data: bytes | None = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=str(method).upper())
    for k, v in hdrs.items():
        req.add_header(k, v)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if disable_proxy else None
    attempts = 2
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            if opener is None:
                resp_ctx = urllib.request.urlopen(req, timeout=float(timeout_seconds))
            else:
                resp_ctx = opener.open(req, timeout=float(timeout_seconds))
            with resp_ctx as resp:
                raw = resp.read()
                text = raw.decode("utf-8", errors="replace")
                return json.loads(text) if text.strip() else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            if enable_failure_hooks:
                try:
                    _mcp_handle_http_failure(
                        failure_kind=None,
                        status_code=e.code,
                        error_type="HTTPError",
                        error=f"HTTP {e.code} {e.reason}: {raw[:400]}",
                        url=url,
                        method=str(method).upper(),
                    )
                except Exception:
                    pass
            raise RuntimeError(f"HTTP {e.code} {e.reason}: {raw}") from e
        except (
            urllib.error.URLError,
            http.client.RemoteDisconnected,
            ConnectionError,
            TimeoutError,
            socket.timeout,
        ) as e:
            last_exc = e
            if _truthy_env("CHATGPTREST_MCP_AUTO_START_API", False) and attempt == 0:
                try:
                    if _maybe_autostart_api_for_base_url(_base_url()):
                        time.sleep(0.2)
                        continue
                except Exception:
                    pass
            if attempt + 1 < attempts:
                time.sleep(0.5)
                continue
            if enable_failure_hooks:
                try:
                    _mcp_handle_http_failure(
                        failure_kind="mcp_transport",
                        status_code=None,
                        error_type=type(e).__name__,
                        error=str(e),
                        url=url,
                        method=str(method).upper(),
                    )
                except Exception:
                    pass
            raise RuntimeError(f"HTTP request failed: {type(e).__name__}: {e}") from e

    raise RuntimeError(f"HTTP request failed: {type(last_exc).__name__}: {last_exc}")


def _parse_host_port_from_base_url(base_url: str) -> tuple[str, int] | None:
    parsed = _parse_host_port_from_url(str(base_url), default_port=0)
    if parsed is None:
        return None
    host, port = parsed
    if host == "0.0.0.0":
        host = "127.0.0.1"
    if int(port) <= 0:
        return None
    return host, port


def _port_open(host: str, port: int, *, timeout_seconds: float = 0.3) -> bool:
    return _shared_port_open(host, port, timeout_seconds=timeout_seconds)


def _preferred_api_python_bin() -> str:
    """
    Prefer the repo-local venv Python when present.

    The MCP server may be started outside the venv (e.g. system python) while the
    ChatgptREST runtime deps live in `.venv/`. Autostarting the API with
    `sys.executable` would then fail (e.g. missing uvicorn) and cause avoidable
    downtime for clients.
    """
    return str(_shared_preferred_api_python_bin(repo_root=_REPO_ROOT))


def _start_api_process(*, host: str, port: int) -> dict[str, Any]:
    ok, meta = _shared_start_local_api(
        repo_root=_REPO_ROOT,
        host=str(host),
        port=int(port),
        action_log=(_REPO_ROOT / "logs" / "chatgptrest_api.autostart.log").resolve(),
        out_log=(_REPO_ROOT / "logs" / "chatgptrest_api.log").resolve(),
        wait_seconds=0.0,
        action_label="autostart api",
    )
    return {"ok": bool(ok), **meta}


def _maybe_autostart_api_for_base_url(base_url: str) -> bool:
    global _API_AUTOSTART_LAST_TS
    hp = _parse_host_port_from_base_url(base_url)
    if hp is None:
        return False
    host, port = hp
    host_l = str(host).strip().lower()
    if host_l not in {"127.0.0.1", "localhost"}:
        return False
    if _port_open(host, port, timeout_seconds=0.2):
        return False

    with _API_AUTOSTART_LOCK:
        now = time.time()
        min_interval = float(os.environ.get("CHATGPTREST_MCP_AUTO_START_API_MIN_INTERVAL_SECONDS") or 30)
        if now - float(_API_AUTOSTART_LAST_TS) < max(0.0, min_interval):
            return False
        _API_AUTOSTART_LAST_TS = now

        ok, _meta = _shared_start_local_api(
            repo_root=_REPO_ROOT,
            host=str(host),
            port=int(port),
            action_log=(_REPO_ROOT / "logs" / "chatgptrest_api.autostart.log").resolve(),
            out_log=(_REPO_ROOT / "logs" / "chatgptrest_api.log").resolve(),
            wait_seconds=8.0,
            action_label="autostart api",
        )
        return bool(ok)


def _controller_pane() -> str | None:
    pane = (os.environ.get("CODEX_CONTROLLER_PANE") or "").strip()
    return pane or None


def _tmux_notify(message: str) -> None:
    pane = _controller_pane()
    if not pane:
        return
    try:
        subprocess.run(["tmux", "display-message", "-t", pane, str(message)], check=False, capture_output=True, text=True)
    except Exception:
        return


def _background_wait_retention_seconds() -> float:
    raw = (os.environ.get("CHATGPTREST_MCP_BACKGROUND_WAIT_RETENTION_SECONDS") or "").strip()
    try:
        value = float(raw) if raw else 24 * 60 * 60
    except Exception:
        value = 24 * 60 * 60
    return max(60.0, value)


def _mcp_wait_background_auto_resume_enabled() -> bool:
    return _truthy_env("CHATGPTREST_MCP_WAIT_BACKGROUND_AUTO_RESUME", True)


def _mcp_wait_background_auto_resume_timeout_seconds() -> int:
    raw = (os.environ.get("CHATGPTREST_MCP_WAIT_BACKGROUND_AUTO_RESUME_TIMEOUT_SECONDS") or "").strip()
    try:
        value = int(raw) if raw else 12 * 60 * 60
    except Exception:
        value = 12 * 60 * 60
    return max(60, min(value, 7 * 24 * 60 * 60))


def _mcp_wait_max_foreground_seconds() -> int:
    raw = (os.environ.get("CHATGPTREST_MCP_WAIT_MAX_FOREGROUND_SECONDS") or "").strip()
    try:
        value = int(raw) if raw else 90
    except Exception:
        value = 90
    return max(5, min(3600, value))


def _mcp_wait_auto_background_enabled() -> bool:
    return _truthy_env("CHATGPTREST_MCP_WAIT_AUTO_BACKGROUND", True)


def _mcp_wait_foreground_enabled() -> bool:
    if _truthy_env("CHATGPTREST_DISABLE_FOREGROUND_WAIT", False):
        return False
    return _truthy_env("CHATGPTREST_MCP_WAIT_FOREGROUND_ENABLED", True)


def _mcp_wait_auto_background_threshold_seconds(*, default_seconds: int) -> int:
    raw = (os.environ.get("CHATGPTREST_MCP_WAIT_AUTO_BACKGROUND_THRESHOLD_SECONDS") or "").strip()
    try:
        value = int(raw) if raw else int(default_seconds)
    except Exception:
        value = int(default_seconds)
    return max(5, min(12 * 60 * 60, value))


def _background_wait_state_view(state: dict[str, Any], *, include_result: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "watch_id": state.get("watch_id"),
        "job_id": state.get("job_id"),
        "watch_status": state.get("watch_status"),
        "started_at": state.get("started_at"),
        "updated_at": state.get("updated_at"),
        "ended_at": state.get("ended_at"),
        "timeout_seconds": state.get("timeout_seconds"),
        "poll_seconds": state.get("poll_seconds"),
        "running": bool(state.get("watch_status") == "running"),
        "done": bool(state.get("watch_status") in {"completed", "doneish", "error", "canceled"}),
        "terminal": bool(state.get("terminal")),
        "job_status": state.get("job_status"),
        "last_job_status": state.get("last_job_status"),
        "heartbeat_at": state.get("heartbeat_at"),
        "poll_count": int(state.get("poll_count") or 0),
        "last_retry_after_seconds": state.get("last_retry_after_seconds"),
        "last_slice_timeout_seconds": state.get("last_slice_timeout_seconds"),
        "notify_done": bool(state.get("notify_done")),
        "notify_controller": bool(state.get("notify_controller")),
    }
    if state.get("error_type"):
        out["error_type"] = state.get("error_type")
    if state.get("error"):
        out["error"] = state.get("error")
    if include_result and isinstance(state.get("result_job"), dict):
        out["result_job"] = state.get("result_job")
    return out


def _background_wait_gc_locked(*, now: float | None = None) -> None:
    ts = float(time.time() if now is None else now)
    keep_seconds = _background_wait_retention_seconds()
    stale_ids: list[str] = []
    for watch_id, state in list(_BACKGROUND_WAIT_STATE.items()):
        watch_status = str(state.get("watch_status") or "").strip().lower()
        if watch_status == "running":
            continue
        ended_at = float(state.get("ended_at") or state.get("updated_at") or ts)
        if (ts - ended_at) > keep_seconds:
            stale_ids.append(watch_id)
    for watch_id in stale_ids:
        state = _BACKGROUND_WAIT_STATE.pop(watch_id, None)
        _BACKGROUND_WAIT_TASKS.pop(watch_id, None)
        if isinstance(state, dict):
            jid = str(state.get("job_id") or "").strip()
            if jid and _BACKGROUND_WAIT_BY_JOB.get(jid) == watch_id:
                _BACKGROUND_WAIT_BY_JOB.pop(jid, None)


def _auto_repair_symptom_from_job(job: dict[str, Any]) -> str:
    kind = str(job.get("kind") or "").strip()
    status = str(job.get("status") or "").strip()
    phase = str(job.get("phase") or "").strip()
    reason_type = str(job.get("reason_type") or job.get("last_error_type") or "").strip()
    reason = str(job.get("reason") or job.get("last_error") or "").strip()
    parts: list[str] = []
    if kind:
        parts.append(f"kind={kind}")
    if status:
        parts.append(f"status={status}")
    if phase:
        parts.append(f"phase={phase}")
    if reason_type:
        parts.append(f"reason_type={reason_type}")
    if reason:
        parts.append(f"reason={reason[:200]}")
    return " | ".join(parts) or "job status abnormal"


async def _notify_done(job_id: str, *, initial: dict[str, Any] | None = None) -> None:
    base = _base_url()
    headers = _auth_headers()
    deadline = time.time() + 12 * 60 * 60
    while time.time() < deadline:
        try:
            job = await asyncio.to_thread(
                _http_json,
                method="GET",
                url=f"{base}/v1/jobs/{job_id}/wait?timeout_seconds=60&poll_seconds=1.0",
                headers=headers,
                timeout_seconds=75.0,
            )
        except Exception as exc:
            await asyncio.sleep(3.0)
            continue

        status = str(job.get("status") or "").strip().lower()
        if status in DONEISH_STATUSES:
            msg = f"[chatgptrest] job done: {job_id} status={status}"
            if status == "completed":
                path = str(job.get("path") or "").strip()
                if path:
                    msg += f" path={path}"
            _tmux_notify(msg)
            return
        await asyncio.sleep(1.0)


async def _maybe_notify_done(job: dict[str, Any], *, notify_done: bool) -> None:
    """Start a background _notify_done task for a newly submitted job.

    Extracted from 7 submit functions that all had this identical block.
    """
    if not (notify_done and isinstance(job, dict) and isinstance(job.get("job_id"), str)):
        return
    jid = str(job["job_id"])
    async with _NOTIFY_LOCK:
        existing = _NOTIFY_TASKS.get(jid)
        if existing is None or existing.done():
            t = asyncio.create_task(_notify_done(jid, initial=job))
            _NOTIFY_TASKS[jid] = t
            t.add_done_callback(lambda _t, jid0=jid: _NOTIFY_TASKS.pop(jid0, None))


async def _background_wait_runner(
    *,
    watch_id: str,
    job_id: str,
    timeout_seconds: int,
    poll_seconds: float,
    notify_controller: bool,
    notify_done: bool,
    auto_repair_check: bool,
    auto_repair_check_mode: str,
    auto_repair_check_timeout_seconds: int,
    auto_repair_check_probe_driver: bool,
    auto_repair_check_capture_ui: bool,
    auto_repair_check_recent_failures: int,
    auto_repair_notify_controller: bool,
    auto_repair_notify_done: bool,
    auto_codex_autofix: bool,
    auto_codex_autofix_timeout_seconds: int,
    auto_codex_autofix_model: str | None,
    auto_codex_autofix_max_risk: str,
    auto_codex_autofix_allow_actions: str | list[str] | None,
    auto_codex_autofix_apply_actions: bool,
    ctx: Context | None = None,
) -> None:
    if notify_controller:
        _tmux_notify(f"[chatgptrest] background wait started: job={job_id} watch={watch_id}")
    async def _on_progress(progress: dict[str, Any]) -> None:
        now = time.time()
        status = str((progress or {}).get("status") or "").strip().lower()
        retry_after = (progress or {}).get("retry_after_seconds")
        slice_timeout = (progress or {}).get("slice_timeout_seconds")
        async with _BACKGROUND_WAIT_LOCK:
            state = _BACKGROUND_WAIT_STATE.get(watch_id)
            if not isinstance(state, dict):
                return
            if str(state.get("watch_status") or "").strip().lower() != "running":
                return
            state["updated_at"] = now
            state["heartbeat_at"] = now
            state["poll_count"] = int(state.get("poll_count") or 0) + 1
            if status:
                state["job_status"] = status
                state["last_job_status"] = status
            if retry_after is not None:
                try:
                    state["last_retry_after_seconds"] = float(retry_after)
                except Exception:
                    pass
            if slice_timeout is not None:
                try:
                    state["last_slice_timeout_seconds"] = int(slice_timeout)
                except Exception:
                    pass

    try:
        job = await _chatgptrest_job_wait_impl(
            job_id=job_id,
            timeout_seconds=int(timeout_seconds),
            poll_seconds=float(poll_seconds),
            auto_repair_check=bool(auto_repair_check),
            auto_repair_check_mode=str(auto_repair_check_mode),
            auto_repair_check_timeout_seconds=int(auto_repair_check_timeout_seconds),
            auto_repair_check_probe_driver=bool(auto_repair_check_probe_driver),
            auto_repair_check_capture_ui=bool(auto_repair_check_capture_ui),
            auto_repair_check_recent_failures=int(auto_repair_check_recent_failures),
            auto_repair_notify_controller=bool(auto_repair_notify_controller),
            auto_repair_notify_done=bool(auto_repair_notify_done),
            auto_codex_autofix=bool(auto_codex_autofix),
            auto_codex_autofix_timeout_seconds=int(auto_codex_autofix_timeout_seconds),
            auto_codex_autofix_model=(str(auto_codex_autofix_model).strip() if auto_codex_autofix_model else None),
            auto_codex_autofix_max_risk=str(auto_codex_autofix_max_risk),
            auto_codex_autofix_allow_actions=auto_codex_autofix_allow_actions,
            auto_codex_autofix_apply_actions=bool(auto_codex_autofix_apply_actions),
            allow_auto_background=False,
            apply_foreground_cap=False,
            progress_callback=_on_progress,
            ctx=ctx,
        )
        status = str((job or {}).get("status") or "").strip().lower()
        terminal = status in TERMINAL_STATUSES
        watch_status = "completed" if terminal else "doneish"
        now = time.time()
        async with _BACKGROUND_WAIT_LOCK:
            state = _BACKGROUND_WAIT_STATE.get(watch_id)
            if isinstance(state, dict):
                state["watch_status"] = watch_status
                state["job_status"] = status
                state["terminal"] = bool(terminal)
                state["result_job"] = job if isinstance(job, dict) else {"job": job}
                state["updated_at"] = now
                state["ended_at"] = now
        if notify_done:
            _tmux_notify(f"[chatgptrest] background wait done: job={job_id} watch={watch_id} status={status}")
    except asyncio.CancelledError:
        now = time.time()
        async with _BACKGROUND_WAIT_LOCK:
            state = _BACKGROUND_WAIT_STATE.get(watch_id)
            if isinstance(state, dict):
                state["watch_status"] = "canceled"
                state["terminal"] = False
                state["updated_at"] = now
                state["ended_at"] = now
        if notify_done:
            _tmux_notify(f"[chatgptrest] background wait canceled: job={job_id} watch={watch_id}")
        raise
    except Exception as exc:
        now = time.time()
        async with _BACKGROUND_WAIT_LOCK:
            state = _BACKGROUND_WAIT_STATE.get(watch_id)
            if isinstance(state, dict):
                state["watch_status"] = "error"
                state["terminal"] = False
                state["error_type"] = type(exc).__name__
                state["error"] = str(exc)[:800]
                state["updated_at"] = now
                state["ended_at"] = now
        if notify_done:
            _tmux_notify(
                f"[chatgptrest] background wait error: job={job_id} watch={watch_id} {type(exc).__name__}: {str(exc)[:200]}"
            )


async def _background_wait_start(
    *,
    job_id: str,
    timeout_seconds: int,
    poll_seconds: float,
    notify_controller: bool,
    notify_done: bool,
    auto_repair_check: bool,
    auto_repair_check_mode: str,
    auto_repair_check_timeout_seconds: int,
    auto_repair_check_probe_driver: bool,
    auto_repair_check_capture_ui: bool,
    auto_repair_check_recent_failures: int,
    auto_repair_notify_controller: bool,
    auto_repair_notify_done: bool,
    auto_codex_autofix: bool,
    auto_codex_autofix_timeout_seconds: int,
    auto_codex_autofix_model: str | None,
    auto_codex_autofix_max_risk: str,
    auto_codex_autofix_allow_actions: str | list[str] | None,
    auto_codex_autofix_apply_actions: bool,
    force_restart: bool,
    ctx: Context | None = None,
) -> dict[str, Any]:
    jid = str(job_id or "").strip()
    if not jid:
        return {"ok": False, "error_type": "ValueError", "error": "job_id is required"}
    if _fastmcp_stateless_http_default():
        return {
            "ok": False,
            "error_type": "BackgroundWaitUnsupported",
            "error": "background wait requires FASTMCP_STATELESS_HTTP=0 (stateful MCP runtime)",
            "job_id": jid,
        }

    ts = time.time()
    async with _BACKGROUND_WAIT_LOCK:
        _background_wait_gc_locked(now=ts)
        existing_watch_id = _BACKGROUND_WAIT_BY_JOB.get(jid)
        if existing_watch_id:
            state = _BACKGROUND_WAIT_STATE.get(existing_watch_id)
            task = _BACKGROUND_WAIT_TASKS.get(existing_watch_id)
            if isinstance(state, dict):
                active = task is not None and not task.done()
                if active and not bool(force_restart):
                    out = _background_wait_state_view(state, include_result=True)
                    out["ok"] = True
                    out["already_running"] = True
                    return out
                # §12: force_restart — cancel old task and clean up state
                if active and bool(force_restart) and task is not None:
                    task.cancel()
                _BACKGROUND_WAIT_STATE.pop(existing_watch_id, None)
                _BACKGROUND_WAIT_TASKS.pop(existing_watch_id, None)

        global _BACKGROUND_WAIT_SEQ
        _BACKGROUND_WAIT_SEQ += 1
        watch_id = f"wait-{int(ts)}-{_BACKGROUND_WAIT_SEQ:04d}-{jid[:8]}"
        state = {
            "watch_id": watch_id,
            "job_id": jid,
            "watch_status": "running",
            "job_status": None,
            "terminal": False,
            "started_at": ts,
            "updated_at": ts,
            "ended_at": None,
            "heartbeat_at": ts,
            "poll_count": 0,
            "last_job_status": None,
            "last_retry_after_seconds": None,
            "last_slice_timeout_seconds": None,
            "timeout_seconds": int(timeout_seconds),
            "poll_seconds": float(poll_seconds),
            "notify_controller": bool(notify_controller),
            "notify_done": bool(notify_done),
            "result_job": None,
            "error_type": None,
            "error": None,
        }
        _BACKGROUND_WAIT_STATE[watch_id] = state
        _BACKGROUND_WAIT_BY_JOB[jid] = watch_id
        task = asyncio.create_task(
            _background_wait_runner(
                watch_id=watch_id,
                job_id=jid,
                timeout_seconds=int(timeout_seconds),
                poll_seconds=float(poll_seconds),
                notify_controller=bool(notify_controller),
                notify_done=bool(notify_done),
                auto_repair_check=bool(auto_repair_check),
                auto_repair_check_mode=str(auto_repair_check_mode),
                auto_repair_check_timeout_seconds=int(auto_repair_check_timeout_seconds),
                auto_repair_check_probe_driver=bool(auto_repair_check_probe_driver),
                auto_repair_check_capture_ui=bool(auto_repair_check_capture_ui),
                auto_repair_check_recent_failures=int(auto_repair_check_recent_failures),
                auto_repair_notify_controller=bool(auto_repair_notify_controller),
                auto_repair_notify_done=bool(auto_repair_notify_done),
                auto_codex_autofix=bool(auto_codex_autofix),
                auto_codex_autofix_timeout_seconds=int(auto_codex_autofix_timeout_seconds),
                auto_codex_autofix_model=(str(auto_codex_autofix_model).strip() if auto_codex_autofix_model else None),
                auto_codex_autofix_max_risk=str(auto_codex_autofix_max_risk),
                auto_codex_autofix_allow_actions=auto_codex_autofix_allow_actions,
                auto_codex_autofix_apply_actions=bool(auto_codex_autofix_apply_actions),
                ctx=ctx,
            )
        )
        _BACKGROUND_WAIT_TASKS[watch_id] = task
        task.add_done_callback(lambda _t, wid=watch_id: _BACKGROUND_WAIT_TASKS.pop(wid, None))
        out = _background_wait_state_view(state, include_result=False)
        out["ok"] = True
        out["already_running"] = False
        return out


def _background_wait_resolve_id_locked(*, watch_id: str | None = None, job_id: str | None = None) -> str | None:
    wid = str(watch_id or "").strip()
    if wid:
        return wid if wid in _BACKGROUND_WAIT_STATE else None
    jid = str(job_id or "").strip()
    if not jid:
        return None
    mapped = _BACKGROUND_WAIT_BY_JOB.get(jid)
    if mapped and mapped in _BACKGROUND_WAIT_STATE:
        return mapped
    return None


def _maybe_attach_client_info(payload: dict[str, Any], ctx: Context | None) -> dict[str, Any]:
    if not ctx:
        return payload
    try:
        sess = ctx.session
        params = sess.client_params if sess is not None else None
        info = getattr(params, "clientInfo", None) if params is not None else None
        name = getattr(info, "name", None) if info is not None else None
        version = getattr(info, "version", None) if info is not None else None
        if name or version:
            payload = dict(payload)
            client = dict(payload.get("client") or {})
            client.setdefault("mcp_client_name", name)
            client.setdefault("mcp_client_version", version)
            payload["client"] = client
    except Exception:
        return payload
    return payload


_HOST, _PORT = _fastmcp_host_port()

mcp = FastMCP(
    name="chatgptrest",
    instructions=(
        "Thin MCP wrapper for the ChatgptREST REST v1 contract.\n"
        "Use this to submit jobs and fetch answers without calling ChatGPT Web UI tools directly."
    ),
    host=_HOST,
    port=_PORT,
    stateless_http=_fastmcp_stateless_http_default(),
)


@mcp.tool(
    name="chatgptrest_job_create",
    description="Create/enqueue a job (POST /v1/jobs). Returns a JobView.",
    structured_output=True,
)
async def chatgptrest_job_create(
    *,
    idempotency_key: str,
    kind: str,
    input: dict[str, Any] | None = None,  # noqa: A002
    params: dict[str, Any] | None = None,
    client: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    payload = {
        "kind": str(kind),
        "input": dict(input or {}),
        "params": dict(params or {}),
        "client": (dict(client) if isinstance(client, dict) else None),
    }
    payload = _maybe_attach_client_info(payload, ctx)
    headers = {**_auth_headers(), "Idempotency-Key": str(idempotency_key)}
    return await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v1/jobs",
        body=payload,
        headers=headers,
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_job_get",
    description="Get job status (GET /v1/jobs/{job_id}).",
    structured_output=True,
)
async def chatgptrest_job_get(job_id: str, ctx: Context | None = None) -> dict[str, Any]:
    base = _base_url()
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/jobs/{urllib.parse.quote(str(job_id))}",
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


async def _chatgptrest_job_wait_impl(
    job_id: str,
    timeout_seconds: int = 60,
    poll_seconds: float = 1.0,
    auto_repair_check: bool = False,
    auto_repair_check_mode: str = "quick",
    auto_repair_check_timeout_seconds: int = 60,
    auto_repair_check_probe_driver: bool = True,
    auto_repair_check_capture_ui: bool = False,
    auto_repair_check_recent_failures: int = 5,
    auto_repair_notify_controller: bool = False,
    auto_repair_notify_done: bool = False,
    auto_codex_autofix: bool = True,
    auto_codex_autofix_timeout_seconds: int = 600,
    auto_codex_autofix_model: str | None = None,
    auto_codex_autofix_max_risk: str = "low",
    auto_codex_autofix_allow_actions: str | list[str] | None = None,
    auto_codex_autofix_apply_actions: bool = True,
    allow_auto_background: bool = True,
    apply_foreground_cap: bool = True,
    progress_callback: Callable[[dict[str, Any]], Any] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    requested_timeout = max(0.0, float(timeout_seconds))
    poll = max(0.2, float(poll_seconds))
    fg_cap = _mcp_wait_max_foreground_seconds()
    foreground_enabled = _mcp_wait_foreground_enabled()
    effective_timeout = requested_timeout
    clamped = False
    wait_warnings: list[dict[str, Any]] = []
    if apply_foreground_cap and requested_timeout > float(fg_cap):
        effective_timeout = float(fg_cap)
        clamped = True

    def _attach_wait_limits(job_view: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(job_view, dict):
            return job_view
        if (not clamped) and (not wait_warnings):
            return job_view
        out = dict(job_view)
        if clamped:
            out.setdefault("wait_mode", "foreground")
            out["wait_clamped"] = True
            out["requested_timeout_seconds"] = int(round(requested_timeout))
            out["effective_timeout_seconds"] = int(round(effective_timeout))
            out["foreground_timeout_cap_seconds"] = int(fg_cap)
        if wait_warnings:
            out["wait_warnings"] = list(wait_warnings)
        return out

    def _record_background_start_failure(stage: str, bg_started: Any) -> None:
        error_type: str | None = None
        error: str | None = None
        if isinstance(bg_started, dict):
            error_type = str(bg_started.get("error_type") or "").strip() or None
            error = str(bg_started.get("error") or "").strip() or None
        wait_warnings.append(
            {
                "type": "background_wait_start_failed",
                "stage": str(stage),
                "error_type": error_type,
                "error": error,
                "hint": "Falling back to bounded foreground wait for this call.",
            }
        )

    def _attach_background_poll_hint(out: dict[str, Any], *, watch_id: str | None) -> None:
        wid = str(watch_id or "").strip()
        if not wid:
            return
        out["next_action"] = {
            "tool": "chatgptrest_job_wait_background_get",
            "args": {"watch_id": wid},
            "recommended_poll_seconds": max(1, int(round(poll))),
        }

    # Hard mode: disable foreground waiting entirely for callers. We still allow
    # internal background runners to use the foreground path by setting
    # allow_auto_background=False when invoking this helper.
    if (not foreground_enabled) and allow_auto_background:
        background_timeout = int(max(1, round(requested_timeout if requested_timeout > 0 else float(_mcp_wait_background_auto_resume_timeout_seconds()))))
        bg_started = await _background_wait_start(
            job_id=str(job_id),
            timeout_seconds=background_timeout,
            poll_seconds=float(poll),
            notify_controller=False,
            notify_done=False,
            auto_repair_check=bool(auto_repair_check),
            auto_repair_check_mode=str(auto_repair_check_mode),
            auto_repair_check_timeout_seconds=int(auto_repair_check_timeout_seconds),
            auto_repair_check_probe_driver=bool(auto_repair_check_probe_driver),
            auto_repair_check_capture_ui=bool(auto_repair_check_capture_ui),
            auto_repair_check_recent_failures=int(auto_repair_check_recent_failures),
            auto_repair_notify_controller=bool(auto_repair_notify_controller),
            auto_repair_notify_done=bool(auto_repair_notify_done),
            auto_codex_autofix=bool(auto_codex_autofix),
            auto_codex_autofix_timeout_seconds=int(auto_codex_autofix_timeout_seconds),
            auto_codex_autofix_model=(str(auto_codex_autofix_model).strip() if auto_codex_autofix_model else None),
            auto_codex_autofix_max_risk=str(auto_codex_autofix_max_risk),
            auto_codex_autofix_allow_actions=auto_codex_autofix_allow_actions,
            auto_codex_autofix_apply_actions=bool(auto_codex_autofix_apply_actions),
            force_restart=False,
            ctx=ctx,
        )
        bg_ok = isinstance(bg_started, dict) and bool(bg_started.get("ok"))
        if not bg_ok:
            _record_background_start_failure("foreground_disabled", bg_started)
            # Safety fallback: still execute bounded foreground wait so callers
            # don't get a non-progressing background watch in stateless mode.
            foreground_enabled = True
        else:
            try:
                snapshot = await asyncio.to_thread(
                    _http_json,
                    method="GET",
                    url=f"{base}/v1/jobs/{urllib.parse.quote(str(job_id))}",
                    headers=_auth_headers(),
                    timeout_seconds=30.0,
                )
            except Exception:
                snapshot = {"ok": True, "job_id": str(job_id), "status": "in_progress"}
            if not isinstance(snapshot, dict):
                snapshot = {"ok": True, "job_id": str(job_id), "status": "in_progress"}
            out = dict(snapshot)
            out["wait_mode"] = "background"
            out["background_wait_started"] = True
            out["watch_id"] = bg_started.get("watch_id")
            out["watch_status"] = bg_started.get("watch_status")
            out["watch_running"] = bool(bg_started.get("running", True))
            out["already_running"] = bool(bg_started.get("already_running", False))
            out["foreground_disabled"] = True
            out["requested_timeout_seconds"] = int(round(requested_timeout))
            out["background_timeout_seconds"] = int(background_timeout)
            out["foreground_timeout_cap_seconds"] = int(fg_cap)
            _attach_background_poll_hint(out, watch_id=str(bg_started.get("watch_id") or ""))
            return out

    if allow_auto_background and _mcp_wait_auto_background_enabled():
        threshold = _mcp_wait_auto_background_threshold_seconds(default_seconds=fg_cap)
        if requested_timeout > float(threshold):
            bg_started = await _background_wait_start(
                job_id=str(job_id),
                timeout_seconds=int(max(1, round(requested_timeout))),
                poll_seconds=float(poll),
                notify_controller=False,
                notify_done=False,
                auto_repair_check=bool(auto_repair_check),
                auto_repair_check_mode=str(auto_repair_check_mode),
                auto_repair_check_timeout_seconds=int(auto_repair_check_timeout_seconds),
                auto_repair_check_probe_driver=bool(auto_repair_check_probe_driver),
                auto_repair_check_capture_ui=bool(auto_repair_check_capture_ui),
                auto_repair_check_recent_failures=int(auto_repair_check_recent_failures),
                auto_repair_notify_controller=bool(auto_repair_notify_controller),
                auto_repair_notify_done=bool(auto_repair_notify_done),
                auto_codex_autofix=bool(auto_codex_autofix),
                auto_codex_autofix_timeout_seconds=int(auto_codex_autofix_timeout_seconds),
                auto_codex_autofix_model=(str(auto_codex_autofix_model).strip() if auto_codex_autofix_model else None),
                auto_codex_autofix_max_risk=str(auto_codex_autofix_max_risk),
                auto_codex_autofix_allow_actions=auto_codex_autofix_allow_actions,
                auto_codex_autofix_apply_actions=bool(auto_codex_autofix_apply_actions),
                force_restart=False,
                ctx=ctx,
            )
            if isinstance(bg_started, dict) and bool(bg_started.get("ok")):
                try:
                    snapshot = await asyncio.to_thread(
                        _http_json,
                        method="GET",
                        url=f"{base}/v1/jobs/{urllib.parse.quote(str(job_id))}",
                        headers=_auth_headers(),
                        timeout_seconds=30.0,
                    )
                except Exception:
                    snapshot = {"ok": True, "job_id": str(job_id), "status": "in_progress"}
                if not isinstance(snapshot, dict):
                    snapshot = {"ok": True, "job_id": str(job_id), "status": "in_progress"}
                out = dict(snapshot)
                out["wait_mode"] = "background"
                out["background_wait_started"] = True
                out["watch_id"] = bg_started.get("watch_id")
                out["watch_status"] = bg_started.get("watch_status")
                out["watch_running"] = bool(bg_started.get("running", True))
                out["already_running"] = bool(bg_started.get("already_running", False))
                out["requested_timeout_seconds"] = int(round(requested_timeout))
                out["background_timeout_seconds"] = int(max(1, round(requested_timeout)))
                out["foreground_timeout_cap_seconds"] = int(fg_cap)
                _attach_background_poll_hint(out, watch_id=str(bg_started.get("watch_id") or ""))
                return out
            _record_background_start_failure("auto_background", bg_started)

    deadline = time.time() + effective_timeout

    async def _emit_progress(payload: dict[str, Any]) -> None:
        cb = progress_callback
        if cb is None:
            return
        try:
            maybe = cb(payload)
            if inspect.isawaitable(maybe):
                await maybe
        except Exception:
            return

    job: dict[str, Any] | None = None
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            if isinstance(job, dict):
                return _attach_wait_limits(job)
            job = await asyncio.to_thread(
                _http_json,
                method="GET",
                url=f"{base}/v1/jobs/{urllib.parse.quote(str(job_id))}",
                headers=_auth_headers(),
                timeout_seconds=30.0,
            )
            if isinstance(job, dict):
                return _attach_wait_limits(job)
            return {"ok": False, "error_type": "TypeError", "error": "job_get returned non-dict"}

        slice_timeout_seconds = int(max(1.0, min(60.0, remaining)))
        qs = urllib.parse.urlencode(
            {"timeout_seconds": slice_timeout_seconds, "poll_seconds": poll},
            doseq=False,
        )
        job = await asyncio.to_thread(
            _http_json,
            method="GET",
            url=f"{base}/v1/jobs/{urllib.parse.quote(str(job_id))}/wait?{qs}",
            headers=_auth_headers(),
            timeout_seconds=float(max(5, slice_timeout_seconds)) + 15.0,
        )
        if not isinstance(job, dict):
            return {"ok": False, "error_type": "TypeError", "error": "job_wait returned non-dict"}
        await _emit_progress(
            {
                "ts": time.time(),
                "job_id": str(job_id),
                "status": str(job.get("status") or "").strip().lower(),
                "retry_after_seconds": job.get("retry_after_seconds"),
                "slice_timeout_seconds": int(slice_timeout_seconds),
                "remaining_seconds": max(0.0, float(deadline - time.time())),
                "mode": "foreground",
            }
        )

        if auto_codex_autofix:
            status = str(job.get("status") or "").strip().lower()
            kind = str(job.get("kind") or "").strip().lower()
            reason_type = str(job.get("reason_type") or "").strip()
            if (
                status in AUTO_AUTOFIX_STATUSES
                and reason_type
                and kind in {"chatgpt_web.ask", "gemini_web.ask", "qwen_web.ask"}
                and not kind.startswith("repair.")
            ):
                    if reason_type.strip().lower() not in {"inprogress"}:
                        try:
                            window_seconds, max_per_window, min_interval_seconds = _auto_autofix_rate_limit()
                            should_submit = True
                            now = time.time()
                            db_path = _rate_limit_db_path()
                            if db_path is not None and (window_seconds > 0 or min_interval_seconds > 0):
                                try:
                                    with _db_connect(db_path) as conn:
                                        conn.execute("BEGIN IMMEDIATE")
                                        if window_seconds > 0 and max_per_window > 0:
                                            wait_s = _db_try_reserve_fixed_window(
                                                conn,
                                                key="mcp:auto_codex_autofix",
                                                window_seconds=int(window_seconds),
                                                max_per_window=int(max_per_window),
                                                now=now,
                                            )
                                            if wait_s > 0:
                                                conn.rollback()
                                                should_submit = False
                                                job = dict(job)
                                                job["auto_codex_autofix"] = {
                                                    "submitted": False,
                                                    "rate_limited": True,
                                                    "reason": "window_limit",
                                                    "window_seconds": float(window_seconds),
                                                    "max_per_window": int(max_per_window),
                                                    "wait_seconds": round(float(wait_s), 3),
                                                }
                                        if should_submit and min_interval_seconds > 0:
                                            wait_s = _db_try_reserve_min_interval(
                                                conn,
                                                key=f"mcp:auto_codex_autofix:job:{job_id}",
                                                min_interval_seconds=int(min_interval_seconds),
                                            )
                                            if wait_s > 0:
                                                conn.rollback()
                                                should_submit = False
                                                job = dict(job)
                                                job["auto_codex_autofix"] = {
                                                    "submitted": False,
                                                    "rate_limited": True,
                                                    "reason": "min_interval",
                                                    "min_interval_seconds": float(min_interval_seconds),
                                                    "wait_seconds": round(float(wait_s), 3),
                                                }
                                        if should_submit:
                                            conn.commit()
                                except Exception:
                                    # Fallback to in-process rate limits if DB is unavailable.
                                    db_path = None

                            if db_path is None:
                                async with _AUTO_AUTOFIX_SUBMIT_LOCK:
                                    global _AUTO_AUTOFIX_SUBMIT_TS, _AUTO_AUTOFIX_LAST_BY_JOB
                                    _AUTO_AUTOFIX_SUBMIT_TS = _trim_window(
                                        _AUTO_AUTOFIX_SUBMIT_TS, now=now, window_seconds=window_seconds
                                    )
                                    last_ts = float(_AUTO_AUTOFIX_LAST_BY_JOB.get(str(job_id), 0.0) or 0.0)
                                    if min_interval_seconds > 0 and last_ts > 0 and (now - last_ts) < min_interval_seconds:
                                        should_submit = False
                                        job = dict(job)
                                        job["auto_codex_autofix"] = {
                                            "submitted": False,
                                            "rate_limited": True,
                                            "reason": "min_interval",
                                            "min_interval_seconds": float(min_interval_seconds),
                                            "seconds_since_last": round(float(now - last_ts), 3),
                                        }
                                    elif (
                                        window_seconds > 0
                                        and max_per_window > 0
                                        and len(_AUTO_AUTOFIX_SUBMIT_TS) >= max_per_window
                                    ):
                                        should_submit = False
                                        job = dict(job)
                                        job["auto_codex_autofix"] = {
                                            "submitted": False,
                                            "rate_limited": True,
                                            "reason": "window_limit",
                                            "window_seconds": float(window_seconds),
                                            "max_per_window": int(max_per_window),
                                            "recent_submissions": len(_AUTO_AUTOFIX_SUBMIT_TS),
                                        }
                                    else:
                                        _AUTO_AUTOFIX_SUBMIT_TS.append(now)
                                        _AUTO_AUTOFIX_LAST_BY_JOB[str(job_id)] = now

                            if should_submit and "auto_codex_autofix" not in job:
                                bucket = int(now // max(1.0, float(window_seconds or 1800.0)))
                                idem = f"mcp:auto_codex_autofix:{job_id}:{bucket}"
                                symptom = _auto_repair_symptom_from_job(job)
                                conversation_url = str(job.get("conversation_url") or "").strip() or None
                                repair = await chatgptrest_repair_autofix_submit(
                                    idempotency_key=idem,
                                    job_id=str(job_id),
                                    symptom=symptom,
                                    conversation_url=conversation_url,
                                    timeout_seconds=int(auto_codex_autofix_timeout_seconds),
                                    model=(str(auto_codex_autofix_model).strip() if auto_codex_autofix_model else None),
                                    max_risk=str(auto_codex_autofix_max_risk),
                                    allow_actions=auto_codex_autofix_allow_actions,
                                    apply_actions=bool(auto_codex_autofix_apply_actions),
                                    notify_controller=False,
                                    notify_done=False,
                                    ctx=ctx,
                                )
                                repair_job_id = str((repair or {}).get("job_id") or "").strip() or None
                                job = dict(job)
                                job["auto_codex_autofix"] = {
                                    "submitted": True,
                                    "repair_job_id": repair_job_id,
                                    "repair_status": str((repair or {}).get("status") or "").strip() or None,
                                    "idempotency_key": idem,
                                }
                        except Exception as exc:
                            job = dict(job)
                            job["auto_codex_autofix"] = {
                                "submitted": False,
                                "error_type": type(exc).__name__,
                                "error": str(exc)[:800],
                            }

        if auto_repair_check:
            status = str(job.get("status") or "").strip().lower()
            kind = str(job.get("kind") or "").strip().lower()
            if status in AUTO_REPAIR_STATUSES and not kind.startswith("repair."):
                try:
                    window_seconds, max_per_window = _auto_repair_rate_limit()
                    db_path = _rate_limit_db_path()
                    if db_path is not None and window_seconds > 0 and max_per_window > 0:
                        now = time.time()
                        try:
                            with _db_connect(db_path) as conn:
                                conn.execute("BEGIN IMMEDIATE")
                                wait_s = _db_try_reserve_fixed_window(
                                    conn,
                                    key="mcp:auto_repair_check",
                                    window_seconds=int(window_seconds),
                                    max_per_window=int(max_per_window),
                                    now=now,
                                )
                                if wait_s > 0:
                                    conn.rollback()
                                    job = dict(job)
                                    job["auto_repair_check"] = {
                                        "submitted": False,
                                        "rate_limited": True,
                                        "window_seconds": float(window_seconds),
                                        "max_per_window": int(max_per_window),
                                        "wait_seconds": round(float(wait_s), 3),
                                    }
                                else:
                                    conn.commit()
                        except Exception:
                            db_path = None

                    if db_path is None and window_seconds > 0 and max_per_window > 0:
                        async with _AUTO_REPAIR_SUBMIT_LOCK:
                            now = time.time()
                            global _AUTO_REPAIR_SUBMIT_TS
                            _AUTO_REPAIR_SUBMIT_TS = _trim_window(_AUTO_REPAIR_SUBMIT_TS, now=now, window_seconds=window_seconds)
                            if len(_AUTO_REPAIR_SUBMIT_TS) >= max_per_window:
                                job = dict(job)
                                job["auto_repair_check"] = {
                                    "submitted": False,
                                    "rate_limited": True,
                                    "window_seconds": float(window_seconds),
                                    "max_per_window": int(max_per_window),
                                    "recent_submissions": len(_AUTO_REPAIR_SUBMIT_TS),
                                }
                            else:
                                _AUTO_REPAIR_SUBMIT_TS.append(now)

                    if "auto_repair_check" not in job:
                        symptom = _auto_repair_symptom_from_job(job)
                        conversation_url = str(job.get("conversation_url") or "").strip() or None
                        repair = await chatgptrest_repair_check_submit(
                            idempotency_key=f"mcp:auto_repair_check:{job_id}",
                            job_id=str(job_id),
                            symptom=symptom,
                            conversation_url=conversation_url,
                            mode=str(auto_repair_check_mode),
                            timeout_seconds=int(auto_repair_check_timeout_seconds),
                            probe_driver=bool(auto_repair_check_probe_driver),
                            capture_ui=bool(auto_repair_check_capture_ui),
                            recent_failures=int(auto_repair_check_recent_failures),
                            notify_controller=bool(auto_repair_notify_controller),
                            notify_done=bool(auto_repair_notify_done),
                            ctx=ctx,
                        )
                        repair_job_id = str((repair or {}).get("job_id") or "").strip() or None
                        job = dict(job)
                        job["auto_repair_check"] = {
                            "submitted": True,
                            "repair_job_id": repair_job_id,
                            "repair_status": str((repair or {}).get("status") or "").strip() or None,
                        }
                except Exception as exc:
                    job = dict(job)
                    job["auto_repair_check"] = {
                        "submitted": False,
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:800],
                    }

        status = str(job.get("status") or "").strip().lower()
        if status in TERMINAL_STATUSES:
            return _attach_wait_limits(job)
        if status in {"blocked", "needs_followup"}:
            return _attach_wait_limits(job)
        if status != "cooldown":
            # queued/in_progress (or unknown): keep waiting until deadline.
            continue

        retry_after_raw = job.get("retry_after_seconds")
        try:
            retry_after = float(retry_after_raw) if retry_after_raw is not None else 1.0
        except Exception:
            retry_after = 1.0
        retry_after = max(0.2, retry_after)
        if retry_after > remaining:
            return _attach_wait_limits(job)
        await asyncio.sleep(retry_after)


@mcp.tool(
    name="chatgptrest_job_wait",
    description=(
        "Wait for a job via GET /v1/jobs/{job_id}/wait.\n"
        "Behavior:\n"
        "- Returns immediately for terminal statuses: completed/error/canceled.\n"
        "- If the requested timeout is long, it may auto-handoff to background waiting and return watch metadata.\n"
        "- If the job enters cooldown, this tool automatically keeps waiting (sleeping until retry_after_seconds)\n"
        "  until it becomes terminal or the effective foreground timeout elapses.\n"
        "- For blocked/needs_followup, returns the current job view so callers can decide next steps.\n"
        "- Optional: auto-trigger Codex-driven autofix (`repair.autofix`) for retryable states, then keep waiting."
    ),
    structured_output=True,
)
async def chatgptrest_job_wait(
    job_id: str,
    timeout_seconds: int = 60,
    poll_seconds: float = 1.0,
    auto_repair_check: bool = False,
    auto_repair_check_mode: str = "quick",
    auto_repair_check_timeout_seconds: int = 60,
    auto_repair_check_probe_driver: bool = True,
    auto_repair_check_capture_ui: bool = False,
    auto_repair_check_recent_failures: int = 5,
    auto_repair_notify_controller: bool = False,
    auto_repair_notify_done: bool = False,
    auto_codex_autofix: bool = True,
    auto_codex_autofix_timeout_seconds: int = 600,
    auto_codex_autofix_model: str | None = None,
    auto_codex_autofix_max_risk: str = "low",
    auto_codex_autofix_allow_actions: str | list[str] | None = None,
    auto_codex_autofix_apply_actions: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    return await _chatgptrest_job_wait_impl(
        job_id=job_id,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
        auto_repair_check=auto_repair_check,
        auto_repair_check_mode=auto_repair_check_mode,
        auto_repair_check_timeout_seconds=auto_repair_check_timeout_seconds,
        auto_repair_check_probe_driver=auto_repair_check_probe_driver,
        auto_repair_check_capture_ui=auto_repair_check_capture_ui,
        auto_repair_check_recent_failures=auto_repair_check_recent_failures,
        auto_repair_notify_controller=auto_repair_notify_controller,
        auto_repair_notify_done=auto_repair_notify_done,
        auto_codex_autofix=auto_codex_autofix,
        auto_codex_autofix_timeout_seconds=auto_codex_autofix_timeout_seconds,
        auto_codex_autofix_model=auto_codex_autofix_model,
        auto_codex_autofix_max_risk=auto_codex_autofix_max_risk,
        auto_codex_autofix_allow_actions=auto_codex_autofix_allow_actions,
        auto_codex_autofix_apply_actions=auto_codex_autofix_apply_actions,
        allow_auto_background=True,
        ctx=ctx,
    )


@mcp.tool(
    name="chatgptrest_job_wait_background_start",
    description=(
        "Start a background wait task for an existing job and return immediately.\n"
        "Use this when callers should continue other work instead of blocking on chatgptrest_job_wait."
    ),
    structured_output=True,
)
async def chatgptrest_job_wait_background_start(
    job_id: str,
    timeout_seconds: int = 43200,
    poll_seconds: float = 1.0,
    notify_controller: bool = True,
    notify_done: bool = True,
    auto_repair_check: bool = False,
    auto_repair_check_mode: str = "quick",
    auto_repair_check_timeout_seconds: int = 60,
    auto_repair_check_probe_driver: bool = True,
    auto_repair_check_capture_ui: bool = False,
    auto_repair_check_recent_failures: int = 5,
    auto_repair_notify_controller: bool = False,
    auto_repair_notify_done: bool = False,
    auto_codex_autofix: bool = True,
    auto_codex_autofix_timeout_seconds: int = 600,
    auto_codex_autofix_model: str | None = None,
    auto_codex_autofix_max_risk: str = "low",
    auto_codex_autofix_allow_actions: str | list[str] | None = None,
    auto_codex_autofix_apply_actions: bool = True,
    force_restart: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    return await _background_wait_start(
        job_id=str(job_id),
        timeout_seconds=int(timeout_seconds),
        poll_seconds=max(0.2, float(poll_seconds)),
        notify_controller=bool(notify_controller),
        notify_done=bool(notify_done),
        auto_repair_check=bool(auto_repair_check),
        auto_repair_check_mode=str(auto_repair_check_mode),
        auto_repair_check_timeout_seconds=int(auto_repair_check_timeout_seconds),
        auto_repair_check_probe_driver=bool(auto_repair_check_probe_driver),
        auto_repair_check_capture_ui=bool(auto_repair_check_capture_ui),
        auto_repair_check_recent_failures=int(auto_repair_check_recent_failures),
        auto_repair_notify_controller=bool(auto_repair_notify_controller),
        auto_repair_notify_done=bool(auto_repair_notify_done),
        auto_codex_autofix=bool(auto_codex_autofix),
        auto_codex_autofix_timeout_seconds=int(auto_codex_autofix_timeout_seconds),
        auto_codex_autofix_model=(str(auto_codex_autofix_model).strip() if auto_codex_autofix_model else None),
        auto_codex_autofix_max_risk=str(auto_codex_autofix_max_risk),
        auto_codex_autofix_allow_actions=auto_codex_autofix_allow_actions,
        auto_codex_autofix_apply_actions=bool(auto_codex_autofix_apply_actions),
        force_restart=bool(force_restart),
        ctx=ctx,
    )


@mcp.tool(
    name="chatgptrest_job_wait_background_get",
    description="Get background wait task status by watch_id or job_id.",
    structured_output=True,
)
async def chatgptrest_job_wait_background_get(
    watch_id: str | None = None,
    job_id: str | None = None,
    include_result: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    req_watch_id = (str(watch_id).strip() if watch_id else None)
    req_job_id = (str(job_id).strip() if job_id else None)

    # §11: Use explicit flag instead of pass+fall-through inside async-with.
    _should_auto_resume = False

    async with _BACKGROUND_WAIT_LOCK:
        _background_wait_gc_locked()
        wid = _background_wait_resolve_id_locked(watch_id=watch_id, job_id=job_id)
        if wid:
            state = _BACKGROUND_WAIT_STATE.get(wid)
            if not isinstance(state, dict):
                return {
                    "ok": False,
                    "error_type": "NotFound",
                    "error": "background wait state missing",
                    "watch_id": wid,
                }
            out = _background_wait_state_view(state, include_result=bool(include_result))
            out["ok"] = True
            return out
        # wid is None — watch not found
        if req_job_id and _mcp_wait_background_auto_resume_enabled():
            _should_auto_resume = True
        else:
            return {
                "ok": False,
                "error_type": "NotFound",
                "error": "background wait not found",
                "watch_id": req_watch_id,
                "job_id": req_job_id,
            }

    # Outside lock: auto-resume for missing watcher (MCP restart recovery).
    if _should_auto_resume and req_job_id:
        try:
            snapshot = await chatgptrest_job_get(req_job_id, ctx=ctx)
        except Exception:
            snapshot = None
        status = str((snapshot or {}).get("status") or "").strip().lower() if isinstance(snapshot, dict) else ""
        if status and status not in TERMINAL_STATUSES:
            resumed = await _background_wait_start(
                job_id=req_job_id,
                timeout_seconds=_mcp_wait_background_auto_resume_timeout_seconds(),
                poll_seconds=1.0,
                notify_controller=False,
                notify_done=False,
                auto_repair_check=False,
                auto_repair_check_mode="quick",
                auto_repair_check_timeout_seconds=60,
                auto_repair_check_probe_driver=True,
                auto_repair_check_capture_ui=False,
                auto_repair_check_recent_failures=5,
                auto_repair_notify_controller=False,
                auto_repair_notify_done=False,
                auto_codex_autofix=True,
                auto_codex_autofix_timeout_seconds=600,
                auto_codex_autofix_model=None,
                auto_codex_autofix_max_risk="low",
                auto_codex_autofix_allow_actions=None,
                auto_codex_autofix_apply_actions=True,
                force_restart=False,
                ctx=ctx,
            )
            if isinstance(resumed, dict) and bool(resumed.get("ok")):
                out = dict(resumed)
                out["auto_resumed"] = True
                out["auto_resumed_from_not_found"] = True
                out["job_snapshot_status"] = status
                return out

    return {
        "ok": False,
        "error_type": "NotFound",
        "error": "background wait not found",
        "watch_id": req_watch_id,
        "job_id": req_job_id,
    }


@mcp.tool(
    name="chatgptrest_job_wait_background_list",
    description="List in-memory background wait tasks (running and optionally recently finished).",
    structured_output=True,
)
async def chatgptrest_job_wait_background_list(
    include_done: bool = False,
    include_result: bool = False,
    limit: int = 200,
    ctx: Context | None = None,
) -> dict[str, Any]:
    max_items = max(1, min(1000, int(limit)))
    async with _BACKGROUND_WAIT_LOCK:
        _background_wait_gc_locked()
        rows: list[dict[str, Any]] = []
        for state in _BACKGROUND_WAIT_STATE.values():
            if not isinstance(state, dict):
                continue
            watch_status = str(state.get("watch_status") or "").strip().lower()
            if (not include_done) and watch_status != "running":
                continue
            rows.append(_background_wait_state_view(state, include_result=bool(include_result)))
        rows.sort(key=lambda x: float(x.get("started_at") or 0.0), reverse=True)
        return {"ok": True, "count": len(rows[:max_items]), "watches": rows[:max_items]}


@mcp.tool(
    name="chatgptrest_job_wait_background_cancel",
    description="Cancel a running background wait task by watch_id or job_id.",
    structured_output=True,
)
async def chatgptrest_job_wait_background_cancel(
    watch_id: str | None = None,
    job_id: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    task: asyncio.Task[None] | None = None
    async with _BACKGROUND_WAIT_LOCK:
        _background_wait_gc_locked()
        wid = _background_wait_resolve_id_locked(watch_id=watch_id, job_id=job_id)
        if not wid:
            return {
                "ok": False,
                "error_type": "NotFound",
                "error": "background wait not found",
                "watch_id": (str(watch_id).strip() if watch_id else None),
                "job_id": (str(job_id).strip() if job_id else None),
            }
        task = _BACKGROUND_WAIT_TASKS.get(wid)
        if task is not None and not task.done():
            task.cancel()
        state = _BACKGROUND_WAIT_STATE.get(wid)
    if task is not None and not task.done():
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    async with _BACKGROUND_WAIT_LOCK:
        state = _BACKGROUND_WAIT_STATE.get(wid)
        if not isinstance(state, dict):
            return {"ok": False, "error_type": "NotFound", "error": "background wait state missing", "watch_id": wid}
        if str(state.get("watch_status") or "").strip().lower() == "running":
            now = time.time()
            state["watch_status"] = "canceled"
            state["terminal"] = False
            state["updated_at"] = now
            state["ended_at"] = now
        out = _background_wait_state_view(state, include_result=True)
        out["ok"] = True
        return out


@mcp.tool(
    name="chatgptrest_job_cancel",
    description="Request cancellation for a job (POST /v1/jobs/{job_id}/cancel).",
    structured_output=True,
)
async def chatgptrest_job_cancel(job_id: str, ctx: Context | None = None) -> dict[str, Any]:
    base = _base_url()
    headers = _auth_headers()
    headers["X-Cancel-Reason"] = _default_cancel_reason(job_id=str(job_id))
    return await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v1/jobs/{urllib.parse.quote(str(job_id))}/cancel",
        body=None,
        headers=headers,
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_job_events",
    description="Fetch DB-backed job events (GET /v1/jobs/{job_id}/events).",
    structured_output=True,
)
async def chatgptrest_job_events(
    job_id: str,
    after_id: int = 0,
    limit: int = 200,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    qs = urllib.parse.urlencode({"after_id": int(after_id), "limit": int(limit)}, doseq=False)
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/jobs/{urllib.parse.quote(str(job_id))}/events?{qs}",
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_answer_get",
    description="[DEPRECATED: use chatgptrest_result] Fetch answer chunk. Prefer chatgptrest_result(job_id, include_answer=true) instead.",
    structured_output=True,
)
async def chatgptrest_answer_get(
    job_id: str,
    offset: int = 0,
    max_chars: int = 8000,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    qs = urllib.parse.urlencode({"offset": int(offset), "max_chars": int(max_chars)}, doseq=False)
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/jobs/{urllib.parse.quote(str(job_id))}/answer?{qs}",
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_conversation_get",
    description="Fetch conversation export chunk (GET /v1/jobs/{job_id}/conversation). Byte-offset based.",
    structured_output=True,
)
async def chatgptrest_conversation_get(
    job_id: str,
    offset: int = 0,
    max_chars: int = 8000,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    qs = urllib.parse.urlencode({"offset": int(offset), "max_chars": int(max_chars)}, doseq=False)
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/jobs/{urllib.parse.quote(str(job_id))}/conversation?{qs}",
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_advisor_advise",
    description=(
        "Run advisor wrapper v1 via REST first-class endpoint (POST /v1/advisor/advise). "
        "Supports plan-only mode (`execute=false`) and execution mode (`execute=true`)."
    ),
    structured_output=True,
)
async def chatgptrest_advisor_advise(
    *,
    raw_question: str,
    context: dict[str, Any] | None = None,
    force: bool = False,
    execute: bool = False,
    mode: str = "balanced",
    orchestrate: bool = False,
    quality_threshold: int | None = None,
    crosscheck: bool = False,
    max_retries: int = 0,
    agent_options: dict[str, Any] | None = None,
    timeout_seconds: int = 180,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    body: dict[str, Any] = {
        "raw_question": str(raw_question),
        "context": dict(context or {}),
        "force": bool(force),
        "execute": bool(execute),
        "mode": str(mode or "balanced"),
        "orchestrate": bool(orchestrate),
        "crosscheck": bool(crosscheck),
        "max_retries": int(max_retries),
    }
    if quality_threshold is not None:
        body["quality_threshold"] = int(quality_threshold)
    if agent_options:
        body["agent_options"] = dict(agent_options)
    return await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v1/advisor/advise",
        body=body,
        headers=_auth_headers(),
        timeout_seconds=max(1.0, float(timeout_seconds)),
    )


@mcp.tool(
    name="chatgptrest_advisor_ask",
    description=(
        "Intelligent ask — automatically routes your question to the best model/preset.\n"
        "Uses KB probe + intent analysis to decide: quick_ask, deep_research, report, or funnel.\n"
        "Returns job_id; use chatgptrest_result(job_id) to get the answer.\n"
        "If KB can answer directly, returns answer immediately (no job created).\n"
        "Prefer this over chatgptrest_ask when you don't know which provider/preset to use."
    ),
    structured_output=True,
)
async def chatgptrest_advisor_ask(
    *,
    idempotency_key: str,
    question: str,
    intent_hint: str = "",
    context: dict[str, Any] | None = None,
    file_paths: list[str] | str | None = None,
    auto_context: bool = True,
    auto_context_top_k: int = 3,
    timeout_seconds: int = 300,
    auto_wait: bool = True,
    notify_done: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    body: dict[str, Any] = {
        "question": str(question),
        "idempotency_key": str(idempotency_key),
        "timeout_seconds": int(timeout_seconds),
    }
    if intent_hint and str(intent_hint).strip():
        body["intent_hint"] = str(intent_hint).strip()
    if context:
        body["context"] = dict(context)
    if file_paths:
        if isinstance(file_paths, str):
            body["file_paths"] = [file_paths]
        else:
            body["file_paths"] = list(file_paths)
    body["auto_context"] = bool(auto_context)
    body["auto_context_top_k"] = int(auto_context_top_k)

    result = await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v2/advisor/ask",
        body=body,
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )

    # If KB answered directly, return immediately
    status = str(result.get("status", "")).lower()
    if status == "completed":
        return result

    # Start background wait for the created job
    job_id = str(result.get("job_id", "")).strip()
    if auto_wait and job_id:
        try:
            await _background_wait_start(
                job_id=job_id,
                timeout_seconds=max(60, int(timeout_seconds) + 120),
                poll_seconds=1.0,
                notify_controller=True,
                notify_done=bool(notify_done),
                auto_repair_check=False,
                auto_repair_check_mode="quick",
                auto_repair_check_timeout_seconds=60,
                auto_repair_check_probe_driver=True,
                auto_repair_check_capture_ui=False,
                auto_repair_check_recent_failures=5,
                auto_repair_notify_controller=False,
                auto_repair_notify_done=False,
                auto_codex_autofix=True,
                auto_codex_autofix_timeout_seconds=600,
                auto_codex_autofix_model=None,
                auto_codex_autofix_max_risk="low",
                auto_codex_autofix_allow_actions=None,
                auto_codex_autofix_apply_actions=True,
                force_restart=False,
                ctx=ctx,
            )
        except Exception as e:
            result["auto_wait_error"] = str(e)

    # Notify controller
    route = result.get("route", "?")
    provider = result.get("provider", "?")
    preset = result.get("preset", "?")
    _tmux_notify(
        f"[advisor_ask] {job_id[:12] if job_id else '?'} "
        f"route={route} {provider}/{preset} "
        f"kb={'✓' if result.get('kb_used') else '✗'}"
    )

    return result


@mcp.tool(
    name="chatgptrest_chatgpt_ask_submit",
    description="[DEPRECATED: use chatgptrest_ask] Submit a chatgpt_web.ask job. Prefer chatgptrest_ask(provider='chatgpt') instead.",
    structured_output=True,
)
async def chatgptrest_chatgpt_ask_submit(
    *,
    idempotency_key: str,
    question: str,
    preset: str,
    timeout_seconds: int = 600,
    send_timeout_seconds: int | None = None,
    wait_timeout_seconds: int | None = None,
    max_wait_seconds: int = 1800,
    min_chars: int = 800,
    answer_format: str = "markdown",
    conversation_url: str | None = None,
    parent_job_id: str | None = None,
    deep_research: bool = False,
    web_search: bool = False,
    agent_mode: bool = False,
    github_repo: str | None = None,
    file_paths: list[str] | str | None = None,
    format_prompt: str | None = None,
    format_preset: str = "thinking_heavy",
    notify_controller: bool = True,
    notify_done: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    input_obj: dict[str, Any] = {"question": str(question)}
    if conversation_url:
        if _looks_like_gemini_conversation_url(conversation_url):
            raise ValueError(
                f"conversation_url looks like Gemini ({conversation_url}); "
                "use chatgptrest_gemini_ask_submit (kind=gemini_web.ask) instead."
            )
        if _looks_like_qwen_conversation_url(conversation_url):
            raise ValueError(
                f"conversation_url looks like Qwen ({conversation_url}); "
                "use chatgptrest_qwen_ask_submit (kind=qwen_web.ask) instead."
            )
        input_obj["conversation_url"] = str(conversation_url)
    if parent_job_id:
        input_obj["parent_job_id"] = str(parent_job_id)
    if github_repo:
        input_obj["github_repo"] = str(github_repo)
    if file_paths:
        if isinstance(file_paths, str):
            input_obj["file_paths"] = [file_paths]
        else:
            input_obj["file_paths"] = list(file_paths)

    params_obj: dict[str, Any] = {
        "preset": str(preset),
        "timeout_seconds": int(timeout_seconds),
        "max_wait_seconds": int(max_wait_seconds),
        "min_chars": int(min_chars),
        "answer_format": str(answer_format),
        "deep_research": bool(deep_research),
        "web_search": bool(web_search),
        "agent_mode": bool(agent_mode),
    }
    if send_timeout_seconds is not None:
        params_obj["send_timeout_seconds"] = int(send_timeout_seconds)
    if wait_timeout_seconds is not None:
        params_obj["wait_timeout_seconds"] = int(wait_timeout_seconds)
    if format_prompt and str(format_prompt).strip():
        params_obj["format_prompt"] = str(format_prompt).strip()
        params_obj["format_preset"] = str(format_preset).strip() or "thinking_heavy"

    job = await chatgptrest_job_create(
        idempotency_key=idempotency_key,
        kind="chatgpt_web.ask",
        input=input_obj,
        params=params_obj,
        client={"name": "chatgptrest_chatgpt_ask_submit"},
        ctx=ctx,
    )

    if notify_controller:
        est = job.get("estimated_wait_seconds")
        msg = f"[chatgptrest] submitted {job.get('job_id')} est_wait={est}s preset={preset}"
        _tmux_notify(msg)

    await _maybe_notify_done(job, notify_done=notify_done)

    return job


@mcp.tool(
    name="chatgptrest_gemini_ask_submit",
    description="[DEPRECATED: use chatgptrest_ask] Submit a gemini_web.ask job. Prefer chatgptrest_ask(provider='gemini') instead.",
    structured_output=True,
)
async def chatgptrest_gemini_ask_submit(
    *,
    idempotency_key: str,
    question: str,
    preset: str,
    timeout_seconds: int = 600,
    send_timeout_seconds: int | None = None,
    wait_timeout_seconds: int | None = None,
    max_wait_seconds: int = 1800,
    min_chars: int = 200,
    answer_format: str = "markdown",
    deep_research: bool = False,
    file_paths: list[str] | str | None = None,
    github_repo: str | None = None,
    enable_import_code: bool = False,
    drive_name_fallback: bool = False,
    conversation_url: str | None = None,
    parent_job_id: str | None = None,
    notify_controller: bool = True,
    notify_done: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    input_obj: dict[str, Any] = {"question": str(question)}
    if conversation_url:
        if _looks_like_chatgpt_conversation_url(conversation_url):
            raise ValueError(
                f"conversation_url looks like ChatGPT ({conversation_url}); "
                "use chatgptrest_chatgpt_ask_submit (kind=chatgpt_web.ask) instead."
            )
        if _looks_like_qwen_conversation_url(conversation_url):
            raise ValueError(
                f"conversation_url looks like Qwen ({conversation_url}); "
                "use chatgptrest_qwen_ask_submit (kind=qwen_web.ask) instead."
            )
        input_obj["conversation_url"] = str(conversation_url)
    if parent_job_id:
        input_obj["parent_job_id"] = str(parent_job_id)
    if file_paths:
        if isinstance(file_paths, str):
            input_obj["file_paths"] = [file_paths]
        else:
            input_obj["file_paths"] = list(file_paths)

    if github_repo:
        if not enable_import_code:
            raise ValueError("github_repo requires enable_import_code=true for gemini_web.ask")
        input_obj["github_repo"] = str(github_repo)

    params_obj: dict[str, Any] = {
        "preset": str(preset),
        "timeout_seconds": int(timeout_seconds),
        "max_wait_seconds": int(max_wait_seconds),
        "min_chars": int(min_chars),
        "answer_format": str(answer_format),
        "deep_research": bool(deep_research),
    }
    if send_timeout_seconds is not None:
        params_obj["send_timeout_seconds"] = int(send_timeout_seconds)
    if wait_timeout_seconds is not None:
        params_obj["wait_timeout_seconds"] = int(wait_timeout_seconds)
    if enable_import_code:
        params_obj["enable_import_code"] = True
    if drive_name_fallback:
        params_obj["drive_name_fallback"] = True

    job = await chatgptrest_job_create(
        idempotency_key=idempotency_key,
        kind="gemini_web.ask",
        input=input_obj,
        params=params_obj,
        client={"name": "chatgptrest_gemini_ask_submit"},
        ctx=ctx,
    )

    if notify_controller:
        est = job.get("estimated_wait_seconds")
        msg = f"[chatgptrest] submitted {job.get('job_id')} est_wait={est}s gemini preset={preset}"
        _tmux_notify(msg)

    await _maybe_notify_done(job, notify_done=notify_done)

    return job


@mcp.tool(
    name="chatgptrest_qwen_ask_submit",
    description="[DEPRECATED: use chatgptrest_ask] Submit a qwen_web.ask job. Prefer chatgptrest_ask(provider='qwen') instead.",
    structured_output=True,
)
async def chatgptrest_qwen_ask_submit(
    *,
    idempotency_key: str,
    question: str,
    preset: str = "deep_thinking",
    timeout_seconds: int = 600,
    send_timeout_seconds: int | None = None,
    wait_timeout_seconds: int | None = None,
    max_wait_seconds: int = 1800,
    min_chars: int = 200,
    answer_format: str = "markdown",
    conversation_url: str | None = None,
    parent_job_id: str | None = None,
    deep_research: bool = False,
    notify_controller: bool = True,
    notify_done: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    input_obj: dict[str, Any] = {"question": str(question)}
    if conversation_url:
        if _looks_like_chatgpt_conversation_url(conversation_url):
            raise ValueError(
                f"conversation_url looks like ChatGPT ({conversation_url}); "
                "use chatgptrest_chatgpt_ask_submit (kind=chatgpt_web.ask) instead."
            )
        if _looks_like_gemini_conversation_url(conversation_url):
            raise ValueError(
                f"conversation_url looks like Gemini ({conversation_url}); "
                "use chatgptrest_gemini_ask_submit (kind=gemini_web.ask) instead."
            )
        input_obj["conversation_url"] = str(conversation_url)
    if parent_job_id:
        input_obj["parent_job_id"] = str(parent_job_id)

    params_obj: dict[str, Any] = {
        "preset": str(preset),
        "timeout_seconds": int(timeout_seconds),
        "max_wait_seconds": int(max_wait_seconds),
        "min_chars": int(min_chars),
        "answer_format": str(answer_format),
        "deep_research": bool(deep_research),
    }
    if send_timeout_seconds is not None:
        params_obj["send_timeout_seconds"] = int(send_timeout_seconds)
    if wait_timeout_seconds is not None:
        params_obj["wait_timeout_seconds"] = int(wait_timeout_seconds)

    job = await chatgptrest_job_create(
        idempotency_key=idempotency_key,
        kind="qwen_web.ask",
        input=input_obj,
        params=params_obj,
        client={"name": "chatgptrest_qwen_ask_submit"},
        ctx=ctx,
    )

    if notify_controller:
        est = job.get("estimated_wait_seconds")
        msg = f"[chatgptrest] submitted {job.get('job_id')} est_wait={est}s qwen preset={preset}"
        _tmux_notify(msg)

    await _maybe_notify_done(job, notify_done=notify_done)

    return job


@mcp.tool(
    name="chatgptrest_gemini_generate_image_submit",
    description="Convenience: submit a gemini_web.generate_image job (Gemini Web image generation) and optionally notify a controller tmux pane.",
    structured_output=True,
)
async def chatgptrest_gemini_generate_image_submit(
    *,
    idempotency_key: str,
    prompt: str,
    timeout_seconds: int = 600,
    conversation_url: str | None = None,
    file_paths: list[str] | None = None,
    notify_controller: bool = True,
    notify_done: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    input_obj: dict[str, Any] = {"prompt": str(prompt)}
    if conversation_url:
        if _looks_like_chatgpt_conversation_url(conversation_url):
            raise ValueError(
                f"conversation_url looks like ChatGPT ({conversation_url}); "
                "use chatgptrest_chatgpt_ask_submit (kind=chatgpt_web.ask) instead."
            )
        if _looks_like_qwen_conversation_url(conversation_url):
            raise ValueError(
                f"conversation_url looks like Qwen ({conversation_url}); "
                "use chatgptrest_qwen_ask_submit (kind=qwen_web.ask) instead."
            )
        input_obj["conversation_url"] = str(conversation_url)
    if isinstance(file_paths, list) and file_paths:
        input_obj["file_paths"] = [str(p) for p in file_paths]

    params_obj: dict[str, Any] = {"timeout_seconds": int(timeout_seconds)}
    job = await chatgptrest_job_create(
        idempotency_key=idempotency_key,
        kind="gemini_web.generate_image",
        input=input_obj,
        params=params_obj,
        client={"name": "chatgptrest_gemini_generate_image_submit"},
        ctx=ctx,
    )

    if notify_controller:
        msg = f"[chatgptrest] submitted {job.get('job_id')} gemini generate_image"
        _tmux_notify(msg)

    await _maybe_notify_done(job, notify_done=notify_done)

    return job


@mcp.tool(
    name="chatgptrest_gemini_extract_answer",
    description=(
        "Extract the last model response from an existing Gemini conversation URL. "
        "Read-only — no question is sent. Submit a gemini_web.extract_answer job. "
        "Use chatgptrest_result(job_id) to get the extracted answer."
    ),
    structured_output=True,
)
async def chatgptrest_gemini_extract_answer(
    *,
    conversation_url: str,
    timeout_seconds: int = 60,
    notify_done: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    if not str(conversation_url or "").strip():
        raise ValueError("conversation_url is required")

    import uuid
    idempotency_key = f"extract-{uuid.uuid4().hex[:16]}"

    input_obj: dict[str, Any] = {"conversation_url": str(conversation_url).strip()}
    params_obj: dict[str, Any] = {"timeout_seconds": int(timeout_seconds)}

    job = await chatgptrest_job_create(
        idempotency_key=idempotency_key,
        kind="gemini_web.extract_answer",
        input=input_obj,
        params=params_obj,
        client={"name": "chatgptrest_gemini_extract_answer"},
        ctx=ctx,
    )

    try:
        await _background_wait_start(
            job_id=str(job.get("job_id", "")),
            timeout_seconds=max(60, int(timeout_seconds) + 60),
            poll_seconds=1.0,
            notify_controller=True,
            notify_done=bool(notify_done),
            auto_repair_check=False,
            auto_repair_check_mode="quick",
            auto_repair_check_timeout_seconds=60,
            auto_repair_check_probe_driver=True,
            auto_repair_check_capture_ui=False,
            auto_repair_check_recent_failures=5,
            auto_repair_notify_controller=False,
            auto_repair_notify_done=False,
            auto_codex_autofix=False,
            auto_codex_autofix_timeout_seconds=600,
            auto_codex_autofix_model=None,
            auto_codex_autofix_max_risk="low",
            auto_codex_autofix_allow_actions=None,
            auto_codex_autofix_apply_actions=True,
            force_restart=False,
            ctx=ctx,
        )
    except Exception as e:
        job["auto_wait_error"] = str(e)

    _tmux_notify(f"[chatgptrest] extract_answer {job.get('job_id')} url={conversation_url}")
    return job


@mcp.tool(
    name="chatgptrest_chatgpt_extract_answer",
    description=(
        "Extract the last model response from an existing ChatGPT conversation URL. "
        "Read-only — no question is sent. Internally uses conversation export. "
        "Use chatgptrest_result(job_id) to get the extracted answer."
    ),
    structured_output=True,
)
async def chatgptrest_chatgpt_extract_answer(
    *,
    conversation_url: str,
    timeout_seconds: int = 60,
    notify_done: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    if not str(conversation_url or "").strip():
        raise ValueError("conversation_url is required")

    import uuid
    idempotency_key = f"chatgpt-extract-{uuid.uuid4().hex[:16]}"

    input_obj: dict[str, Any] = {"conversation_url": str(conversation_url).strip()}
    params_obj: dict[str, Any] = {"timeout_seconds": int(timeout_seconds)}

    job = await chatgptrest_job_create(
        idempotency_key=idempotency_key,
        kind="chatgpt_web.extract_answer",
        input=input_obj,
        params=params_obj,
        client={"name": "chatgptrest_chatgpt_extract_answer"},
        ctx=ctx,
    )

    try:
        await _background_wait_start(
            job_id=str(job.get("job_id", "")),
            timeout_seconds=max(60, int(timeout_seconds) + 60),
            poll_seconds=1.0,
            notify_controller=True,
            notify_done=bool(notify_done),
            auto_repair_check=False,
            auto_repair_check_mode="quick",
            auto_repair_check_timeout_seconds=60,
            auto_repair_check_probe_driver=True,
            auto_repair_check_capture_ui=False,
            auto_repair_check_recent_failures=5,
            auto_repair_notify_controller=False,
            auto_repair_notify_done=False,
            auto_codex_autofix=False,
            auto_codex_autofix_timeout_seconds=600,
            auto_codex_autofix_model=None,
            auto_codex_autofix_max_risk="low",
            auto_codex_autofix_allow_actions=None,
            auto_codex_autofix_apply_actions=True,
            force_restart=False,
            ctx=ctx,
        )
    except Exception as e:
        job["auto_wait_error"] = str(e)

    _tmux_notify(f"[chatgptrest] chatgpt_extract_answer {job.get('job_id')} url={conversation_url}")
    return job

@mcp.tool(
    name="chatgptrest_repair_check_submit",
    description="Convenience: submit a repair.check diagnostics job (no prompt send).",
    structured_output=True,
)
async def chatgptrest_repair_check_submit(
    *,
    idempotency_key: str,
    job_id: str | None = None,
    symptom: str | None = None,
    conversation_url: str | None = None,
    mode: str = "quick",
    timeout_seconds: int = 60,
    probe_driver: bool = True,
    capture_ui: bool = False,
    recent_failures: int = 5,
    notify_controller: bool = True,
    notify_done: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    job = await chatgptrest_job_create(
        idempotency_key=idempotency_key,
        kind="repair.check",
        input=_build_repair_input(
            job_id=(str(job_id) if job_id else None),
            symptom=symptom,
            conversation_url=conversation_url,
        ),
        params=_build_repair_check_params(
            mode=str(mode),
            timeout_seconds=int(timeout_seconds),
            probe_driver=bool(probe_driver),
            capture_ui=bool(capture_ui),
            recent_failures=int(recent_failures),
        ),
        client={"name": "chatgptrest_repair_check_submit"},
        ctx=ctx,
    )

    if notify_controller:
        msg = f"[chatgptrest] submitted repair.check {job.get('job_id')} mode={mode}"
        _tmux_notify(msg)

    await _maybe_notify_done(job, notify_done=notify_done)

    return job


@mcp.tool(
    name="chatgptrest_repair_autofix_submit",
    description="Convenience: submit a repair.autofix job (Codex-driven, may execute guarded actions; no prompt send).",
    structured_output=True,
)
async def chatgptrest_repair_autofix_submit(
    *,
    idempotency_key: str,
    job_id: str,
    symptom: str | None = None,
    conversation_url: str | None = None,
    timeout_seconds: int = 600,
    model: str | None = None,
    max_risk: str = "low",
    allow_actions: str | list[str] | None = None,
    apply_actions: bool = True,
    notify_controller: bool = True,
    notify_done: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    job = await chatgptrest_job_create(
        idempotency_key=idempotency_key,
        kind="repair.autofix",
        input=_build_repair_input(
            job_id=str(job_id),
            symptom=symptom,
            conversation_url=conversation_url,
        ),
        params=_build_repair_autofix_params(
            timeout_seconds=int(timeout_seconds),
            model=(str(model).strip() if model else None),
            max_risk=str(max_risk),
            allow_actions=allow_actions,
            apply_actions=bool(apply_actions),
        ),
        client={"name": "chatgptrest_repair_autofix_submit"},
        ctx=ctx,
    )

    if notify_controller:
        msg = f"[chatgptrest] submitted repair.autofix {job.get('job_id')} max_risk={max_risk}"
        _tmux_notify(msg)

    await _maybe_notify_done(job, notify_done=notify_done)

    return job


@mcp.tool(
    name="chatgptrest_sre_fix_request_submit",
    description=(
        "Submit an incident-scoped SRE fix-request job. The coordinator keeps lane-scoped memory, "
        "optionally resumes the same lane, and can route to repair.autofix or repair.open_pr."
    ),
    structured_output=True,
)
async def chatgptrest_sre_fix_request_submit(
    *,
    idempotency_key: str,
    issue_id: str | None = None,
    incident_id: str | None = None,
    job_id: str | None = None,
    symptom: str | None = None,
    instructions: str | None = None,
    lane_id: str | None = None,
    context: dict[str, Any] | str | None = None,
    context_pack: dict[str, Any] | list[Any] | str | None = None,
    timeout_seconds: int = 600,
    model: str | None = None,
    resume_lane: bool = True,
    route_mode: str = "auto_best_effort",
    runtime_apply_actions: bool = True,
    runtime_max_risk: str = "low",
    runtime_allow_actions: str | list[str] | None = None,
    open_pr_mode: str = "p0",
    open_pr_run_tests: bool | None = None,
    gitnexus_limit: int = 5,
    notify_controller: bool = True,
    notify_done: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    job = await chatgptrest_job_create(
        idempotency_key=idempotency_key,
        kind="sre.fix_request",
        input=_build_sre_fix_request_input(
            issue_id=issue_id,
            incident_id=incident_id,
            job_id=job_id,
            symptom=symptom,
            instructions=instructions,
            lane_id=lane_id,
            context=context,
            context_pack=context_pack,
        ),
        params=_build_sre_fix_request_params(
            timeout_seconds=int(timeout_seconds),
            model=(str(model).strip() if model else None),
            resume_lane=bool(resume_lane),
            route_mode=str(route_mode),
            runtime_apply_actions=bool(runtime_apply_actions),
            runtime_max_risk=str(runtime_max_risk),
            runtime_allow_actions=runtime_allow_actions,
            open_pr_mode=str(open_pr_mode),
            open_pr_run_tests=open_pr_run_tests,
            gitnexus_limit=int(gitnexus_limit),
        ),
        client={"name": "chatgptrest_sre_fix_request_submit"},
        ctx=ctx,
    )

    if notify_controller:
        msg = f"[chatgptrest] submitted sre.fix_request {job.get('job_id')} route_mode={route_mode}"
        _tmux_notify(msg)

    await _maybe_notify_done(job, notify_done=notify_done)

    return job


@mcp.tool(
    name="chatgptrest_repair_open_pr_submit",
    description=(
        "Convenience: submit a repair.open_pr job (Codex-driven patch proposal; optional apply/commit/push/PR).\n"
        "Modes:\n"
        "- p0: propose patch only (no git changes)\n"
        "- p1: apply patch in a worktree + run tests + commit (no push/PR)\n"
        "- p2: apply + tests + commit + push + open PR (requires git/gh auth)\n"
    ),
    structured_output=True,
)
async def chatgptrest_repair_open_pr_submit(
    *,
    idempotency_key: str,
    job_id: str,
    symptom: str | None = None,
    instructions: str | None = None,
    mode: str = "p0",
    timeout_seconds: int = 900,
    model: str | None = None,
    remote: str = "origin",
    base_ref: str = "HEAD",
    base_branch: str = "master",
    run_tests: bool | None = None,
    push: bool | None = None,
    create_pr: bool | None = None,
    notify_controller: bool = True,
    notify_done: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    input_obj: dict[str, Any] = {"job_id": str(job_id)}
    if symptom and str(symptom).strip():
        input_obj["symptom"] = str(symptom).strip()
    if instructions and str(instructions).strip():
        input_obj["instructions"] = str(instructions).strip()

    params_obj: dict[str, Any] = {
        "mode": str(mode),
        "timeout_seconds": int(timeout_seconds),
        "remote": str(remote),
        "base_ref": str(base_ref),
        "base_branch": str(base_branch),
    }
    if model and str(model).strip():
        params_obj["model"] = str(model).strip()
    if run_tests is not None:
        params_obj["run_tests"] = bool(run_tests)
    if push is not None:
        params_obj["push"] = bool(push)
    if create_pr is not None:
        params_obj["create_pr"] = bool(create_pr)

    job = await chatgptrest_job_create(
        idempotency_key=idempotency_key,
        kind="repair.open_pr",
        input=input_obj,
        params=params_obj,
        client={"name": "chatgptrest_repair_open_pr_submit"},
        ctx=ctx,
    )

    if notify_controller:
        msg = f"[chatgptrest] submitted repair.open_pr {job.get('job_id')} mode={mode}"
        _tmux_notify(msg)

    await _maybe_notify_done(job, notify_done=notify_done)

    return job


@mcp.tool(
    name="chatgptrest_ops_pause_get",
    description="Get system pause/drain state (GET /v1/ops/pause).",
    structured_output=True,
)
async def chatgptrest_ops_pause_get(ctx: Context | None = None) -> dict[str, Any]:
    base = _base_url()
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/ops/pause",
        headers=_ops_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_ops_pause_set",
    description="Set/clear system pause/drain state (POST /v1/ops/pause).",
    structured_output=True,
)
async def chatgptrest_ops_pause_set(
    *,
    mode: str,
    until_ts: float | None = None,
    duration_seconds: int | None = None,
    reason: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    body: dict[str, Any] = {"mode": str(mode)}
    if until_ts is not None:
        body["until_ts"] = float(until_ts)
    if duration_seconds is not None:
        body["duration_seconds"] = int(duration_seconds)
    if reason is not None:
        body["reason"] = str(reason)
    return await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v1/ops/pause",
        body=body,
        headers=_ops_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_ops_status",
    description="Get compact ops status (GET /v1/ops/status).",
    structured_output=True,
)
async def chatgptrest_ops_status(ctx: Context | None = None) -> dict[str, Any]:
    base = _base_url()
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/ops/status",
        headers=_ops_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_ops_incidents_list",
    description="List incidents (GET /v1/ops/incidents).",
    structured_output=True,
)
async def chatgptrest_ops_incidents_list(
    status: str | None = None,
    severity: str | None = None,
    before_ts: float | None = None,
    before_incident_id: str | None = None,
    limit: int = 200,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    qs = _qs(
        {
            "status": status,
            "severity": severity,
            "before_ts": before_ts,
            "before_incident_id": before_incident_id,
            "limit": int(limit),
        },
    )
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/ops/incidents?{qs}",
        headers=_ops_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_ops_incident_get",
    description="Get incident by id (GET /v1/ops/incidents/{incident_id}).",
    structured_output=True,
)
async def chatgptrest_ops_incident_get(incident_id: str, ctx: Context | None = None) -> dict[str, Any]:
    base = _base_url()
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/ops/incidents/{urllib.parse.quote(str(incident_id))}",
        headers=_ops_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_ops_incident_actions_list",
    description="List remediation actions for an incident (GET /v1/ops/incidents/{incident_id}/actions).",
    structured_output=True,
)
async def chatgptrest_ops_incident_actions_list(
    incident_id: str,
    limit: int = 200,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    qs = urllib.parse.urlencode({"limit": int(limit)}, doseq=False)
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/ops/incidents/{urllib.parse.quote(str(incident_id))}/actions?{qs}",
        headers=_ops_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_ops_events",
    description="Fetch global job events (GET /v1/ops/events).",
    structured_output=True,
)
async def chatgptrest_ops_events(
    after_id: int = 0,
    limit: int = 200,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    qs = urllib.parse.urlencode({"after_id": int(after_id), "limit": int(limit)}, doseq=False)
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/ops/events?{qs}",
        headers=_ops_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_ops_idempotency_get",
    description="Lookup Idempotency-Key record (GET /v1/ops/idempotency/{idempotency_key}).",
    structured_output=True,
)
async def chatgptrest_ops_idempotency_get(idempotency_key: str, ctx: Context | None = None) -> dict[str, Any]:
    base = _base_url()
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/ops/idempotency/{urllib.parse.quote(str(idempotency_key))}",
        headers=_ops_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_ops_jobs_list",
    description="List recent jobs (GET /v1/ops/jobs).",
    structured_output=True,
)
async def chatgptrest_ops_jobs_list(
    status: str | None = None,
    kind_prefix: str | None = None,
    phase: str | None = None,
    before_ts: float | None = None,
    before_job_id: str | None = None,
    limit: int = 200,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    qs = _qs(
        {
            "status": status,
            "kind_prefix": kind_prefix,
            "phase": phase,
            "before_ts": before_ts,
            "before_job_id": before_job_id,
            "limit": int(limit),
        },
    )
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/ops/jobs?{qs}",
        headers=_ops_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_issue_report",
    description="Report/merge a client issue into Issue Ledger (POST /v1/issues/report).",
    structured_output=True,
)
async def chatgptrest_issue_report(
    *,
    project: str,
    title: str,
    severity: str | None = None,
    kind: str | None = None,
    symptom: str | None = None,
    raw_error: str | None = None,
    job_id: str | None = None,
    conversation_url: str | None = None,
    artifacts_path: str | None = None,
    source: str | None = None,
    fingerprint: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    allow_resolved_job: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    metadata_obj = (dict(metadata) if isinstance(metadata, dict) else {})
    if bool(allow_resolved_job):
        metadata_obj["allow_resolved_job"] = True
    body: dict[str, Any] = {
        "project": str(project),
        "title": str(title),
        "severity": severity,
        "kind": kind,
        "symptom": symptom,
        "raw_error": raw_error,
        "job_id": job_id,
        "conversation_url": conversation_url,
        "artifacts_path": artifacts_path,
        "source": source,
        "fingerprint": fingerprint,
        "tags": list(tags or []),
        "metadata": (metadata_obj if metadata_obj else None),
    }
    return await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v1/issues/report",
        body=body,
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_issue_list",
    description="List client issues from Issue Ledger (GET /v1/issues).",
    structured_output=True,
)
async def chatgptrest_issue_list(
    project: str | None = None,
    kind: str | None = None,
    source: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    fingerprint_hash: str | None = None,
    fingerprint_text: str | None = None,
    since_ts: float | None = None,
    until_ts: float | None = None,
    before_ts: float | None = None,
    before_issue_id: str | None = None,
    limit: int = 200,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    qs = _qs(
        {
            "project": project,
            "kind": kind,
            "source": source,
            "status": status,
            "severity": severity,
            "fingerprint_hash": fingerprint_hash,
            "fingerprint_text": fingerprint_text,
            "since_ts": since_ts,
            "until_ts": until_ts,
            "before_ts": before_ts,
            "before_issue_id": before_issue_id,
            "limit": int(limit),
        },
    )
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/issues?{qs}",
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_issue_get",
    description="Get a client issue by id (GET /v1/issues/{issue_id}).",
    structured_output=True,
)
async def chatgptrest_issue_get(issue_id: str, ctx: Context | None = None) -> dict[str, Any]:
    base = _base_url()
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/issues/{urllib.parse.quote(str(issue_id))}",
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_issue_update_status",
    description="Update client issue status (POST /v1/issues/{issue_id}/status).",
    structured_output=True,
)
async def chatgptrest_issue_update_status(
    *,
    issue_id: str,
    status: str,
    note: str | None = None,
    actor: str | None = None,
    linked_job_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    body: dict[str, Any] = {"status": str(status)}
    if note is not None:
        body["note"] = str(note)
    if actor is not None:
        body["actor"] = str(actor)
    if linked_job_id is not None:
        body["linked_job_id"] = str(linked_job_id)
    if isinstance(metadata, dict):
        body["metadata"] = dict(metadata)
    return await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v1/issues/{urllib.parse.quote(str(issue_id))}/status",
        body=body,
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_issue_link_evidence",
    description="Link evidence to a client issue (POST /v1/issues/{issue_id}/evidence).",
    structured_output=True,
)
async def chatgptrest_issue_link_evidence(
    *,
    issue_id: str,
    job_id: str | None = None,
    conversation_url: str | None = None,
    artifacts_path: str | None = None,
    note: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    body: dict[str, Any] = {}
    if job_id is not None:
        body["job_id"] = str(job_id)
    if conversation_url is not None:
        body["conversation_url"] = str(conversation_url)
    if artifacts_path is not None:
        body["artifacts_path"] = str(artifacts_path)
    if note is not None:
        body["note"] = str(note)
    if source is not None:
        body["source"] = str(source)
    if isinstance(metadata, dict):
        body["metadata"] = dict(metadata)
    return await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v1/issues/{urllib.parse.quote(str(issue_id))}/evidence",
        body=body,
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_issue_events",
    description="List events for a client issue (GET /v1/issues/{issue_id}/events).",
    structured_output=True,
)
async def chatgptrest_issue_events(
    issue_id: str,
    after_id: int = 0,
    limit: int = 200,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    qs = urllib.parse.urlencode({"after_id": int(after_id), "limit": int(limit)}, doseq=False)
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/issues/{urllib.parse.quote(str(issue_id))}/events?{qs}",
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_issue_record_verification",
    description="Record verification evidence for a client issue (POST /v1/issues/{issue_id}/verification).",
    structured_output=True,
)
async def chatgptrest_issue_record_verification(
    *,
    issue_id: str,
    verification_type: str,
    status: str = "passed",
    verifier: str | None = None,
    note: str | None = None,
    job_id: str | None = None,
    conversation_url: str | None = None,
    artifacts_path: str | None = None,
    metadata: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    body: dict[str, Any] = {
        "verification_type": str(verification_type),
        "status": str(status),
    }
    if verifier is not None:
        body["verifier"] = str(verifier)
    if note is not None:
        body["note"] = str(note)
    if job_id is not None:
        body["job_id"] = str(job_id)
    if conversation_url is not None:
        body["conversation_url"] = str(conversation_url)
    if artifacts_path is not None:
        body["artifacts_path"] = str(artifacts_path)
    if isinstance(metadata, dict):
        body["metadata"] = dict(metadata)
    return await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v1/issues/{urllib.parse.quote(str(issue_id))}/verification",
        body=body,
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_issue_list_verifications",
    description="List verification evidence for a client issue (GET /v1/issues/{issue_id}/verification).",
    structured_output=True,
)
async def chatgptrest_issue_list_verifications(
    issue_id: str,
    after_ts: float = 0.0,
    limit: int = 200,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    qs = urllib.parse.urlencode({"after_ts": float(after_ts), "limit": int(limit)}, doseq=False)
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/issues/{urllib.parse.quote(str(issue_id))}/verification?{qs}",
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_issue_record_usage",
    description="Record qualifying client usage for a client issue (POST /v1/issues/{issue_id}/usage).",
    structured_output=True,
)
async def chatgptrest_issue_record_usage(
    *,
    issue_id: str,
    job_id: str,
    client_name: str | None = None,
    kind: str | None = None,
    status: str = "completed",
    answer_chars: int | None = None,
    metadata: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    body: dict[str, Any] = {"job_id": str(job_id), "status": str(status)}
    if client_name is not None:
        body["client_name"] = str(client_name)
    if kind is not None:
        body["kind"] = str(kind)
    if answer_chars is not None:
        body["answer_chars"] = int(answer_chars)
    if isinstance(metadata, dict):
        body["metadata"] = dict(metadata)
    return await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v1/issues/{urllib.parse.quote(str(issue_id))}/usage",
        body=body,
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_issue_list_usage",
    description="List qualifying client usage for a client issue (GET /v1/issues/{issue_id}/usage).",
    structured_output=True,
)
async def chatgptrest_issue_list_usage(
    issue_id: str,
    after_ts: float = 0.0,
    limit: int = 200,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    qs = urllib.parse.urlencode({"after_ts": float(after_ts), "limit": int(limit)}, doseq=False)
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/issues/{urllib.parse.quote(str(issue_id))}/usage?{qs}",
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_issue_graph_query",
    description="Query the issue knowledge graph (POST /v1/issues/graph/query).",
    structured_output=True,
)
async def chatgptrest_issue_graph_query(
    *,
    issue_id: str | None = None,
    family_id: str | None = None,
    q: str | None = None,
    status: str | None = None,
    include_closed: bool = True,
    limit: int = 20,
    neighbor_depth: int = 1,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    body = {
        "issue_id": issue_id,
        "family_id": family_id,
        "q": q,
        "status": status,
        "include_closed": bool(include_closed),
        "limit": int(limit),
        "neighbor_depth": int(neighbor_depth),
    }
    return await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v1/issues/graph/query",
        body=body,
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="chatgptrest_issue_digest",
    description="Get a compact digest of open issues grouped by severity and kind.",
    structured_output=True,
)
async def chatgptrest_issue_digest(
    *,
    project: str | None = None,
    include_closed_since_hours: float = 0,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Returns issue counts by severity/kind plus top issues list."""
    base = _base_url()
    qs_parts: dict[str, str] = {"status": "open,in_progress", "limit": "200"}
    if project and str(project).strip():
        qs_parts["project"] = str(project).strip()
    qs = urllib.parse.urlencode(qs_parts, doseq=False)
    open_resp = await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/issues?{qs}",
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )
    issues = open_resp.get("issues", [])

    # Optionally include recently closed
    recently_closed: list[dict[str, Any]] = []
    if include_closed_since_hours > 0:
        since_ts = time.time() - float(include_closed_since_hours) * 3600
        qs_closed = urllib.parse.urlencode({
            "status": "closed,mitigated",
            "since_ts": str(since_ts),
            "limit": "50",
            **({"project": str(project).strip()} if project and str(project).strip() else {}),
        }, doseq=False)
        closed_resp = await asyncio.to_thread(
            _http_json,
            method="GET",
            url=f"{base}/v1/issues?{qs_closed}",
            headers=_auth_headers(),
            timeout_seconds=30.0,
        )
        recently_closed = closed_resp.get("issues", [])

    # Build digest
    by_severity: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    total_occurrences = 0
    for iss in issues:
        sev = str(iss.get("severity", "P2"))
        kind = str(iss.get("kind", "unknown"))
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_kind[kind] = by_kind.get(kind, 0) + 1
        total_occurrences += int(iss.get("count", 1))

    # Top issues (P0 first, then by count)
    severity_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    top = sorted(
        issues,
        key=lambda i: (severity_order.get(str(i.get("severity", "P2")), 9), -int(i.get("count", 0))),
    )[:20]

    return {
        "open_count": len(issues),
        "total_occurrences": total_occurrences,
        "by_severity": by_severity,
        "by_kind": by_kind,
        "top_issues": [
            {
                "issue_id": i.get("issue_id"),
                "title": i.get("title"),
                "severity": i.get("severity"),
                "count": i.get("count"),
                "kind": i.get("kind"),
                "status": i.get("status"),
                "last_seen_at": i.get("last_seen_at"),
            }
            for i in top
        ],
        "recently_closed_count": len(recently_closed),
        "recently_closed": [
            {
                "issue_id": i.get("issue_id"),
                "title": i.get("title"),
                "closed_at": i.get("closed_at"),
            }
            for i in recently_closed[:10]
        ],
    }


@mcp.tool(
    name="chatgptrest_issue_auto_link_repair",
    description="Link a repair.check job result to matching open issues by error pattern.",
    structured_output=True,
)
async def chatgptrest_issue_auto_link_repair(
    *,
    repair_job_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Fetch repair.check result and auto-link to matching open issues."""
    base = _base_url()
    headers = _auth_headers()

    # 1. Get repair job details
    repair_job = await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/jobs/{urllib.parse.quote(str(repair_job_id))}",
        headers=headers,
        timeout_seconds=15.0,
    )

    # 2. Get open issues
    open_resp = await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/issues?status=open%2Cin_progress&limit=100",
        headers=headers,
        timeout_seconds=15.0,
    )
    issues = open_resp.get("issues", [])

    # 3. Match issues by error pattern from the repair result
    repair_error_type = str(repair_job.get("last_error_type", "") or "").lower()
    repair_symptom = str(repair_job.get("input", {}).get("symptom", "") or "").lower()

    linked: list[dict[str, Any]] = []
    for iss in issues:
        title_lower = str(iss.get("title", "")).lower()
        raw_error_lower = str(iss.get("raw_error", "") or "").lower()

        matched = False
        if repair_error_type and (repair_error_type in title_lower or repair_error_type in raw_error_lower):
            matched = True
        if repair_symptom and repair_symptom in title_lower:
            matched = True

        if matched:
            try:
                await asyncio.to_thread(
                    _http_json,
                    method="POST",
                    url=f"{base}/v1/issues/{urllib.parse.quote(str(iss['issue_id']))}/evidence",
                    body={
                        "job_id": repair_job_id,
                        "note": f"repair.check result: {repair_job.get('status', '?')}",
                        "source": "repair_auto_link",
                    },
                    headers=headers,
                    timeout_seconds=10.0,
                )
                linked.append({"issue_id": iss["issue_id"], "title": iss.get("title")})
            except Exception:
                pass

    return {
        "repair_job_id": repair_job_id,
        "repair_status": repair_job.get("status"),
        "matched_issues": len(linked),
        "linked": linked,
    }


# ══════════════════════════════════════════════════════════════════════════
# L0 Core Tools — Agent-optimized interface (submit→result in 2-3 calls)
# ══════════════════════════════════════════════════════════════════════════

# ── Answer Prefetch (delegated to chatgptrest.mcp._answer_cache) ─────────


async def _answer_prefetch(job_id: str) -> None:
    """Pre-fetch and cache the answer. Delegates to _answer_cache module."""
    await _answer_cache.prefetch(
        str(job_id),
        http_json_fn=_http_json,
        base_url=_base_url(),
        auth_headers=_auth_headers(),
    )


async def _answer_prefetch_get(job_id: str) -> dict[str, Any] | None:
    """Get cached answer prefetch. Delegates to _answer_cache module."""
    return await _answer_cache.get(str(job_id))


def _set_inline_answer_fields(
    out: dict[str, Any],
    normalized: dict[str, Any],
    *,
    source: str,
    completion_quality: str,
) -> None:
    content = str(normalized.get("content") or "")
    try:
        offset = int(normalized.get("offset") or 0)
    except Exception:
        offset = 0
    try:
        length = int(normalized.get("length") or len(content))
    except Exception:
        length = len(content)
    total_bytes_raw = normalized.get("total_bytes")
    try:
        total_bytes = int(total_bytes_raw) if total_bytes_raw is not None else offset + length
    except Exception:
        total_bytes = offset + length
    done_raw = normalized.get("done")
    done = bool(done_raw) if isinstance(done_raw, bool) else total_bytes <= offset + length
    next_offset_raw = normalized.get("next_offset")
    try:
        next_offset = int(next_offset_raw) if next_offset_raw is not None else None
    except Exception:
        next_offset = None

    out["answer"] = content
    out["answer_total_bytes"] = total_bytes
    out["answer_length"] = max(0, length)
    out["answer_offset"] = max(0, offset)
    out["answer_truncated"] = not done
    if not done:
        out["next_offset"] = next_offset if next_offset is not None else offset + length
    else:
        out.pop("next_offset", None)
    out["answer_source"] = source
    out["action_hint"] = "review_completed_answer" if completion_quality and completion_quality != "final" else "answer_ready"


# Provider kind mapping delegated to chatgptrest.mcp._providers
_PROVIDER_TO_KIND = __import__('chatgptrest.mcp._providers', fromlist=['PROVIDER_TO_KIND']).PROVIDER_TO_KIND
_KIND_TO_PROVIDER = __import__('chatgptrest.mcp._providers', fromlist=['KIND_TO_PROVIDER']).KIND_TO_PROVIDER
_resolve_provider = __import__('chatgptrest.mcp._providers', fromlist=['resolve_provider']).resolve_provider


# ── L0 Tool 1: chatgptrest_ask ───────────────────────────────────────────

@mcp.tool(
    name="chatgptrest_ask",
    description=(
        "Unified ask tool — submit a question to ChatGPT/Gemini/Qwen and return immediately.\n"
        "Server auto-starts background wait + answer prefetch. Use chatgptrest_result() to get the answer.\n"
        "Replaces chatgptrest_chatgpt_ask_submit / chatgptrest_gemini_ask_submit / chatgptrest_qwen_ask_submit + manual background wait.\n"
        "Typical flow: chatgptrest_ask() → ... do other work ... → chatgptrest_result(job_id)\n"
        "Set auto_context=true to automatically inject relevant KB knowledge into the prompt."
    ),
    structured_output=True,
)
async def chatgptrest_ask(
    *,
    idempotency_key: str,
    question: str,
    # ── Routing ──
    provider: str = "chatgpt",
    preset: str = "auto",
    # ── Follow-up ──
    parent_job_id: str | None = None,
    conversation_url: str | None = None,
    # ── Common optional ──
    file_paths: list[str] | str | None = None,
    deep_research: bool | None = None,
    # ── KB Context ──
    auto_context: bool = False,
    auto_context_top_k: int = 3,
    # ── Timeouts ──
    timeout_seconds: int = 600,
    max_wait_seconds: int = 1800,
    min_chars: int | None = None,
    # ── Server behavior ──
    auto_wait: bool = True,
    notify_done: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    # Resolve provider
    p = _resolve_provider(provider=provider, conversation_url=conversation_url)
    kind = _PROVIDER_TO_KIND[p]

    # KB context enrichment
    enriched_question = str(question)
    kb_context_injected = False
    if auto_context and not parent_job_id:
        # Only enrich for fresh questions, not follow-ups
        try:
            recall_result = await asyncio.to_thread(
                _http_json,
                method="POST",
                url=f"{_base_url()}/v1/advisor/recall",
                body={"query": str(question), "top_k": int(auto_context_top_k)},
                headers=_auth_headers(),
                timeout_seconds=10.0,
            )
            if isinstance(recall_result, dict) and recall_result.get("ok"):
                hits = recall_result.get("hits") or []
                if hits:
                    parts = []
                    total = 0
                    for h in hits:
                        title = str(h.get("title") or "")
                        snippet = str(h.get("snippet") or "")
                        entry = f"[{title}] {snippet}" if title else snippet
                        if total + len(entry) > 2000:
                            break
                        parts.append(entry)
                        total += len(entry)
                    if parts:
                        kb_prefix = "相关知识库参考：\n" + "\n---\n".join(parts)
                        enriched_question = f"{kb_prefix}\n\n---\n\n用户问题：{question}"
                        kb_context_injected = True
        except Exception:
            pass  # KB enrichment failure is non-fatal

    # Build input
    input_obj: dict[str, Any] = {"question": enriched_question}
    if conversation_url:
        input_obj["conversation_url"] = str(conversation_url)
    if parent_job_id:
        input_obj["parent_job_id"] = str(parent_job_id)
    if file_paths:
        if isinstance(file_paths, str):
            input_obj["file_paths"] = [file_paths]
        else:
            input_obj["file_paths"] = list(file_paths)

    effective_min_chars = min_chars
    if effective_min_chars is None:
        effective_min_chars = 800 if p == "chatgpt" else 200

    # Build params
    params_obj: dict[str, Any] = {
        "preset": str(preset),
        "timeout_seconds": int(timeout_seconds),
        "max_wait_seconds": int(max_wait_seconds),
        "min_chars": max(0, int(effective_min_chars)),
        "answer_format": "markdown",
    }
    if deep_research is not None:
        params_obj["deep_research"] = bool(deep_research)

    # Submit
    job = await chatgptrest_job_create(
        idempotency_key=idempotency_key,
        kind=kind,
        input=input_obj,
        params=params_obj,
        client={"name": "chatgptrest_ask", "provider": p},
        ctx=ctx,
    )

    jid = str(job.get("job_id") or "").strip()
    status = str(job.get("status") or "").strip().lower()

    # Auto-start background wait + answer prefetch
    if auto_wait and jid and status not in TERMINAL_STATUSES:
        try:
            await _background_wait_start(
                job_id=jid,
                cfg=BackgroundWaitConfig(
                    timeout_seconds=max(int(max_wait_seconds), 3600),
                    poll_seconds=1.0,
                    notify_controller=True,
                    notify_done=bool(notify_done),
                    force_restart=False,
                ),
                ctx=ctx,
            )
        except Exception:
            pass  # best-effort; bg wait failure is non-fatal

    # Notify
    if notify_done:
        await _maybe_notify_done(job, notify_done=True)

    _tmux_notify(f"[chatgptrest] ask {jid} ({p}/{preset}) est_wait={job.get('estimated_wait_seconds')}s")

    # Enhance response for agent convenience
    out = dict(job) if isinstance(job, dict) else {"job": job}
    out["provider"] = p
    out["action_hint"] = "poll_result" if status not in TERMINAL_STATUSES else "fetch_answer"
    out["suggested_poll_seconds"] = 30 if not bool(deep_research) else 120
    out["kb_context_injected"] = kb_context_injected
    return out


# ── L0 Tool 2: chatgptrest_result ────────────────────────────────────────

@mcp.tool(
    name="chatgptrest_result",
    description=(
        "One-stop result retrieval — get job status + answer in one call.\n"
        "If job is completed and include_answer=true, returns the answer inline (up to max_answer_chars).\n"
        "If job is still running, returns progress info and a suggested retry interval.\n"
        "Replaces chatgptrest_job_get + chatgptrest_job_wait_background_get + chatgptrest_answer_get."
    ),
    structured_output=True,
)
async def chatgptrest_result(
    job_id: str,
    *,
    include_answer: bool = True,
    max_answer_chars: int = 24000,
    answer_offset: int = 0,
    ctx: Context | None = None,
) -> dict[str, Any]:
    jid = str(job_id or "").strip()
    if not jid:
        return {"ok": False, "error_type": "ValueError", "error": "job_id is required"}

    base = _base_url()

    # 1. Get job status
    try:
        job = await asyncio.to_thread(
            _http_json,
            method="GET",
            url=f"{base}/v1/jobs/{urllib.parse.quote(jid)}",
            headers=_auth_headers(),
            timeout_seconds=30.0,
        )
    except Exception as exc:
        return {"ok": False, "job_id": jid, "error_type": type(exc).__name__, "error": str(exc)[:800]}

    if not isinstance(job, dict):
        return {"ok": False, "job_id": jid, "error_type": "TypeError", "error": "unexpected response"}

    status = str(job.get("status") or "").strip().lower()
    out: dict[str, Any] = dict(job)
    out["provider"] = _KIND_TO_PROVIDER.get(str(job.get("kind") or "").strip().lower())

    # 2. Enrich with background wait state if available
    async with _BACKGROUND_WAIT_LOCK:
        watch_id = _BACKGROUND_WAIT_BY_JOB.get(jid)
        if watch_id:
            bg_state = _BACKGROUND_WAIT_STATE.get(watch_id)
            if isinstance(bg_state, dict):
                out["background_wait"] = {
                    "watch_id": watch_id,
                    "watch_status": bg_state.get("watch_status"),
                    "poll_count": bg_state.get("poll_count"),
                    "started_at": bg_state.get("started_at"),
                    "heartbeat_at": bg_state.get("heartbeat_at"),
                }

    # 3. Handle by status
    if status == "completed" and include_answer:
        completion_quality = str(out.get("completion_quality") or "").strip().lower()
        # Try prefetch cache first
        cached = await _answer_prefetch_get(jid)
        if cached and answer_offset == 0:
            normalized = _answer_cache.normalize_answer_payload(cached, requested_offset=0)
            if normalized is not None:
                _set_inline_answer_fields(out, normalized, source="prefetch_cache", completion_quality=completion_quality)
        else:
            # Fetch answer from API
            try:
                qs = urllib.parse.urlencode(
                    {"offset": int(answer_offset), "max_chars": int(max_answer_chars)},
                    doseq=False,
                )
                answer = await asyncio.to_thread(
                    _http_json,
                    method="GET",
                    url=f"{base}/v1/jobs/{urllib.parse.quote(jid)}/answer?{qs}",
                    headers=_auth_headers(),
                    timeout_seconds=30.0,
                )
                normalized = _answer_cache.normalize_answer_payload(answer, requested_offset=int(answer_offset))
                if normalized is not None:
                    _set_inline_answer_fields(out, normalized, source="api", completion_quality=completion_quality)
            except Exception as exc:
                out["answer_error"] = str(exc)[:400]
                out["action_hint"] = "fetch_answer_failed"
    elif status == "completed":
        out["action_hint"] = "fetch_answer"
    elif status in ("queued", "in_progress"):
        est = job.get("estimated_wait_seconds")
        out["action_hint"] = "poll_later"
        out["suggested_retry_seconds"] = min(60, max(15, int(est or 30) // 3)) if est else 30
    elif status == "cooldown":
        retry_after = job.get("retry_after_seconds")
        out["action_hint"] = "retry_after_cooldown"
        out["suggested_retry_seconds"] = int(retry_after) if retry_after else 60
    elif status in ("error", "blocked"):
        out["action_hint"] = "investigate_or_retry"
    elif status == "needs_followup":
        out["action_hint"] = "followup_required"
    elif status == "canceled":
        out["action_hint"] = "job_canceled"
    else:
        out["action_hint"] = "unknown_status"

    return out


# ── L0 Tool 3: chatgptrest_followup ──────────────────────────────────────

@mcp.tool(
    name="chatgptrest_followup",
    description=(
        "Simplified follow-up — continue a conversation by referencing parent_job_id.\n"
        "Auto-detects provider from parent job, inherits conversation_url.\n"
        "Equivalent to chatgptrest_ask(parent_job_id=...) but with fewer required params."
    ),
    structured_output=True,
)
async def chatgptrest_followup(
    *,
    idempotency_key: str,
    parent_job_id: str,
    question: str,
    preset: str = "auto",
    deep_research: bool | None = None,
    min_chars: int | None = None,
    file_paths: list[str] | str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    # Lookup parent job to detect provider
    pjid = str(parent_job_id).strip()
    parent_job: dict[str, Any] | None = None
    try:
        parent_job = await chatgptrest_job_get(pjid, ctx=ctx)
    except Exception:
        pass

    provider = _resolve_provider(parent_job=parent_job)

    return await chatgptrest_ask(
        idempotency_key=idempotency_key,
        question=question,
        provider=provider,
        preset=preset,
        parent_job_id=pjid,
        deep_research=deep_research,
        min_chars=min_chars,
        file_paths=file_paths,
        auto_wait=True,
        notify_done=True,
        ctx=ctx,
    )


# ── L1 Tool: chatgptrest_consult ─────────────────────────────────────────

@mcp.tool(
    name="chatgptrest_consult",
    description=(
        "Parallel multi-model consultation — submit the same question to multiple models at once.\n"
        "Useful for crosscheck, quality comparison, or getting diverse perspectives.\n"
        "Returns a consultation_id; use chatgptrest_consult_result() to get all answers.\n"
        "Mode shortcuts: 'default' (chatgpt_pro + gemini_deepthink), "
        "'deep_research' (chatgpt_dr + gemini_dr), "
        "'thinking' (chatgpt_pro + gemini_deepthink + qwen), "
        "'all' (all 5 models).\n"
        "Or specify models list directly: chatgpt_pro, gemini_deepthink, chatgpt_dr, gemini_dr, qwen.\n"
        "auto_context=true injects KB knowledge into the prompt automatically."
    ),
    structured_output=True,
)
async def chatgptrest_consult(
    *,
    question: str,
    mode: str | None = None,
    models: list[str] | None = None,
    file_paths: list[str] | str | None = None,
    auto_context: bool = True,
    auto_context_top_k: int = 3,
    persist_answer: bool = False,
    timeout_seconds: int = 600,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    body: dict[str, Any] = {
        "question": str(question),
        "auto_context": bool(auto_context),
        "auto_context_top_k": int(auto_context_top_k),
        "persist_answer": bool(persist_answer),
        "timeout_seconds": int(timeout_seconds),
    }
    if mode:
        body["mode"] = str(mode)
    if models:
        body["models"] = models
    if file_paths:
        if isinstance(file_paths, str):
            body["file_paths"] = [file_paths]
        else:
            body["file_paths"] = list(file_paths)
    result = await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v1/advisor/consult",
        body=body,
        headers=_auth_headers(),
        timeout_seconds=max(30.0, float(timeout_seconds)),
    )

    # Auto-start background waits for all jobs
    if isinstance(result, dict) and result.get("ok"):
        for job_info in (result.get("jobs") or []):
            jid = str(job_info.get("job_id") or "").strip()
            if jid:
                try:
                    await _background_wait_start(
                        job_id=jid,
                        cfg=BackgroundWaitConfig(
                            timeout_seconds=max(int(timeout_seconds) * 3, 3600),
                            poll_seconds=1.0,
                            notify_controller=True,
                            notify_done=True,
                            force_restart=False,
                        ),
                        ctx=ctx,
                    )
                except Exception:
                    pass

    return result


# ── L1 Tool: chatgptrest_consult_result ──────────────────────────────────

@mcp.tool(
    name="chatgptrest_consult_result",
    description=(
        "Get status and answers from a parallel consultation.\n"
        "Returns all job statuses and any available answers.\n"
        "Once all_completed=true, all model answers are available."
    ),
    structured_output=True,
)
async def chatgptrest_consult_result(
    consultation_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v1/advisor/consult/{urllib.parse.quote(str(consultation_id))}",
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


# ── L1 Tool: chatgptrest_recall ──────────────────────────────────────────

@mcp.tool(
    name="chatgptrest_recall",
    description=(
        "Search accumulated knowledge in the KB.\n"
        "Returns matching documents with relevance scores.\n"
        "Use before deciding whether to call external models — the answer might already be in KB."
    ),
    structured_output=True,
)
async def chatgptrest_recall(
    query: str,
    *,
    top_k: int = 5,
    ctx: Context | None = None,
) -> dict[str, Any]:
    base = _base_url()
    body: dict[str, Any] = {
        "query": str(query),
        "top_k": int(top_k),
    }
    return await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v1/advisor/recall",
        body=body,
        headers=_auth_headers(),
        timeout_seconds=15.0,
    )


@mcp.tool(
    name="advisor_agent_turn",
    description=(
        "Execute a single advisor agent turn.\n"
        "High-level entry point for agent interactions - abstracts away job/wait/answer machinery.\n"
        "Returns final answer directly without needing to manage jobs."
    ),
    structured_output=True,
)
async def advisor_agent_turn(
    message: str,
    session_id: str = "",
    goal_hint: str = "",
    depth: str = "standard",
    execution_profile: str = "",
    timeout_seconds: int = 300,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Execute a single advisor agent turn."""
    base = _base_url()
    body: dict[str, Any] = {
        "message": str(message),
        "session_id": str(session_id) if session_id else "",
        "goal_hint": str(goal_hint) if goal_hint else "",
        "depth": str(depth) if depth else "standard",
        "timeout_seconds": int(timeout_seconds),
        "client": {
            "name": "chatgptrest-mcp",
            "instance": "legacy",
        },
    }
    if execution_profile:
        body["execution_profile"] = str(execution_profile)
    return await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v3/agent/turn",
        body=body,
        headers=_auth_headers(),
        timeout_seconds=float(timeout_seconds) + 30.0,
    )


@mcp.tool(
    name="advisor_agent_cancel",
    description=(
        "Cancel a running agent session.\n"
        "Cancels the session at the facade level."
    ),
    structured_output=True,
)
async def advisor_agent_cancel(
    session_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Cancel an agent session."""
    base = _base_url()
    body: dict[str, Any] = {
        "session_id": str(session_id),
    }
    return await asyncio.to_thread(
        _http_json,
        method="POST",
        url=f"{base}/v3/agent/cancel",
        body=body,
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


@mcp.tool(
    name="advisor_agent_status",
    description=(
        "Get status of an agent session.\n"
        "Returns current session state, last answer, and next actions."
    ),
    structured_output=True,
)
async def advisor_agent_status(
    session_id: str,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get agent session status."""
    base = _base_url()
    return await asyncio.to_thread(
        _http_json,
        method="GET",
        url=f"{base}/v3/agent/session/{session_id}",
        headers=_auth_headers(),
        timeout_seconds=15.0,
    )
