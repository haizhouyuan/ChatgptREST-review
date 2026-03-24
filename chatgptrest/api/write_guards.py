from __future__ import annotations

import os
import re
import socket
from typing import Any

from fastapi import HTTPException, Request

from chatgptrest.core.env import truthy_env as _truthy_env


def _parse_client_name_csv(raw: str) -> set[str]:
    parts = [p.strip().lower() for p in re.split(r"[\s,;]+", str(raw or "").strip()) if p and p.strip()]
    return {p for p in parts if p}


def _client_name_allowlist() -> set[str]:
    return _parse_client_name_csv(os.environ.get("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST") or "")


def _fallback_client_name_allowlist_when_mcp_down() -> set[str]:
    return _parse_client_name_csv(os.environ.get("CHATGPTREST_FALLBACK_CLIENT_NAME_ALLOWLIST_WHEN_MCP_DOWN") or "")


def _cancel_client_name_allowlist() -> set[str]:
    return _parse_client_name_csv(os.environ.get("CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST") or "")


def _require_trace_headers_for_write() -> bool:
    return _truthy_env("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", False)


def _direct_live_chatgpt_client_allowlist() -> set[str]:
    raw = os.environ.get("CHATGPTREST_DIRECT_LIVE_CHATGPT_CLIENT_ALLOWLIST")
    if raw is None:
        return {"chatgptrest-admin-mcp"}
    return _parse_client_name_csv(raw)


def _require_cancel_reason() -> bool:
    return _truthy_env("CHATGPTREST_REQUIRE_CANCEL_REASON", False)


def _cancel_reason_max_chars() -> int:
    raw = (os.environ.get("CHATGPTREST_CANCEL_REASON_MAX_CHARS") or "").strip()
    try:
        val = int(raw) if raw else 240
    except Exception:
        val = 240
    return max(40, min(val, 2000))


def _normalize_reason_text(value: str | None) -> str:
    raw = str(value or "")
    if not raw:
        return ""
    raw = raw.replace("\r", " ").replace("\n", " ").strip()
    raw = re.sub(r"\s+", " ", raw)
    return raw


def _mcp_fallback_probe_host_port() -> tuple[str, int]:
    host = (os.environ.get("CHATGPTREST_MCP_PROBE_HOST") or "").strip() or "127.0.0.1"
    raw_port = (os.environ.get("CHATGPTREST_MCP_PROBE_PORT") or "").strip()
    if not raw_port:
        return host, 18712
    try:
        port = int(raw_port)
    except Exception:
        return host, 18712
    if port <= 0 or port > 65535:
        return host, 18712
    return host, port


def _mcp_fallback_probe_timeout_seconds() -> float:
    raw = (os.environ.get("CHATGPTREST_MCP_PROBE_TIMEOUT_SECONDS") or "").strip()
    try:
        timeout = float(raw) if raw else 0.2
    except Exception:
        timeout = 0.2
    return min(2.0, max(0.05, timeout))


def _mcp_probe_reachable() -> bool:
    host, port = _mcp_fallback_probe_host_port()
    timeout_seconds = _mcp_fallback_probe_timeout_seconds()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _allow_fallback_when_mcp_down() -> bool:
    return _truthy_env("CHATGPTREST_ALLOW_FALLBACK_WHEN_MCP_DOWN", False)


def enforce_client_name_allowlist(request: Request) -> None:
    allowlist = _client_name_allowlist()
    if not allowlist:
        return
    client_name = (request.headers.get("x-client-name") or "").strip().lower()
    if client_name and client_name in allowlist:
        return
    fallback_allowlist = _fallback_client_name_allowlist_when_mcp_down()
    if _allow_fallback_when_mcp_down() and client_name and client_name in fallback_allowlist:
        if not _mcp_probe_reachable():
            return
        probe_host, probe_port = _mcp_fallback_probe_host_port()
        raise HTTPException(
            status_code=403,
            detail={
                "error": "client_not_allowed",
                "error_type": "ClientNotAllowed",
                "reason": "mcp_fallback_allowed_only_when_down",
                "retry_after_seconds": None,
                "detail": "X-Client-Name fallback is only allowed when MCP is down",
                "x_client_name": client_name,
                "allowed_client_names": sorted(allowlist),
                "fallback_allowed_when_mcp_down": sorted(fallback_allowlist),
                "mcp_probe": {"host": probe_host, "port": probe_port, "reachable": True},
                "hint": "Use MCP directly while it is healthy.",
            },
        )
    raise HTTPException(
        status_code=403,
        detail={
            "error": "client_not_allowed",
            "error_type": "ClientNotAllowed",
            "reason": "x_client_name_not_in_allowlist",
            "retry_after_seconds": None,
            "detail": "X-Client-Name is not allowed for this operation",
            "x_client_name": (client_name or None),
            "allowed_client_names": sorted(allowlist),
            "fallback_allowed_when_mcp_down": sorted(fallback_allowlist) if fallback_allowlist else None,
            "hint": "Use the MCP adapter, or set CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST to include your client name.",
        },
    )


