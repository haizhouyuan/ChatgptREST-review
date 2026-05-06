from __future__ import annotations

import ipaddress
import os
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

from chatgptrest.integrations.mcp_http_client import McpHttpClient, McpHttpError


class OpenClawAdapterError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = str(stage)


@dataclass(frozen=True)
class OpenClawSessionTrace:
    session_key: str
    spawn: dict[str, Any]
    send: dict[str, Any] | None
    status: dict[str, Any] | None


def _env_first(*names: str) -> str:
    for name in names:
        value = str(os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _allow_remote_openclaw_mcp_url() -> bool:
    raw = _env_first(
        "CHATGPTREST_OPENCLAW_ALLOW_REMOTE_MCP_URL",
        "CHATGPTREST_OPENCLOW_ALLOW_REMOTE_MCP_URL",
    ).lower()
    return raw in {"1", "true", "yes", "on"}


def _is_loopback_http_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(str(url or "").strip())
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").strip()
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def openclaw_mcp_url_from_params(params: dict[str, Any]) -> str | None:
    raw = str(
        (params or {}).get("openclaw_mcp_url")
        or _env_first("CHATGPTREST_OPENCLAW_MCP_URL", "CHATGPTREST_OPENCLOW_MCP_URL")
        or ""
    ).strip()
    if not raw:
        return None
    if _allow_remote_openclaw_mcp_url() or _is_loopback_http_url(raw):
        return raw
    raise ValueError(
        "openclaw_mcp_url must target a loopback http(s) endpoint unless "
        "CHATGPTREST_OPENCLAW_ALLOW_REMOTE_MCP_URL=1 "
        "(legacy alias CHATGPTREST_OPENCLOW_ALLOW_REMOTE_MCP_URL is also accepted)"
    )


class OpenClawAdapter:
    def __init__(self, *, url: str, client_name: str = "chatgptrest-advisor", client_version: str = "v2") -> None:
        self._url = str(url).strip()
        if not self._url:
            raise OpenClawAdapterError("initialize", "openclaw mcp url is empty")
        self._client = McpHttpClient(url=self._url, client_name=client_name, client_version=client_version)

    @property
    def url(self) -> str:
        return self._url

    def sessions_spawn(self, *, tool_args: dict[str, Any], timeout_sec: float = 60.0) -> dict[str, Any]:
        try:
            return self._client.call_tool(tool_name="sessions_spawn", tool_args=dict(tool_args or {}), timeout_sec=timeout_sec)
        except (McpHttpError, Exception) as exc:
            raise OpenClawAdapterError("sessions_spawn", str(exc)) from exc

    def sessions_send(self, *, tool_args: dict[str, Any], timeout_sec: float = 60.0) -> dict[str, Any]:
        try:
            return self._client.call_tool(tool_name="sessions_send", tool_args=dict(tool_args or {}), timeout_sec=timeout_sec)
        except (McpHttpError, Exception) as exc:
            raise OpenClawAdapterError("sessions_send", str(exc)) from exc

    def session_status(self, *, tool_args: dict[str, Any], timeout_sec: float = 30.0) -> dict[str, Any]:
        try:
            return self._client.call_tool(tool_name="session_status", tool_args=dict(tool_args or {}), timeout_sec=timeout_sec)
        except (McpHttpError, Exception) as exc:
            raise OpenClawAdapterError("session_status", str(exc)) from exc

    def run_protocol(
        self,
        *,
        run_id: str,
        step_id: str,
        question: str,
        params: dict[str, Any],
    ) -> OpenClawSessionTrace:
        timeout_sec = max(5.0, float(params.get("openclaw_timeout_seconds") or 45.0))
        session_key = str(
            params.get("openclaw_session_key")
            or f"advisor:{str(run_id).strip()}:{str(step_id).strip()}:{int(time.time())}"
        ).strip()
        spawn_args: dict[str, Any] = {
            "sessionKey": session_key,
            "agentId": str(params.get("openclaw_agent_id") or "advisor"),
            "model": (str(params.get("openclaw_model") or "").strip() or None),
            "thinking": (str(params.get("openclaw_thinking") or "").strip() or None),
            "timeoutSeconds": int(params.get("openclaw_session_timeout_seconds") or timeout_sec),
            "cleanup": bool(params.get("openclaw_cleanup", True)),
        }
        spawn = self.sessions_spawn(tool_args=spawn_args, timeout_sec=timeout_sec)

        send: dict[str, Any] | None = None
        if str(question or "").strip():
            send_args: dict[str, Any] = {
                "sessionKey": session_key,
                "message": str(question),
                "allowA2A": bool(params.get("openclaw_allow_a2a", True)),
            }
            send = self.sessions_send(tool_args=send_args, timeout_sec=timeout_sec)

        status = self.session_status(tool_args={"sessionKey": session_key}, timeout_sec=max(5.0, timeout_sec / 2.0))
        return OpenClawSessionTrace(session_key=session_key, spawn=spawn, send=send, status=status)
