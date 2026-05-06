"""Public Agent MCP Server - lightweight northbound MCP transport.

Canonical public surface:
- automation_*: explicit automation-kernel-v1 contract backed by /v1/jobs

Public MCP no longer exposes advisor/coding compatibility lanes. Task
understanding belongs in Hermes or other front clients; this transport only
provides the shared automation kernel plus a few operational helpers.
"""

from __future__ import annotations

import asyncio
import hashlib
import http.client
import json
import os
import re
import socket
import sqlite3
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
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from chatgptrest.core.client_request_auth import build_registered_client_hmac_headers
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
from chatgptrest.mcp._answer_cache import normalize_answer_payload as _normalize_answer_payload

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


def _openmind_api_key() -> str:
    return os.environ.get("OPENMIND_API_KEY", os.environ.get("CHATGPTREST_API_TOKEN", "")).strip()


def _jobs_bearer_token() -> str:
    return os.environ.get("CHATGPTREST_API_TOKEN", os.environ.get("CHATGPTREST_OPS_TOKEN", "")).strip()


def _api_key() -> str:
    return _openmind_api_key()


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


def _public_mcp_health_payload() -> dict[str, Any]:
    auth_state = public_agent_mcp_auth_state()
    jobs_bearer_present = bool(_jobs_bearer_token())
    return {
        "ok": bool(auth_state.get("ok")),
        "service": "chatgptrest-agent-mcp",
        "surface": "automation-kernel-v1",
        "primary_surfaces": ["automation-kernel-v1"],
        "compatibility_surfaces": [],
        "base_url": _base_url(),
        "degraded_mode": not jobs_bearer_present,
        "auth": {
            "public_agent_auth_source": str(auth_state.get("source") or ""),
            "public_agent_key_present": bool(_openmind_api_key()),
            "jobs_bearer_present": jobs_bearer_present,
            "primary_path_ready": jobs_bearer_present,
            "degraded_fallback_allowed": True,
            "allowlist_enforced": bool(auth_state.get("allowlist_enforced")),
            "allowlisted": bool(auth_state.get("allowlisted", True)),
            "client_name": str(auth_state.get("client_name") or ""),
        },
    }


def _job_kernel_module():
    from chatgptrest.mcp import server as job_kernel

    return job_kernel


_CHATGPT_CONVERSATION_URL_RE = re.compile(
    r"^https?://(?:chatgpt\.com|chat\.openai\.com)/c/([A-Za-z0-9_-]{8,})(?:[/?#].*)?$",
    re.IGNORECASE,
)


def _normalize_chatgpt_conversation_url(value: str) -> tuple[str, str]:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("conversation_url is required")
    match = _CHATGPT_CONVERSATION_URL_RE.match(raw)
    if not match:
        raise ValueError("conversation_url must look like https://chatgpt.com/c/<conversation_id>")
    conversation_id = str(match.group(1) or "").strip()
    if not conversation_id:
        raise ValueError("conversation_url is missing a conversation id")
    return f"https://chatgpt.com/c/{conversation_id}", conversation_id