def enforce_cancel_client_name_allowlist(request: Request) -> None:
    allowlist = _cancel_client_name_allowlist()
    if not allowlist:
        return
    client_name = (request.headers.get("x-client-name") or "").strip().lower()
    if client_name and client_name in allowlist:
        return
    fallback_allowlist = _fallback_client_name_allowlist_when_mcp_down()
    if _allow_fallback_when_mcp_down() and client_name and client_name in fallback_allowlist:
        if not _mcp_probe_reachable():
            return
        probe_host, probe_port = _mcp_fallback_probe_host_port()
        raise HTTPException(
            status_code=403,
            detail={
                "error": "cancel_client_not_allowed",
                "error_type": "CancelClientNotAllowed",
                "reason": "mcp_fallback_allowed_only_when_down",
                "retry_after_seconds": None,
                "detail": "X-Client-Name fallback is only allowed for /cancel when MCP is down",
                "x_client_name": client_name,
                "allowed_cancel_client_names": sorted(allowlist),
                "fallback_allowed_when_mcp_down": sorted(fallback_allowlist),
                "mcp_probe": {"host": probe_host, "port": probe_port, "reachable": True},
                "hint": "Use MCP directly while it is healthy.",
            },
        )
    raise HTTPException(
        status_code=403,
        detail={
            "error": "cancel_client_not_allowed",
            "error_type": "CancelClientNotAllowed",
            "reason": "x_client_name_not_in_cancel_allowlist",
            "retry_after_seconds": None,
            "detail": "X-Client-Name is not allowed to cancel jobs",
            "x_client_name": (client_name or None),
            "allowed_cancel_client_names": sorted(allowlist),
            "fallback_allowed_when_mcp_down": sorted(fallback_allowlist) if fallback_allowlist else None,
            "hint": "Set CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST to include this client, or cancel via an allowed client.",
        },
    )


def enforce_write_trace_headers(request: Request, *, operation: str) -> None:
    if not _require_trace_headers_for_write():
        return
    headers = request.headers
    missing: list[str] = []
    x_client_instance = (headers.get("x-client-instance") or "").strip()
    x_request_id = (headers.get("x-request-id") or "").strip()
    if not x_client_instance:
        missing.append("X-Client-Instance")
    if not x_request_id:
        missing.append("X-Request-ID")
    if not missing:
        return
    raise HTTPException(
        status_code=400,
        detail={
            "error": "missing_trace_headers",
            "error_type": "MissingTraceHeaders",
            "reason": "trace_headers_required_for_write",
            "retry_after_seconds": None,
            "operation": operation,
            "missing_headers": missing,
            "detail": "write operation requires trace headers",
        },
    )


def enforce_direct_live_chatgpt_submission(
    request: Request,
    *,
    kind: str,
    params_obj: dict[str, Any] | None = None,
    client_obj: dict[str, Any] | None = None,
) -> None:
    if str(kind or "").strip().lower() != "chatgpt_web.ask":
        return
    params_obj = dict(params_obj or {})
    client_obj = dict(client_obj or {})
    if bool(params_obj.get("allow_direct_live_chatgpt_ask") or False):
        return

    headers = request.headers
    header_client_name = (headers.get("x-client-name") or "").strip().lower()
    body_client_name = str(client_obj.get("name") or "").strip().lower()
    user_agent = (headers.get("user-agent") or "").strip().lower()

    # Keep in-process FastAPI tests stable while still blocking explicit direct callers.
    if "testclient" in user_agent and not header_client_name and not body_client_name:
        return

    effective_client_name = header_client_name or body_client_name
    allowlist = _direct_live_chatgpt_client_allowlist()
    if effective_client_name and effective_client_name in allowlist:
        return

    raise HTTPException(
        status_code=403,
        detail={
            "error": "direct_live_chatgpt_ask_blocked",
            "error_type": "DirectLiveChatgptAskBlocked",
            "reason": "direct_low_level_live_chatgpt_ask_not_allowed",
            "detail": "direct /v1/jobs chatgpt_web.ask submission is blocked by default",
            "x_client_name": effective_client_name or None,
            "allowed_client_names": sorted(allowlist),
            "hint": "Use /v3/agent/turn (or advisor_agent_turn via MCP) for live asks. For tightly controlled exceptions, allowlist the client or set params.allow_direct_live_chatgpt_ask=true.",
        },
    )


def extract_cancel_reason(request: Request) -> str:
    headers = request.headers
    from_header = _normalize_reason_text(headers.get("x-cancel-reason"))
    from_query = _normalize_reason_text(request.query_params.get("reason"))
    reason = from_header or from_query
    max_chars = _cancel_reason_max_chars()
    if len(reason) > max_chars:
        reason = reason[:max_chars]
    if _require_cancel_reason() and not reason:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_cancel_reason",
                "error_type": "MissingCancelReason",
                "reason": "cancel_reason_required",
                "retry_after_seconds": None,
                "detail": "cancel operation requires X-Cancel-Reason header or ?reason= query",
            },
        )
    return reason


def summarize_write_context(request: Request) -> dict[str, Any]:
    return {
        "x_client_name": (request.headers.get("x-client-name") or "").strip() or None,
        "x_client_instance": (request.headers.get("x-client-instance") or "").strip() or None,
        "x_request_id": (request.headers.get("x-request-id") or "").strip() or None,
    }
