from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional, Tuple


JSONRPCMessage = Dict[str, Any]


class McpHttpError(RuntimeError):
    pass


@dataclass(frozen=True)
class McpHttpSession:
    url: str
    session_id: Optional[str]
    protocol_version: str


def _is_loopback_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    host = (parsed.hostname or "").strip().lower()
    return host in {"127.0.0.1", "localhost"}


def _urlopen(req: urllib.request.Request, *, timeout_sec: float, bypass_proxy: bool) -> Any:
    if not bypass_proxy:
        return urllib.request.urlopen(req, timeout=float(timeout_sec))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(req, timeout=float(timeout_sec))


def _read_header(headers: Dict[str, str], name: str) -> Optional[str]:
    for k, v in headers.items():
        if k.lower() == name.lower():
            return v
    return None


def _iter_sse_events(fp: Any, *, deadline_monotonic: float | None = None) -> Iterator[Dict[str, str]]:
    event: Dict[str, str] = {}
    data_lines: list[str] = []
    while True:
        if deadline_monotonic is not None and time.monotonic() > deadline_monotonic:
            raise McpHttpError("SSE stream timeout (deadline exceeded).")
        try:
            raw = fp.readline()
        except (socket.timeout, TimeoutError):
            continue
        if not raw:
            break
        try:
            line = raw.decode("utf-8", errors="replace")
        except Exception:
            line = str(raw)
        line = line.rstrip("\r\n")
        if not line:
            if data_lines:
                event["data"] = "\n".join(data_lines)
            if event:
                yield dict(event)
            event = {}
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        if ":" in line:
            field, value = line.split(":", 1)
            value = value.lstrip(" ")
        else:
            field, value = line, ""
        field = field.strip()
        if field == "data":
            data_lines.append(value)
        else:
            event[field] = value

    if data_lines:
        event["data"] = "\n".join(data_lines)
    if event:
        yield event


def _jsonrpc_post_stream(
    url: str,
    *,
    message: JSONRPCMessage,
    headers: Dict[str, str],
    timeout_sec: float,
) -> Tuple[int, Dict[str, str], Any]:
    bypass_proxy = _is_loopback_url(url)
    req = urllib.request.Request(
        url,
        data=json.dumps(message, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    # For SSE streams, urllib's socket timeout only limits "idle read" time.
    socket_timeout_sec = min(float(timeout_sec), 60.0)
    try:
        resp = _urlopen(req, timeout_sec=socket_timeout_sec, bypass_proxy=bypass_proxy)
        status = int(getattr(resp, "status", 200))
        resp_headers = {k: v for k, v in resp.headers.items()}
        return status, resp_headers, resp
    except urllib.error.HTTPError as e:
        status = int(getattr(e, "code", 500))
        resp_headers = {k: v for k, v in (e.headers.items() if e.headers else [])}
        return status, resp_headers, e
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None)
        msg = str(reason) if reason is not None else str(e)
        raise McpHttpError(f"transport error: {msg}") from e
    except (socket.timeout, TimeoutError) as e:
        raise McpHttpError(f"transport timeout: {e}") from e
    except OSError as e:
        raise McpHttpError(f"transport error: {type(e).__name__}: {e}") from e
    except Exception as e:
        # Anything else is unexpected (logic/serialization bugs, etc).
        raise McpHttpError(f"internal error: {type(e).__name__}: {e}") from e


def _parse_jsonrpc_from_sse(
    fp: Any,
    *,
    want_id: Any,
    deadline_monotonic: float | None = None,
) -> JSONRPCMessage:
    for ev in _iter_sse_events(fp, deadline_monotonic=deadline_monotonic):
        if ev.get("event") and ev.get("event") != "message":
            continue
        data = (ev.get("data") or "").strip()
        if not data:
            continue
        try:
            msg = json.loads(data)
        except Exception:
            continue
        if not isinstance(msg, dict):
            continue
        if msg.get("id") == want_id:
            return msg
    raise McpHttpError("SSE stream ended without a JSON-RPC response.")


def _prepare_headers(session: McpHttpSession | None) -> Dict[str, str]:
    headers: Dict[str, str] = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if session and session.session_id:
        headers["mcp-session-id"] = session.session_id
    if session and session.protocol_version:
        headers["mcp-protocol-version"] = session.protocol_version
    return headers


def mcp_http_initialize(
    url: str,
    *,
    client_name: str,
    client_version: str,
    protocol_version: str = "2025-06-18",
    timeout_sec: float = 30.0,
) -> McpHttpSession:
    message: JSONRPCMessage = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": protocol_version,
            "clientInfo": {"name": client_name, "version": client_version},
            "capabilities": {},
        },
    }
    deadline = time.monotonic() + float(timeout_sec)
    status, resp_headers, fp = _jsonrpc_post_stream(url, message=message, headers=_prepare_headers(None), timeout_sec=timeout_sec)
    try:
        if status != 200:
            raise McpHttpError(f"initialize failed: HTTP {status}")
        ctype = (_read_header(resp_headers, "content-type") or "").lower()
        if ctype.startswith("application/json"):
            raw = fp.read()
            msg = json.loads(raw.decode("utf-8", errors="replace"))
        else:
            msg = _parse_jsonrpc_from_sse(fp, want_id=1, deadline_monotonic=deadline)
    finally:
        try:
            fp.close()
        except Exception:
            pass

    if not isinstance(msg, dict) or msg.get("id") != 1:
        raise McpHttpError(f"initialize bad response: {str(msg)[:300]}")
    if "error" in msg:
        raise McpHttpError(f"initialize error: {json.dumps(msg['error'], ensure_ascii=False)[:500]}")

    session_id = _read_header(resp_headers, "mcp-session-id")
    negotiated = None
    try:
        result = msg.get("result") or {}
        negotiated = str(result.get("protocolVersion") or "").strip() or None
    except Exception:
        negotiated = None
    session = McpHttpSession(url=url, session_id=session_id, protocol_version=negotiated or protocol_version)

    # Best-effort notifications/initialized (no response expected).
    notif: JSONRPCMessage = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                url,
                data=json.dumps(notif, ensure_ascii=False).encode("utf-8"),
                headers=_prepare_headers(session),
                method="POST",
            ),
            timeout=float(timeout_sec),
        ).close()
    except Exception:
        pass

    return session


