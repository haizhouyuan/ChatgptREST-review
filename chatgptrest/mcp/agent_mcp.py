"""Public Agent MCP Server - Lightweight MCP for advisor-agent interactions.

This is a separate public MCP server that exposes only a few high-level tools:
- advisor_agent_turn: Execute a single agent turn
- advisor_agent_cancel: Cancel a running session
- advisor_agent_status: Get session status
- advisor_agent_wait: Wait for a terminal session result

This server is designed for Codex/Claude Code/Antigravity clients who don't
need to see all 51 low-level tools from the main chatgptrest-mcp.
"""

from __future__ import annotations

import asyncio
import http.client
import json
import os
import socket
import subprocess
import tempfile
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from chatgptrest.core.file_path_inputs import coerce_file_path_input
from chatgptrest.core.control_plane import (
    parse_host_port_from_url as _parse_host_port_from_url,
    port_open as _shared_port_open,
    start_local_api as _shared_start_local_api,
)
from chatgptrest.core.runtime_contract import (
    public_agent_client_name as _runtime_contract_client_name,
    public_agent_mcp_runtime_contract_state,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _fastmcp_host_port() -> tuple[str, int]:
    host = os.environ.get("FASTMCP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port_raw = (os.environ.get("FASTMCP_PORT") or "").strip()
    if not port_raw:
        return host, 18712
    try:
        return host, int(port_raw)
    except ValueError:
        return host, 18712


def _base_url() -> str:
    raw = os.environ.get("CHATGPTREST_AGENT_MCP_BASE_URL", "").strip()
    if raw:
        return raw.rstrip("/")
    return os.environ.get("CHATGPTREST_BASE_URL", "http://127.0.0.1:18711").rstrip("/")


def _api_key() -> str:
    return os.environ.get("OPENMIND_API_KEY", os.environ.get("CHATGPTREST_API_TOKEN", "")).strip()


def public_agent_mcp_auth_state() -> dict[str, Any]:
    return public_agent_mcp_runtime_contract_state()


def ensure_public_agent_mcp_auth_configured() -> dict[str, Any]:
    state = public_agent_mcp_auth_state()
    if state.get("token_present") and not state.get("allowlisted"):
        raise RuntimeError(
            "Public agent MCP service_identity_not_allowlisted: "
            f"client_name={state.get('client_name')} is not present in "
            "CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST. Add the running MCP client identity to the API allowlist "
            "or align CHATGPTREST_AGENT_MCP_CLIENT_NAME/CHATGPTREST_CLIENT_NAME before starting the service."
        )
    if state.get("ok"):
        return state
    raise RuntimeError(
        "Public agent MCP requires OPENMIND_API_KEY or CHATGPTREST_API_TOKEN in the process environment. "
        "Use the systemd-managed http://127.0.0.1:18712/mcp service or launch via ops/start_mcp.sh; "
        "do not start an ad-hoc public MCP process without loading the ChatgptREST env files."
    )


_HOST, _PORT = _fastmcp_host_port()


def _agent_fastmcp_stateless_http_default() -> bool:
    raw = (os.environ.get("CHATGPTREST_AGENT_MCP_STATELESS_HTTP") or "").strip().lower()
    if not raw:
        return False
    return raw in {"1", "true", "yes", "on"}


mcp = FastMCP(
    "chatgptrest-agent-mcp",
    host=_HOST,
    port=_PORT,
    stateless_http=_agent_fastmcp_stateless_http_default(),
)

_LONG_RUNNING_GOAL_HINTS = {
    "consult",
    "dual_review",
    "gemini_deep_research",
    "gemini_research",
    "report",
    "research",
    "write_report",
}
_AGENT_WATCH_LOCK = asyncio.Lock()
_AGENT_WATCH_TASKS: dict[str, asyncio.Task[None]] = {}
_AGENT_WATCH_STATE: dict[str, dict[str, Any]] = {}
_AGENT_WATCH_BY_SESSION: dict[str, str] = {}
_AGENT_WATCH_SEQ = 0
_AGENT_AUTOSTART_LOCK = threading.Lock()
_AGENT_AUTOSTART_LAST_TS = 0.0
_AGENT_TERMINAL_STATUSES = {
    "blocked",
    "canceled",
    "cancelled",
    "completed",
    "cooldown",
    "error",
    "failed",
    "needs_followup",
    "needs_input",
}
_DEFAULT_AGENT_WATCH_RESUME_TIMEOUT_SECONDS = 12 * 60 * 60


class _AgentWatchStore:
    """File-backed persistence for public MCP watch state across MCP restarts."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @classmethod
    def from_env(cls) -> "_AgentWatchStore":
        session_dir = str(os.environ.get("CHATGPTREST_AGENT_SESSION_DIR", "")).strip()
        if session_dir:
            return cls(Path(session_dir).expanduser().resolve().parent / "agent_mcp_watch")

        db_path = str(os.environ.get("CHATGPTREST_DB_PATH", "")).strip()
        if db_path:
            return cls(Path(db_path).expanduser().resolve().parent / "agent_mcp_watch")

        if os.environ.get("PYTEST_CURRENT_TEST"):
            return cls(Path(tempfile.mkdtemp(prefix="agent-mcp-watch-store-")))

        return cls(Path("/tmp/chatgptrest-agent-mcp-watch"))

    def _watch_path(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.json"

    def get(self, session_id: str) -> dict[str, Any] | None:
        path = self._watch_path(session_id)
        if not path.exists():
            return None
        with self._lock:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None

    def put(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        path = self._watch_path(session_id)
        tmp_path = path.with_suffix(".tmp")
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._lock:
            tmp_path.write_text(data, encoding="utf-8")
            tmp_path.replace(path)
        return dict(payload)

    def delete(self, session_id: str) -> None:
        path = self._watch_path(session_id)
        with self._lock:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                return


_AGENT_WATCH_STORE = _AgentWatchStore.from_env()


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


def _port_open(host: str, port: int, *, timeout_seconds: float = 0.2) -> bool:
    return _shared_port_open(host, port, timeout_seconds=timeout_seconds)


def _maybe_autostart_api_for_base_url(base_url: str) -> bool:
    global _AGENT_AUTOSTART_LAST_TS
    hp = _parse_host_port_from_base_url(base_url)
    if hp is None:
        return False
    host, port = hp
    host_l = str(host).strip().lower()
    if host_l not in {"127.0.0.1", "localhost"}:
        return False
    if _port_open(host, port, timeout_seconds=0.2):
        return False

    with _AGENT_AUTOSTART_LOCK:
        now = time.time()
        min_interval_raw = (os.environ.get("CHATGPTREST_MCP_AUTO_START_API_MIN_INTERVAL_SECONDS") or "").strip()
        try:
            min_interval = float(min_interval_raw) if min_interval_raw else 30.0
        except Exception:
            min_interval = 30.0
        if now - float(_AGENT_AUTOSTART_LAST_TS) < max(0.0, min_interval):
            return False
        _AGENT_AUTOSTART_LAST_TS = now

        ok, _meta = _shared_start_local_api(
            repo_root=_REPO_ROOT,
            host=str(host),
            port=int(port),
            action_log=(_REPO_ROOT / "logs" / "chatgptrest_api.autostart.log").resolve(),
            out_log=(_REPO_ROOT / "logs" / "chatgptrest_api.log").resolve(),
            wait_seconds=8.0,
            action_label="public agent mcp autostart api",
        )
        return bool(ok)


def _open_with_recovery(req: urllib.request.Request, *, timeout: float) -> Any:
    attempts = 2 if _truthy_env("CHATGPTREST_MCP_AUTO_START_API", False) else 1
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except (urllib.error.URLError, http.client.RemoteDisconnected, ConnectionError, TimeoutError, socket.timeout) as exc:
            last_exc = exc
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
            raise
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("failed to open request")


def _client_name() -> str:
    return _runtime_contract_client_name()


def _client_instance() -> str:
    raw = (os.environ.get("CHATGPTREST_AGENT_MCP_CLIENT_INSTANCE") or os.environ.get("CHATGPTREST_CLIENT_INSTANCE") or "").strip()
    if raw:
        return raw
    return f"public-agent-mcp-{os.getpid()}"


def _clean_client_label(value: Any, *, max_chars: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:max_chars]


def _public_agent_client_payload(ctx: Context | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "mcp-agent",
        "instance": "public-mcp",
    }
    if not ctx:
        return payload
    try:
        sess = ctx.session
        params = sess.client_params if sess is not None else None
        info = getattr(params, "clientInfo", None) if params is not None else None
        name = _clean_client_label(getattr(info, "name", None))
        version = _clean_client_label(getattr(info, "version", None))
        client_id = _clean_client_label(getattr(ctx, "client_id", None))
        if name:
            payload["name"] = name
            payload["mcp_client_name"] = name
        if version:
            payload["mcp_client_version"] = version
        if client_id:
            payload["mcp_client_id"] = client_id
    except Exception:
        return payload
    return payload


def _new_request_id() -> str:
    prefix = (os.environ.get("CHATGPTREST_AGENT_MCP_REQUEST_ID_PREFIX") or os.environ.get("CHATGPTREST_REQUEST_ID_PREFIX") or _client_name()).strip() or _client_name()
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _truthy_env(name: str, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on"}


def _agent_watch_enabled() -> bool:
    return _truthy_env("CHATGPTREST_AGENT_MCP_AUTO_WATCH", True)


def _agent_watch_notify_done_enabled() -> bool:
    return _truthy_env("CHATGPTREST_AGENT_MCP_NOTIFY_DONE", True)


def _agent_watch_retention_seconds() -> float:
    raw = (os.environ.get("CHATGPTREST_AGENT_MCP_WATCH_RETENTION_SECONDS") or "").strip()
    try:
        value = float(raw) if raw else 24 * 60 * 60
    except Exception:
        value = 24 * 60 * 60
    return max(60.0, value)


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


def _watch_state_view(state: dict[str, Any], *, include_result: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "watch_id": str(state.get("watch_id") or ""),
        "session_id": str(state.get("session_id") or ""),
        "watch_status": str(state.get("watch_status") or ""),
        "started_at": state.get("started_at"),
        "updated_at": state.get("updated_at"),
        "ended_at": state.get("ended_at"),
        "notify_done": bool(state.get("notify_done")),
        "running": str(state.get("watch_status") or "") == "running",
        "done": str(state.get("watch_status") or "") in {"completed", "error", "canceled"},
        "last_status": str(state.get("last_status") or ""),
        "last_event_type": str(state.get("last_event_type") or ""),
    }
    if state.get("error"):
        out["error"] = str(state.get("error"))
    if state.get("error_type"):
        out["error_type"] = str(state.get("error_type"))
    if include_result and isinstance(state.get("result_session"), dict):
        out["result_session"] = dict(state["result_session"])
    return out


def _persist_watch_state(state: dict[str, Any]) -> None:
    session_id = str(state.get("session_id") or "").strip()
    if not session_id:
        return
    payload = dict(state)
    if not isinstance(payload.get("result_session"), dict):
        payload.pop("result_session", None)
    _AGENT_WATCH_STORE.put(session_id, payload)


def _delete_persisted_watch_state(session_id: str) -> None:
    sid = str(session_id or "").strip()
    if not sid:
        return
    _AGENT_WATCH_STORE.delete(sid)


def _restore_persisted_watch_state_locked(session_id: str) -> dict[str, Any] | None:
    sid = str(session_id or "").strip()
    if not sid:
        return None
    existing_watch_id = _AGENT_WATCH_BY_SESSION.get(sid)
    existing_state = _AGENT_WATCH_STATE.get(existing_watch_id) if existing_watch_id else None
    if isinstance(existing_state, dict):
        return existing_state
    persisted = _AGENT_WATCH_STORE.get(sid)
    if not isinstance(persisted, dict):
        return None
    watch_id = str(persisted.get("watch_id") or "").strip()
    if not watch_id:
        return None
    _AGENT_WATCH_STATE[watch_id] = persisted
    _AGENT_WATCH_BY_SESSION[sid] = watch_id
    return persisted


def _agent_watch_gc_locked(*, now: float | None = None) -> None:
    ts = float(time.time() if now is None else now)
    keep_seconds = _agent_watch_retention_seconds()
    stale_ids: list[str] = []
    for watch_id, state in list(_AGENT_WATCH_STATE.items()):
        status = str(state.get("watch_status") or "").strip().lower()
        if status == "running":
            continue
        ended_at = float(state.get("ended_at") or state.get("updated_at") or ts)
        if (ts - ended_at) > keep_seconds:
            stale_ids.append(watch_id)
    for watch_id in stale_ids:
        state = _AGENT_WATCH_STATE.pop(watch_id, None)
        _AGENT_WATCH_TASKS.pop(watch_id, None)
        if isinstance(state, dict):
            sid = str(state.get("session_id") or "").strip()
            if sid and _AGENT_WATCH_BY_SESSION.get(sid) == watch_id:
                _AGENT_WATCH_BY_SESSION.pop(sid, None)
            if sid:
                _delete_persisted_watch_state(sid)


def _should_auto_background(*, goal_hint: str, delivery_mode: str) -> bool:
    requested = str(delivery_mode or "").strip().lower()
    if requested in {"deferred", "background", "async"}:
        return True
    return str(goal_hint or "").strip().lower() in _LONG_RUNNING_GOAL_HINTS


def _normalize_stream_url(*, base: str, stream_url: str, session_id: str) -> str:
    raw = str(stream_url or "").strip()
    if not raw:
        return f"{base}/v3/agent/session/{session_id}/stream"
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if raw.startswith("/"):
        return f"{base}{raw}"
    return urllib.parse.urljoin(f"{base}/", raw)


def _build_request(*, url: str, method: str, api_key: str, payload: dict[str, Any] | None = None) -> urllib.request.Request:
    data = None
    client_name = _client_name()
    headers = {
        "Accept": "application/json",
        "User-Agent": "chatgptrest-agent-mcp/0.1.0",
        "X-Client-Name": client_name,
        "X-Client-Instance": _client_instance(),
        "X-Request-ID": _new_request_id(),
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    if api_key:
        req.add_header("X-Api-Key", api_key)
    return req


def _read_json_response(resp: Any) -> dict[str, Any]:
    return json.loads(resp.read().decode("utf-8"))


def _structured_http_error_result(
    exc: urllib.error.HTTPError,
    *,
    session_id: str = "",
    requested_delivery_mode: str = "",
    effective_delivery_mode: str = "",
) -> dict[str, Any]:
    body = exc.read().decode("utf-8") if exc.fp else ""
    try:
        parsed = json.loads(body) if body else {}
    except Exception:
        parsed = {"error": body} if body else {}

    result: dict[str, Any] = {
        "ok": False,
        "status_code": exc.code,
        "error_type": "HTTPError",
    }
    if session_id:
        result["session_id"] = str(session_id)
    if requested_delivery_mode:
        result["delivery_mode_requested"] = str(requested_delivery_mode)
    if effective_delivery_mode:
        result["delivery_mode_effective"] = str(effective_delivery_mode)

    if isinstance(parsed, dict):
        detail = parsed.get("detail")
        if isinstance(detail, dict):
            result["detail"] = dict(detail)
            for key, value in detail.items():
                if key in {"ok", "status_code"}:
                    continue
                result.setdefault(str(key), value)
        elif detail is not None:
            result["detail"] = detail

        for key in (
            "error",
            "reason",
            "hint",
            "wait_tool",
            "existing_session_id",
            "recommended_client_action",
            "next_action",
            "recoverable",
            "route",
            "status",
        ):
            if key in parsed and key not in result:
                result[key] = parsed[key]

    if not result.get("error"):
        detail_obj = result.get("detail")
        if isinstance(detail_obj, dict) and detail_obj.get("error"):
            result["error"] = str(detail_obj.get("error"))
        elif isinstance(detail_obj, str) and detail_obj.strip():
            result["error"] = detail_obj
        elif isinstance(parsed, dict) and parsed.get("error"):
            result["error"] = str(parsed.get("error"))
        elif body:
            result["error"] = body
        else:
            result["error"] = str(exc)
    return result


def _session_status(base: str, api_key: str, session_id: str, *, timeout: float = 30.0) -> dict[str, Any]:
    req = _build_request(
        url=f"{base}/v3/agent/session/{session_id}",
        method="GET",
        api_key=api_key,
    )
    with _open_with_recovery(req, timeout=timeout) as resp:
        return _read_json_response(resp)


def _wait_stream_terminal(*, base: str, api_key: str, session_id: str, stream_url: str, timeout_seconds: int) -> dict[str, Any] | None:
    req = urllib.request.Request(
        _normalize_stream_url(base=base, stream_url=stream_url, session_id=session_id),
        headers={
            "Accept": "text/event-stream",
            "User-Agent": "chatgptrest-agent-mcp/0.1.0",
            "X-Client-Name": _client_name(),
            "X-Client-Instance": _client_instance(),
            "X-Request-ID": _new_request_id(),
        },
        method="GET",
    )
    if api_key:
        req.add_header("X-Api-Key", api_key)

    event_type = ""
    data_lines: list[str] = []
    latest_session: dict[str, Any] | None = None
    with _open_with_recovery(req, timeout=max(30, int(timeout_seconds) + 15)) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                payload_raw = "\n".join(data_lines).strip()
                payload: dict[str, Any] = {}
                if payload_raw:
                    try:
                        payload = json.loads(payload_raw)
                    except Exception:
                        payload = {}
                if event_type == "snapshot" and isinstance(payload.get("session"), dict):
                    latest_session = dict(payload["session"])
                elif event_type == "done":
                    done_session = payload.get("session")
                    if isinstance(done_session, dict):
                        return dict(done_session)
                    return latest_session
                elif event_type == "error":
                    return latest_session
                event_type = ""
                data_lines = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_type = line.partition(":")[2].strip()
                continue
            if line.startswith("data:"):
                data_lines.append(line.partition(":")[2].lstrip())
        return latest_session


async def _agent_watch_runner(
    *,
    watch_id: str,
    session_id: str,
    base: str,
    api_key: str,
    stream_url: str,
    timeout_seconds: int,
    notify_done: bool,
) -> None:
    started_at = time.time()
    try:
        session = await asyncio.to_thread(
            _wait_stream_terminal,
            base=base,
            api_key=api_key,
            session_id=session_id,
            stream_url=stream_url,
            timeout_seconds=timeout_seconds,
        )
        deadline = started_at + max(30.0, float(timeout_seconds))
        while not isinstance(session, dict) or str(session.get("status") or "").strip().lower() not in _AGENT_TERMINAL_STATUSES:
            if time.time() >= deadline:
                break
            await asyncio.sleep(1.5)
            try:
                session = await asyncio.to_thread(_session_status, base, api_key, session_id, timeout=15.0)
            except Exception:
                session = session if isinstance(session, dict) else None
        terminal_status = str((session or {}).get("status") or "").strip().lower()
        watch_status = "completed" if terminal_status in _AGENT_TERMINAL_STATUSES else "error"
        async with _AGENT_WATCH_LOCK:
            state = _AGENT_WATCH_STATE.get(watch_id)
            if isinstance(state, dict):
                state["updated_at"] = time.time()
                state["ended_at"] = time.time()
                state["watch_status"] = watch_status
                state["last_status"] = terminal_status
                state["last_event_type"] = "done" if watch_status == "completed" else "timeout"
                if isinstance(session, dict):
                    state["result_session"] = dict(session)
                _persist_watch_state(state)
        if notify_done:
            _tmux_notify(f"[chatgptrest-agent] session done: {session_id} status={terminal_status or 'unknown'}")
    except asyncio.CancelledError:
        async with _AGENT_WATCH_LOCK:
            state = _AGENT_WATCH_STATE.get(watch_id)
            if isinstance(state, dict):
                state["updated_at"] = time.time()
                state["ended_at"] = time.time()
                state["watch_status"] = "canceled"
                state["last_event_type"] = "canceled"
                _persist_watch_state(state)
        if notify_done:
            _tmux_notify(f"[chatgptrest-agent] session watch canceled: {session_id}")
        raise
    except Exception as exc:
        async with _AGENT_WATCH_LOCK:
            state = _AGENT_WATCH_STATE.get(watch_id)
            if isinstance(state, dict):
                state["updated_at"] = time.time()
                state["ended_at"] = time.time()
                state["watch_status"] = "error"
                state["error"] = str(exc)
                state["error_type"] = type(exc).__name__
                state["last_event_type"] = "error"
                _persist_watch_state(state)
        if notify_done:
            _tmux_notify(f"[chatgptrest-agent] session watch error: {session_id} {type(exc).__name__}: {str(exc)[:160]}")


async def _ensure_agent_watch(
    *,
    session_id: str,
    base: str,
    api_key: str,
    stream_url: str,
    timeout_seconds: int,
    notify_done: bool,
    auto_resumed: bool,
) -> dict[str, Any]:
    now = time.time()
    async with _AGENT_WATCH_LOCK:
        _agent_watch_gc_locked(now=now)
        state = _restore_persisted_watch_state_locked(session_id)
        existing_watch_id = _AGENT_WATCH_BY_SESSION.get(session_id)
        task = _AGENT_WATCH_TASKS.get(existing_watch_id) if existing_watch_id else None
        if isinstance(state, dict) and isinstance(task, asyncio.Task) and not task.done():
            return {
                "ok": True,
                "already_running": True,
                **_watch_state_view(state),
            }
        if isinstance(state, dict) and not auto_resumed:
            prior_status = str(state.get("watch_status") or "").strip().lower()
            if prior_status and prior_status != "running":
                state = None
        if not isinstance(state, dict) and existing_watch_id:
            _AGENT_WATCH_STATE.pop(existing_watch_id, None)
            _AGENT_WATCH_TASKS.pop(existing_watch_id, None)

        if isinstance(state, dict):
            watch_id = str(state.get("watch_id") or "").strip()
            if not watch_id:
                state = None
            else:
                state["watch_status"] = "running"
                state["updated_at"] = now
                state["ended_at"] = None
                state["notify_done"] = bool(notify_done)
                state["stream_url"] = str(stream_url or state.get("stream_url") or "")
                state["timeout_seconds"] = int(timeout_seconds)
                state["error"] = ""
                state["error_type"] = ""
                state["last_event_type"] = "resumed" if auto_resumed else "started"

        if not isinstance(state, dict):
            global _AGENT_WATCH_SEQ
            _AGENT_WATCH_SEQ += 1
            watch_id = f"agent-watch-{int(now)}-{_AGENT_WATCH_SEQ:04d}-{session_id[-8:]}"
            state = {
                "watch_id": watch_id,
                "session_id": session_id,
                "watch_status": "running",
                "started_at": now,
                "updated_at": now,
                "ended_at": None,
                "notify_done": bool(notify_done),
                "stream_url": stream_url,
                "timeout_seconds": int(timeout_seconds),
                "last_status": "",
                "last_event_type": "resumed" if auto_resumed else "started",
            }
        else:
            _AGENT_WATCH_STATE.pop(existing_watch_id or "", None)
            _AGENT_WATCH_TASKS.pop(existing_watch_id or "", None)
            watch_id = str(state["watch_id"])

        _AGENT_WATCH_STATE[watch_id] = state
        _AGENT_WATCH_BY_SESSION[session_id] = watch_id
        _persist_watch_state(state)
        task = asyncio.create_task(
            _agent_watch_runner(
                watch_id=watch_id,
                session_id=session_id,
                base=base,
                api_key=api_key,
                stream_url=stream_url,
                timeout_seconds=timeout_seconds,
                notify_done=bool(notify_done),
            )
        )
        _AGENT_WATCH_TASKS[watch_id] = task
        task.add_done_callback(lambda _t, wid=watch_id: _AGENT_WATCH_TASKS.pop(wid, None))
        return {"ok": True, "already_running": False, "auto_resumed": bool(auto_resumed), **_watch_state_view(state)}


async def _start_agent_watch(
    *,
    session_id: str,
    base: str,
    api_key: str,
    stream_url: str,
    timeout_seconds: int,
    notify_done: bool,
) -> dict[str, Any]:
    return await _ensure_agent_watch(
        session_id=session_id,
        base=base,
        api_key=api_key,
        stream_url=stream_url,
        timeout_seconds=timeout_seconds,
        notify_done=notify_done,
        auto_resumed=False,
    )


def _watch_timeout_seconds(state: dict[str, Any] | None = None) -> int:
    if isinstance(state, dict):
        try:
            value = int(state.get("timeout_seconds") or 0)
            if value > 0:
                return value
        except Exception:
            pass
    return _DEFAULT_AGENT_WATCH_RESUME_TIMEOUT_SECONDS


async def _resume_agent_watch(
    *,
    session: dict[str, Any],
    base: str,
    api_key: str,
    state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    status = str((session or {}).get("status") or "").strip().lower()
    if not isinstance(session, dict) or status in _AGENT_TERMINAL_STATUSES:
        return None
    prior_watch_status = str((state or {}).get("watch_status") or "").strip().lower()
    if prior_watch_status and prior_watch_status != "running":
        return None
    session_id = str(session.get("session_id") or "").strip()
    if not session_id:
        return None
    stream_url = str(session.get("stream_url") or f"/v3/agent/session/{session_id}/stream")
    notify_done = bool(state.get("notify_done")) if isinstance(state, dict) else _agent_watch_notify_done_enabled()
    return await _ensure_agent_watch(
        session_id=session_id,
        base=base,
        api_key=api_key,
        stream_url=stream_url,
        timeout_seconds=_watch_timeout_seconds(state),
        notify_done=notify_done,
        auto_resumed=True,
    )


def _recover_turn_after_disconnect(*, base: str, api_key: str, session_id: str) -> dict[str, Any] | None:
    try:
        data = _session_status(base, api_key, session_id, timeout=10.0)
        if isinstance(data, dict) and data.get("ok"):
            data["transport_recovered"] = True
            data["session_id"] = str(data.get("session_id") or session_id)
            return data
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    return None


def _attach_watch_fields(data: dict[str, Any], state: dict[str, Any] | None) -> None:
    if not isinstance(data, dict) or not isinstance(state, dict):
        return
    view = _watch_state_view(state, include_result=False)
    data["watch_id"] = view.get("watch_id")
    data["watch_status"] = view.get("watch_status")
    data["background_watch"] = view


def _sync_watch_state_from_session_locked(*, state: dict[str, Any], session: dict[str, Any]) -> None:
    status = str((session or {}).get("status") or "").strip().lower()
    if not status:
        return
    state["last_status"] = status
    state["updated_at"] = time.time()
    if status in _AGENT_TERMINAL_STATUSES:
        state["watch_status"] = "completed"
        state["ended_at"] = time.time()
        state["last_event_type"] = "recovered_terminal"
        state["result_session"] = dict(session)
    _persist_watch_state(state)


def _session_terminal_status(status: str) -> bool:
    return str(status or "").strip().lower() in _AGENT_TERMINAL_STATUSES


def _progress_phase(session: dict[str, Any]) -> str:
    status = str(session.get("status") or "").strip().lower()
    if status in {"needs_followup", "needs_input"}:
        return "clarify_required"
    if _session_terminal_status(status):
        return status or "completed"
    watch_status = str(session.get("watch_status") or "").strip().lower()
    if watch_status == "running":
        return "background_running"
    delivery = dict(session.get("delivery") or {})
    artifacts = list(session.get("artifacts") or [])
    artifact_kinds = {str(item.get("kind") or "").strip() for item in artifacts if str(item.get("kind") or "").strip()}
    delivery_mode = str(session.get("delivery_mode_effective") or delivery.get("mode") or "").strip().lower()
    if "conversation_url" in artifact_kinds:
        return "conversation_ready"
    if delivery_mode == "deferred":
        return "background_running"
    return "running"


def _recommended_client_action(session: dict[str, Any]) -> str:
    status = str(session.get("status") or "").strip().lower()
    if status in {"needs_followup", "needs_input"}:
        return "patch_same_session"
    if status == "completed":
        return "followup"
    if status in {"failed", "cancelled", "canceled"}:
        return "retry_or_new_turn"
    if str(session.get("session_id") or "").strip():
        return "wait"
    return "poll_status"


def _enrich_public_session(
    session: dict[str, Any],
    *,
    requested_delivery_mode: str = "",
    effective_delivery_mode: str = "",
    auto_background_reason: str = "",
) -> dict[str, Any]:
    data = dict(session or {})
    delivery = dict(data.get("delivery") or {})
    requested = str(requested_delivery_mode or data.get("delivery_mode_requested") or "").strip().lower()
    effective = str(
        effective_delivery_mode
        or data.get("delivery_mode_effective")
        or delivery.get("mode")
        or ""
    ).strip().lower()
    if requested:
        data["delivery_mode_requested"] = requested
    if effective:
        data["delivery_mode_effective"] = effective
    if auto_background_reason:
        data["auto_background_reason"] = auto_background_reason
        data["why_sync_was_not_possible"] = auto_background_reason
    accepted_for_background = bool(data.get("accepted")) and requested == "sync" and effective == "deferred"
    if accepted_for_background:
        data["accepted_for_background"] = True
    data["recommended_client_action"] = _recommended_client_action(data)
    data["wait_supported"] = bool(str(data.get("session_id") or "").strip())
    if data["wait_supported"]:
        data["wait_tool"] = "advisor_agent_wait"
    artifacts = list(data.get("artifacts") or [])
    artifact_kinds = sorted(
        {str(item.get("kind") or "").strip() for item in artifacts if str(item.get("kind") or "").strip()}
    )
    status = str(data.get("status") or "").strip().lower()
    data["progress"] = {
        "phase": _progress_phase(data),
        "status": status,
        "route": str(data.get("route") or (data.get("provenance") or {}).get("route") or "").strip(),
        "terminal": _session_terminal_status(status),
        "background_mode": effective == "deferred",
        "artifact_kinds": artifact_kinds,
        "conversation_ready": "conversation_url" in artifact_kinds,
    }
    return data


@mcp.tool()
async def advisor_agent_turn(
    ctx: Context | None,
    message: str = "",
    session_id: str = "",
    goal_hint: str = "",
    depth: str = "standard",
    execution_profile: str = "",
    task_intake: dict[str, Any] | None = None,
    workspace_request: dict[str, Any] | None = None,
    contract_patch: dict[str, Any] | None = None,
    delivery_mode: str = "sync",
    attachments: list[str] | str | None = None,
    memory_capture: dict[str, Any] | None = None,
    role_id: str = "",
    user_id: str = "",
    trace_id: str = "",
    timeout_seconds: int = 300,
    auto_watch: bool = True,
    notify_done: bool = True,
) -> dict[str, Any]:
    """Execute a single advisor agent turn.

    This is the primary high-level entry point for agent interactions.
    The server handles routing, execution, and response formatting.

    Args:
        message: User's natural language message (optional when workspace_request is provided)
        session_id: Session ID for continuity (auto-created if empty)
        goal_hint: High-level goal hint (code_review, research, image, report, repair)
        depth: Execution depth (light, standard, deep, heavy)
        execution_profile: Optional high-level execution override (thinking_heavy, deep_research, report_grade)
        task_intake: Optional canonical task intake object (task-intake-v2)
        workspace_request: Optional northbound Google Workspace task object (workspace-request-v1)
        contract_patch: Optional patch object applied to prior session contract/task_intake
        delivery_mode: sync | deferred. deferred returns session_id/stream_url immediately.
        attachments: Optional file paths for repo/file review tasks
        memory_capture: Optional capture request dict forwarded to /v3/agent/turn
        role_id: Optional role binding
        user_id: Optional explicit user identity
        trace_id: Optional trace ID
        timeout_seconds: Execution timeout (default 300)
        auto_watch: For deferred/long turns, start background watcher automatically
        notify_done: If watcher is started, emit completion notification to controller pane

    Returns:
        {ok, session_id, run_id, status, answer, delivery, provenance, next_action, recovery_status, watch_id}
    """
    base = _base_url()
    api_key = _api_key()
    effective_session_id = str(session_id or "").strip() or f"agent_sess_{uuid.uuid4().hex[:16]}"
    requested_delivery_mode = str(delivery_mode or "").strip().lower() or "sync"
    effective_delivery_mode = requested_delivery_mode
    auto_background_reason = ""
    if _should_auto_background(goal_hint=goal_hint, delivery_mode=requested_delivery_mode):
        effective_delivery_mode = "deferred"
        if requested_delivery_mode == "sync":
            auto_background_reason = "long_goal_auto_background"

    payload = {
        "message": message,
        "session_id": effective_session_id,
        "goal_hint": goal_hint,
        "depth": depth,
        "delivery_mode": effective_delivery_mode,
        "timeout_seconds": timeout_seconds,
        "client": _public_agent_client_payload(ctx),
    }
    if execution_profile:
        payload["execution_profile"] = str(execution_profile)
    if isinstance(task_intake, dict) and task_intake:
        payload["task_intake"] = dict(task_intake)
    if isinstance(workspace_request, dict) and workspace_request:
        payload["workspace_request"] = dict(workspace_request)
    if isinstance(contract_patch, dict) and contract_patch:
        payload["contract_patch"] = dict(contract_patch)
    normalized_attachments = coerce_file_path_input(attachments)
    if normalized_attachments:
        payload["attachments"] = list(normalized_attachments)
    if isinstance(memory_capture, dict) and memory_capture:
        payload["memory_capture"] = dict(memory_capture)
    if role_id:
        payload["role_id"] = str(role_id)
    if user_id:
        payload["user_id"] = str(user_id)
    if trace_id:
        payload["trace_id"] = str(trace_id)

    req = _build_request(
        url=f"{base}/v3/agent/turn",
        method="POST",
        api_key=api_key,
        payload=payload,
    )

    try:
        with _open_with_recovery(req, timeout=timeout_seconds + 30) as resp:
            data = _read_json_response(resp)
            if isinstance(data, dict):
                data = _enrich_public_session(
                    data,
                    requested_delivery_mode=requested_delivery_mode,
                    effective_delivery_mode=effective_delivery_mode,
                    auto_background_reason=auto_background_reason,
                )
                if (
                    data.get("ok")
                    and bool(auto_watch)
                    and _agent_watch_enabled()
                    and effective_delivery_mode == "deferred"
                ):
                    sid = str(data.get("session_id") or effective_session_id)
                    stream_url = str(
                        data.get("stream_url")
                        or (data.get("delivery") or {}).get("stream_url")
                        or f"/v3/agent/session/{sid}/stream"
                    )
                    watch = await _start_agent_watch(
                        session_id=sid,
                        base=base,
                        api_key=api_key,
                        stream_url=stream_url,
                        timeout_seconds=timeout_seconds,
                        notify_done=bool(notify_done and _agent_watch_notify_done_enabled()),
                    )
                    if watch.get("ok"):
                        data["background_watch_started"] = True
                        data["watch_id"] = watch.get("watch_id")
                        data["watch_status"] = watch.get("watch_status")
                        data["watch_running"] = bool(watch.get("running"))
            return data
    except urllib.error.HTTPError as e:
        return _structured_http_error_result(
            e,
            session_id=effective_session_id,
            requested_delivery_mode=requested_delivery_mode,
            effective_delivery_mode=effective_delivery_mode,
        )
    except (http.client.RemoteDisconnected, urllib.error.URLError) as e:
        recovered = _recover_turn_after_disconnect(
            base=base,
            api_key=api_key,
            session_id=effective_session_id,
        )
        if recovered is not None:
            recovered = _enrich_public_session(
                recovered,
                requested_delivery_mode=requested_delivery_mode,
                effective_delivery_mode=effective_delivery_mode,
                auto_background_reason=auto_background_reason,
            )
            if (
                recovered.get("ok")
                and bool(auto_watch)
                and _agent_watch_enabled()
                and effective_delivery_mode == "deferred"
            ):
                watch = await _resume_agent_watch(
                    session=recovered,
                    base=base,
                    api_key=api_key,
                    state=None,
                )
                if isinstance(watch, dict) and watch.get("ok"):
                    recovered["background_watch_started"] = True
                    recovered["watch_id"] = watch.get("watch_id")
                    recovered["watch_status"] = watch.get("watch_status")
                    recovered["watch_running"] = bool(watch.get("running"))
                    if watch.get("auto_resumed"):
                        recovered["background_watch_resumed"] = True
            return recovered
        return {
            "ok": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "session_id": effective_session_id,
            "recoverable": True,
            "delivery_mode_requested": requested_delivery_mode,
            "delivery_mode_effective": effective_delivery_mode,
            "next_action": {
                "type": "check_status_or_retry",
                "safe_hint": "transport disconnected; check the same session_id before retrying",
                "session_id": effective_session_id,
            },
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "session_id": effective_session_id,
            "delivery_mode_requested": requested_delivery_mode,
            "delivery_mode_effective": effective_delivery_mode,
        }


@mcp.tool()
async def advisor_agent_cancel(
    ctx: Context | None,
    session_id: str,
) -> dict[str, Any]:
    """Cancel a running agent session.

    Args:
        session_id: Session ID to cancel

    Returns:
        {ok, session_id, status, message}
    """
    base = _base_url()
    api_key = _api_key()

    payload = {
        "session_id": session_id,
    }

    req = _build_request(
        url=f"{base}/v3/agent/cancel",
        method="POST",
        api_key=api_key,
        payload=payload,
    )

    try:
        with _open_with_recovery(req, timeout=30) as resp:
            data = _read_json_response(resp)
            async with _AGENT_WATCH_LOCK:
                wid = _AGENT_WATCH_BY_SESSION.pop(session_id, None)
                state = _restore_persisted_watch_state_locked(session_id)
                if wid:
                    task = _AGENT_WATCH_TASKS.get(wid)
                    if task and not task.done():
                        task.cancel()
                if not isinstance(state, dict) and wid:
                    state = _AGENT_WATCH_STATE.get(wid)
                if isinstance(state, dict):
                    state["watch_status"] = "canceled"
                    state["updated_at"] = time.time()
                    state["ended_at"] = time.time()
                    state["last_event_type"] = "canceled"
                    _persist_watch_state(state)
            return data
    except urllib.error.HTTPError as e:
        return _structured_http_error_result(e, session_id=session_id)
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


@mcp.tool()
async def advisor_agent_status(
    ctx: Context | None,
    session_id: str,
) -> dict[str, Any]:
    """Get status of an agent session.

    Args:
        session_id: Session ID to query

    Returns:
        {ok, session_id, run_id, status, last_message, last_answer, route, next_action}
    """
    base = _base_url()
    api_key = _api_key()

    req = _build_request(
        url=f"{base}/v3/agent/session/{session_id}",
        method="GET",
        api_key=api_key,
    )

    restored_state: dict[str, Any] | None = None
    async with _AGENT_WATCH_LOCK:
        _agent_watch_gc_locked()
        restored_state = _restore_persisted_watch_state_locked(session_id)

    try:
        with _open_with_recovery(req, timeout=30) as resp:
            data = _read_json_response(resp)
            resumed_watch: dict[str, Any] | None = None
            if isinstance(data, dict) and data.get("ok") and _agent_watch_enabled():
                resumed_watch = await _resume_agent_watch(
                    session=data,
                    base=base,
                    api_key=api_key,
                    state=restored_state,
                )
            async with _AGENT_WATCH_LOCK:
                _agent_watch_gc_locked()
                wid = _AGENT_WATCH_BY_SESSION.get(session_id)
                state = _AGENT_WATCH_STATE.get(wid) if wid else restored_state
                if isinstance(data, dict) and isinstance(state, dict):
                    _sync_watch_state_from_session_locked(state=state, session=data)
                if isinstance(data, dict) and isinstance(state, dict):
                    _attach_watch_fields(data, state)
                elif isinstance(data, dict) and isinstance(resumed_watch, dict):
                    data["watch_id"] = resumed_watch.get("watch_id")
                    data["watch_status"] = resumed_watch.get("watch_status")
                    data["background_watch"] = {
                        "watch_id": resumed_watch.get("watch_id"),
                        "session_id": session_id,
                        "watch_status": resumed_watch.get("watch_status"),
                        "running": bool(resumed_watch.get("running")),
                        "done": bool(resumed_watch.get("done")),
                    }
            if isinstance(data, dict) and isinstance(resumed_watch, dict) and resumed_watch.get("auto_resumed"):
                data["auto_resumed"] = True
            if isinstance(data, dict):
                data = _enrich_public_session(data)
            return data
    except urllib.error.HTTPError as e:
        async with _AGENT_WATCH_LOCK:
            _agent_watch_gc_locked()
            wid = _AGENT_WATCH_BY_SESSION.get(session_id)
            state = _AGENT_WATCH_STATE.get(wid) if wid else restored_state
            if e.code == 404 and isinstance(state, dict) and isinstance(state.get("result_session"), dict):
                recovered = dict(state["result_session"])
                _attach_watch_fields(recovered, state)
                recovered["transport_recovered"] = True
                return _enrich_public_session(recovered)
        return _structured_http_error_result(e, session_id=session_id)
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


@mcp.tool()
async def advisor_agent_wait(
    ctx: Context | None,
    session_id: str,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Wait for an agent session to reach a terminal status.

    Args:
        session_id: Session ID to wait on
        timeout_seconds: Maximum wait time in seconds

    Returns:
        Session payload with terminal answer/artifacts when ready, or timeout metadata otherwise
    """
    base = _base_url()
    api_key = _api_key()
    started_at = time.time()
    effective_timeout = max(0, int(timeout_seconds))

    restored_state: dict[str, Any] | None = None
    async with _AGENT_WATCH_LOCK:
        _agent_watch_gc_locked()
        restored_state = _restore_persisted_watch_state_locked(session_id)

    try:
        initial = await asyncio.to_thread(_session_status, base, api_key, session_id, timeout=30.0)
        if not isinstance(initial, dict):
            initial = {"ok": False, "error": "invalid_session_payload", "session_id": session_id}
        if _session_terminal_status(str(initial.get("status") or "")) or effective_timeout <= 0:
            result = _enrich_public_session(dict(initial))
            result["wait_status"] = "completed" if _session_terminal_status(str(result.get("status") or "")) else "noop"
            result["timed_out"] = False
            result["timeout_seconds"] = effective_timeout
            result["wait_elapsed_seconds"] = round(time.time() - started_at, 3)
            return result

        delivery = dict(initial.get("delivery") or {})
        stream_url = str(
            initial.get("stream_url")
            or delivery.get("stream_url")
            or f"/v3/agent/session/{session_id}/stream"
        ).strip()
        waited = await asyncio.to_thread(
            _wait_stream_terminal,
            base=base,
            api_key=api_key,
            session_id=session_id,
            stream_url=stream_url,
            timeout_seconds=effective_timeout,
        )
        latest = dict(waited) if isinstance(waited, dict) else {}
        refreshed: dict[str, Any] | None = None
        try:
            refreshed_candidate = await asyncio.to_thread(_session_status, base, api_key, session_id, timeout=15.0)
            if isinstance(refreshed_candidate, dict):
                refreshed = dict(refreshed_candidate)
        except Exception:
            refreshed = None
        if isinstance(refreshed, dict):
            latest_status = str(latest.get("status") or "")
            refreshed_status = str(refreshed.get("status") or "")
            if (
                not latest
                or _session_terminal_status(refreshed_status)
                or not _session_terminal_status(latest_status)
            ):
                latest = refreshed
        result = _enrich_public_session(dict(latest or initial))

        async with _AGENT_WATCH_LOCK:
            _agent_watch_gc_locked()
            wid = _AGENT_WATCH_BY_SESSION.get(session_id)
            state = _AGENT_WATCH_STATE.get(wid) if wid else restored_state
            if isinstance(state, dict):
                _sync_watch_state_from_session_locked(state=state, session=result)
                _attach_watch_fields(result, state)

        terminal = _session_terminal_status(str(result.get("status") or ""))
        result["wait_status"] = "completed" if terminal else "timeout"
        result["timed_out"] = not terminal
        result["timeout_seconds"] = effective_timeout
        result["wait_elapsed_seconds"] = round(time.time() - started_at, 3)
        return result
    except urllib.error.HTTPError as e:
        return _structured_http_error_result(e, session_id=session_id)
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool()
async def repo_bootstrap(
    ctx: Context | None,
    task_description: str = "",
    changed_files: list[str] | None = None,
    goal_hint: str = "",
    runtime_mode: str = "quick",
) -> dict[str, Any]:
    """Generate machine-first repo entry bootstrap packet for coding agents.

    Returns a bootstrap-v1 packet containing:
    - Repo identity (name, path, git HEAD/branch)
    - Detected planes (execution, public_agent, advisor, etc.)
    - Canonical docs relevant to the task
    - Runtime snapshot (quick or deep mode)
    - Task-relevant symbols from GitNexus
    - Task-relevant history hits
    - Change obligations (doc/test requirements)
    - Surface policy (what agents can/cannot use)
    - Danger zones (high-risk areas)
    - Closeout contract (what must be done before task completion)

    Args:
        task_description: Natural language task description
        changed_files: List of changed file paths
        goal_hint: Optional goal hint (e.g., "execution", "public_agent")
        runtime_mode: "quick" for basic checks, "deep" for full health_probe

    Returns:
        Bootstrap packet (bootstrap-v1 schema)
    """
    try:
        import sys
        sys.path.insert(0, str(_REPO_ROOT))
        from chatgptrest.repo_cognition.bootstrap import generate_bootstrap_packet

        packet = generate_bootstrap_packet(
            task_description=task_description,
            changed_files=changed_files,
            goal_hint=goal_hint,
            runtime_mode=runtime_mode if runtime_mode in ("quick", "deep") else "quick",
        )
        return {"ok": True, "packet": packet}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:500]}