def _manual_conversation_fetch_idempotency_key(
    *,
    conversation_url: str,
    bucket_seconds: int,
) -> str:
    safe_bucket = max(60, min(int(bucket_seconds or 300), 24 * 60 * 60))
    bucket = int(time.time() // safe_bucket)
    digest = hashlib.sha256(str(conversation_url).encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"manual-chatgpt-conversation-export-{digest}-{bucket}"


def _manual_conversation_job_db_path() -> Path:
    raw = str(os.environ.get("CHATGPTREST_DB_PATH") or "").strip()
    if raw:
        path = Path(raw).expanduser()
        return path if path.is_absolute() else (_REPO_ROOT / path)
    return _REPO_ROOT / "state" / "jobdb.sqlite3"


def _manual_conversation_find_jobs(
    *,
    conversation_url: str,
    conversation_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    db_path = _manual_conversation_job_db_path()
    if not db_path.exists():
        return []
    safe_limit = max(1, min(int(limit or 20), 100))
    like_token = f"%{conversation_id}%"
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
              job_id, kind, status, phase, created_at, updated_at,
              conversation_url, conversation_id, answer_path, answer_chars,
              conversation_export_path, conversation_export_chars,
              last_error_type, last_error, input_json
            FROM jobs
            WHERE
              conversation_id = ?
              OR conversation_url = ?
              OR conversation_url LIKE ?
              OR input_json LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (conversation_id, conversation_url, like_token, like_token, safe_limit),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = {key: row[key] for key in row.keys() if key != "input_json"}
        item["has_answer"] = bool(item.get("answer_path"))
        item["has_conversation_export"] = bool(item.get("conversation_export_path"))
        try:
            input_obj = json.loads(str(row["input_json"] or "{}"))
            if isinstance(input_obj, dict):
                item["input_conversation_url"] = str(input_obj.get("conversation_url") or "").strip() or None
        except Exception:
            item["input_conversation_url"] = None
        out.append(item)
    return out


@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def public_agent_mcp_health(_request: Request) -> Response:
    return JSONResponse(_public_mcp_health_payload())

_LONG_RUNNING_GOAL_HINTS = {
    "consult",
    "dual_review",
    "gemini_deep_research",
    "gemini_research",
    "report",
    "research",
    "write_report",
}
_CODING_AGENT_ALLOWED_EXECUTION_PROFILES = {
    "",
    "thinking_heavy",
    "deep_research",
    "report_grade",
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




@mcp.tool()
async def automation_ask(
    ctx: Context | None,
    idempotency_key: str,
    question: str,
    provider: str = "chatgpt",
    preset: str = "auto",
    requested_execution_lane: str = "",
    premium_allowed: bool | None = None,
    task_object_contract: dict[str, Any] | None = None,
    parent_job_id: str = "",
    conversation_url: str = "",
    file_paths: list[str] | str | None = None,
    deep_research: bool | None = None,
    auto_context: bool = False,
    auto_context_top_k: int = 3,
    timeout_seconds: int = 600,
    max_wait_seconds: int = 1800,
    min_chars: int | None = None,
    preflight: dict[str, Any] | None = None,
    provider_selection: dict[str, Any] | None = None,
    client_context: dict[str, Any] | None = None,
    delivery_preference: str = "push_only",
    auto_wait: bool = True,
    notify_done: bool = True,
) -> dict[str, Any]:
    """Submit an explicit automation ask via automation-kernel-v1.

    This is the preferred shared backend surface for Hermes / Codex /
    Claude Code / Antigravity when they need ChatGPT/Gemini web automation
    without going through advisor/task-intake routing.
    """
    mod = _job_kernel_module()
    result = await mod.chatgptrest_ask(
        idempotency_key=idempotency_key,
        question=question,
        provider=provider,
        preset=preset,
        requested_execution_lane=str(requested_execution_lane or ""),
        premium_allowed=premium_allowed if isinstance(premium_allowed, bool) else None,
        task_object_contract=(dict(task_object_contract) if isinstance(task_object_contract, dict) else None),
        parent_job_id=(str(parent_job_id).strip() or None),
        conversation_url=(str(conversation_url).strip() or None),
        file_paths=file_paths,
        deep_research=deep_research,
        auto_context=bool(auto_context),
        auto_context_top_k=int(auto_context_top_k),
        timeout_seconds=int(timeout_seconds),
        max_wait_seconds=int(max_wait_seconds),
        min_chars=min_chars,
        preflight=(dict(preflight) if isinstance(preflight, dict) else None),
        provider_selection=(dict(provider_selection) if isinstance(provider_selection, dict) else None),
        client_context=(dict(client_context) if isinstance(client_context, dict) else None),
        delivery_preference=str(delivery_preference or "push_only"),
        auto_wait=bool(auto_wait),
        notify_done=bool(notify_done),
        ctx=ctx,
    )
    projected = dict(result or {})
    jid = str(projected.get("job_id") or "").strip()
    if jid and str(projected.get("completion_mode") or "").strip().lower() == "push":
        next_action_channel = str(projected.get("notify_channel") or "controller").strip() or "controller"
        projected["next_action"] = {
            "kind": "await_push",
            "channel": next_action_channel,
            "job_id": jid,
            "watch_id": str(projected.get("watch_id") or ""),
            "fallback_tools": ["automation_job_events", "automation_result"],
        }
        projected.setdefault("front_action", "return_now")
        projected.setdefault("action_hint", "await_push")
    return projected


@mcp.tool()
async def automation_result(
    ctx: Context | None,
    job_id: str,
    include_answer: bool = True,
    max_answer_chars: int = 24000,
    answer_offset: int = 0,
) -> dict[str, Any]:
    """Fetch automation job status + answer in one call."""
    mod = _job_kernel_module()
    return await mod.chatgptrest_result(
        job_id=job_id,
        include_answer=bool(include_answer),
        max_answer_chars=int(max_answer_chars),
        answer_offset=int(answer_offset),
        ctx=ctx,
    )


@mcp.tool()
async def automation_job_create(
    ctx: Context | None,
    idempotency_key: str,
    kind: str,
    input: dict[str, Any] | None = None,  # noqa: A002
    params: dict[str, Any] | None = None,
    client: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a raw automation job against /v1/jobs.

    Use this for explicit job-kernel access when the caller already knows the
    exact kind and params it wants.
    """
    mod = _job_kernel_module()
    return await mod.chatgptrest_job_create(
        idempotency_key=str(idempotency_key),
        kind=str(kind or "").strip(),
        input=dict(input or {}),
        params=dict(params or {}),
        client=(dict(client) if isinstance(client, dict) else None),
        ctx=ctx,
    )


@mcp.tool()
async def automation_job_status(
    ctx: Context | None,
    job_id: str,
) -> dict[str, Any]:
    """Get automation job status."""
    mod = _job_kernel_module()
    return await mod.chatgptrest_job_get(job_id=str(job_id).strip(), ctx=ctx)


@mcp.tool()
async def automation_job_wait(
    ctx: Context | None,
    job_id: str,
    timeout_seconds: int = 90,
    poll_seconds: float = 1.0,
) -> dict[str, Any]:
    """Foreground wait on an automation job."""
    mod = _job_kernel_module()
    return await mod.chatgptrest_job_wait(
        job_id=job_id,
        timeout_seconds=int(timeout_seconds),
        poll_seconds=float(poll_seconds),
        ctx=ctx,
    )


@mcp.tool()
async def automation_job_answer(
    ctx: Context | None,
    job_id: str,
    offset: int = 0,
    max_chars: int = 24000,
) -> dict[str, Any]:
    """Fetch answer chunk for an automation job."""
    mod = _job_kernel_module()
    return await mod.chatgptrest_answer_get(
        job_id=job_id,
        offset=int(offset),
        max_chars=int(max_chars),
        ctx=ctx,
    )


@mcp.tool()
async def automation_job_cancel(
    ctx: Context | None,
    job_id: str,
    reason: str = "",
) -> dict[str, Any]:
    """Cancel an automation job."""
    state = public_agent_mcp_auth_state()
    if state.get("token_present") and not state.get("cancel_allowlisted"):
        return {
            "ok": False,
            "job_id": str(job_id),
            "error_type": "CancelClientNotAllowed",
            "error": "public_agent_mcp_service_identity_not_cancel_allowlisted",
            "client_name": state.get("client_name"),
            "cancel_allowlist_enforced": bool(state.get("cancel_allowlist_enforced")),
            "cancel_allowlist": list(state.get("cancel_allowlist") or []),
            "recommended_action": (
                "Add the running public MCP client identity to "
                "CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST before using automation_job_cancel."
            ),
        }
    mod = _job_kernel_module()
    return await mod.chatgptrest_job_cancel(job_id=job_id, ctx=ctx, reason=reason)


@mcp.tool()
async def automation_job_events(
    ctx: Context | None,
    job_id: str,
    after_id: int = 0,
    limit: int = 200,
) -> dict[str, Any]:
    """Fetch event stream for an automation job."""
    mod = _job_kernel_module()
    return await mod.chatgptrest_job_events(
        job_id=job_id,
        after_id=int(after_id),
        limit=int(limit),
        ctx=ctx,
    )


@mcp.tool()
async def automation_conversation_fetch(
    ctx: Context | None,
    conversation_url: str,
    idempotency_key: str = "",
    timeout_seconds: int = 120,
    backend_mode: str = "dom_only",
    auto_wait: bool = True,
    notify_done: bool = True,
    idempotency_bucket_seconds: int = 300,
) -> dict[str, Any]:
    """Create a read-only export job for an existing ChatGPT conversation URL.

    This is the agent-facing URL recovery path for human-created ChatGPT Web
    conversations. It does not send a prompt. The worker renders the full
    exported conversation as the job answer; use automation_result(job_id) for
    markdown, or automation_conversation_get(job_id) for raw export chunks.
    """
    normalized_url, conversation_id = _normalize_chatgpt_conversation_url(conversation_url)
    mode = str(backend_mode or "dom_only").strip().lower()
    if mode not in {"dom_only", "auto"}:
        mode = "dom_only"
    key = str(idempotency_key or "").strip()
    if not key:
        key = _manual_conversation_fetch_idempotency_key(
            conversation_url=normalized_url,
            bucket_seconds=int(idempotency_bucket_seconds),
        )

    mod = _job_kernel_module()
    job = await mod.chatgptrest_job_create(
        idempotency_key=key,
        kind="chatgpt_web.conversation_export",
        input={"conversation_url": normalized_url},
        params={
            "timeout_seconds": int(timeout_seconds),
            "allow_dom_fallback": True,
            "backend_mode": mode,
            "manual_harvest": True,
            "read_only_harvest": True,
            "answer_format": "markdown",
        },
        client={
            "name": "chatgptrest_manual_conversation_fetch",
            "source": "automation_conversation_fetch",
            "conversation_id": conversation_id,
            "conversation_url": normalized_url,
        },
        ctx=ctx,
    )
    projected = dict(job or {})
    jid = str(projected.get("job_id") or "").strip()
    background_wait: dict[str, Any] | None = None
    if jid and bool(auto_wait):
        try:
            background_wait = await mod.chatgptrest_job_wait_background_start(
                job_id=jid,
                timeout_seconds=max(180, int(timeout_seconds) + 300),
                poll_seconds=1.0,
                notify_controller=False,
                notify_done=bool(notify_done),
                auto_repair_check=False,
                auto_codex_autofix=False,
                ctx=ctx,
            )
        except Exception as exc:
            background_wait = {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
            }

    projected.update(
        {
            "ok": bool(projected.get("ok", True)),
            "conversation_url": normalized_url,
            "conversation_id": conversation_id,
            "idempotency_key": key,
            "backend_mode": mode,
            "read_only_harvest": True,
            "background_wait": background_wait,
            "front_action": "return_now",
            "action_hint": "await_export",
            "next_action": {
                "kind": "poll_or_await_push",
                "job_id": jid,
                "fallback_tools": [
                    "automation_result",
                    "automation_conversation_get",
                    "automation_conversation_find",
                    "automation_job_events",
                ],
            },
        }
    )
    return projected


@mcp.tool()
async def automation_conversation_get(
    ctx: Context | None,
    job_id: str,
    offset: int = 0,
    max_chars: int = 24000,
) -> dict[str, Any]:
    """Fetch raw conversation export chunks for a ChatGPT conversation export job."""
    mod = _job_kernel_module()
    return await mod.chatgptrest_conversation_get(
        job_id=str(job_id).strip(),
        offset=int(offset),
        max_chars=int(max_chars),
        ctx=ctx,
    )


@mcp.tool()
async def automation_conversation_find(
    ctx: Context | None,
    conversation_url: str = "",
    conversation_id: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """Find local jobs already associated with a ChatGPT conversation URL or id."""
    del ctx
    cid = str(conversation_id or "").strip()
    normalized_url = ""
    if str(conversation_url or "").strip():
        normalized_url, cid = _normalize_chatgpt_conversation_url(conversation_url)
    elif not cid:
        raise ValueError("conversation_url or conversation_id is required")
    elif not re.fullmatch(r"[A-Za-z0-9_-]{8,}", cid):
        raise ValueError("conversation_id must be a ChatGPT conversation id token")
    if not normalized_url:
        normalized_url = f"https://chatgpt.com/c/{cid}"
    matches = _manual_conversation_find_jobs(
        conversation_url=normalized_url,
        conversation_id=cid,
        limit=int(limit),
    )
    return {
        "ok": True,
        "conversation_url": normalized_url,
        "conversation_id": cid,
        "count": len(matches),
        "matches": matches,
        "next_action": {
            "kind": "fetch_if_missing",
            "tool": "automation_conversation_fetch",
            "conversation_url": normalized_url,
        },
    }


@mcp.tool()
async def automation_gemini_generate_image_submit(
    ctx: Context | None,
    idempotency_key: str,
    prompt: str,
    timeout_seconds: int = 600,
    conversation_url: str = "",
    file_paths: list[str] | None = None,
    notify_done: bool = True,
) -> dict[str, Any]:
    """Submit Gemini image generation through the shared automation kernel."""
    mod = _job_kernel_module()
    return await mod.chatgptrest_gemini_generate_image_submit(
        idempotency_key=idempotency_key,
        prompt=prompt,
        timeout_seconds=int(timeout_seconds),
        conversation_url=(str(conversation_url).strip() or None),
        file_paths=file_paths,
        notify_controller=False,
        notify_done=bool(notify_done),
        ctx=ctx,
    )


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


for _noncanonical_public_tool_name in (
    "automation_job_wait",
    "repo_bootstrap",
    "repo_doc_obligations",
):
    try:
        mcp.remove_tool(_noncanonical_public_tool_name)
    except Exception:
        pass


def main():
    import sys
    port = int(os.environ.get("CHATGPTREST_AGENT_MCP_PORT", "18714"))
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", port=port)


if __name__ == "__main__":
    main()