def mcp_http_call_tool(
    session: McpHttpSession,
    *,
    tool_name: str,
    tool_args: Dict[str, Any],
    timeout_sec: float = 600.0,
) -> Dict[str, Any]:
    req_id = int(time.time() * 1000) % 10_000_000
    deadline = time.monotonic() + float(timeout_sec)
    message: JSONRPCMessage = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": tool_args},
    }

    status, resp_headers, fp = _jsonrpc_post_stream(
        session.url,
        message=message,
        headers=_prepare_headers(session),
        timeout_sec=timeout_sec,
    )
    try:
        if status == 202:
            raise McpHttpError("tools/call returned 202 Accepted (unexpected)")
        if status != 200:
            raw = fp.read() if hasattr(fp, "read") else b""
            snippet = raw.decode("utf-8", errors="replace")[:500].strip()
            raise McpHttpError(f"tools/call failed: HTTP {status} {snippet}")

        ctype = (_read_header(resp_headers, "content-type") or "").lower()
        if ctype.startswith("application/json"):
            raw = fp.read()
            msg = json.loads(raw.decode("utf-8", errors="replace"))
        else:
            msg = _parse_jsonrpc_from_sse(fp, want_id=req_id, deadline_monotonic=deadline)
    finally:
        try:
            fp.close()
        except Exception:
            pass

    if not isinstance(msg, dict) or msg.get("id") != req_id:
        raise McpHttpError(f"tools/call bad response: {str(msg)[:300]}")
    if "error" in msg:
        raise McpHttpError(f"tools/call error: {json.dumps(msg['error'], ensure_ascii=False)[:500]}")

    result = msg.get("result") or {}
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured

    if bool(result.get("isError")) and isinstance(result.get("content"), list):
        parts: list[str] = []
        for item in result.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    parts.append(text)
        if parts:
            snippet = "\n".join(parts)[:1200]
            raise McpHttpError(f"tools/call tool error: {snippet}")

    raise McpHttpError(f"tools/call missing structuredContent: {json.dumps(result, ensure_ascii=False)[:500]}")


class McpHttpClient:
    def __init__(self, *, url: str, client_name: str, client_version: str):
        self._url = url
        self._client_name = client_name
        self._client_version = client_version
        self._session: McpHttpSession | None = None

    @property
    def url(self) -> str:
        return self._url

    def _ensure_session(self) -> McpHttpSession:
        if self._session is None:
            self._session = mcp_http_initialize(
                self._url,
                client_name=self._client_name,
                client_version=self._client_version,
            )
        return self._session

    def call_tool(self, *, tool_name: str, tool_args: Dict[str, Any], timeout_sec: float = 600.0) -> Dict[str, Any]:
        session = self._ensure_session()
        try:
            return mcp_http_call_tool(session, tool_name=tool_name, tool_args=tool_args, timeout_sec=timeout_sec)
        except McpHttpError:
            # Retry once with a fresh session (server may have rotated/invalidated state).
            self._session = None
            session = self._ensure_session()
            return mcp_http_call_tool(session, tool_name=tool_name, tool_args=tool_args, timeout_sec=timeout_sec)