@mcp.tool()
async def repo_doc_obligations(
    ctx: Context | None,
    changed_files: list[str] | None = None,
    diff_spec: str = "",
) -> dict[str, Any]:
    """Check doc/test obligations for changed files.

    Args:
        changed_files: List of changed file paths
        diff_spec: Git diff spec (e.g., "HEAD~1..HEAD", "origin/master..HEAD")

    Returns:
        {
            "ok": bool,
            "obligations": [...],
            "validation": {"ok": bool, "missing_docs": [...], "missing_tests": [...]},
            "changed_files": [...]
        }
    """
    try:
        import sys
        import subprocess
        sys.path.insert(0, str(_REPO_ROOT))
        from chatgptrest.repo_cognition.obligations import (
            compute_change_obligations,
            validate_obligations,
        )

        # Get changed files
        if diff_spec:
            proc = subprocess.run(
                ["git", "diff", "--name-only", diff_spec],
                capture_output=True,
                text=True,
                cwd=_REPO_ROOT,
                check=False,
            )
            if proc.returncode == 0:
                changed_files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            else:
                return {"ok": False, "error": f"git diff failed: {proc.stderr[:200]}"}

        if not changed_files:
            return {"ok": True, "obligations": [], "note": "No changed files"}

        # Compute obligations
        obligations = compute_change_obligations(changed_files)

        if not obligations:
            return {"ok": True, "obligations": [], "note": "No obligations"}

        # Validate obligations
        validation = validate_obligations(obligations)

        return {
            "ok": validation["ok"],
            "obligations": obligations,
            "validation": validation,
            "changed_files": changed_files,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:500]}


def main():
    import sys
    port = int(os.environ.get("CHATGPTREST_AGENT_MCP_PORT", "18714"))
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", port=port)


if __name__ == "__main__":
    main()
