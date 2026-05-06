"""Network request logging for ChatGPT Web automation.

Extracted from _tools_impl.py — ~440 lines of self-contained netlog
infrastructure.  All public names are re-exported by _tools_impl to
maintain backward compatibility.
"""
from __future__ import annotations

import datetime
import json
import logging
import logging.handlers
import os
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mcp.server.fastmcp import Context

from chatgpt_web_mcp.env import _truthy_env
from chatgpt_web_mcp.runtime.paths import _debug_dir
from chatgpt_web_mcp.runtime.util import _coerce_error_text, _ctx_info

def _chatgpt_netlog_enabled() -> bool:
    return _truthy_env("CHATGPT_NETLOG_ENABLED", False)


def _chatgpt_netlog_path() -> Path:
    raw = (os.environ.get("CHATGPT_NETLOG_PATH") or "").strip()
    if raw:
        return Path(raw).expanduser()
    debug_dir = _debug_dir()
    if debug_dir is not None:
        return debug_dir / "chatgpt_web_netlog.jsonl"
    return Path("artifacts/chatgpt_web_netlog.jsonl")


def _chatgpt_netlog_max_bytes() -> int:
    raw = (os.environ.get("CHATGPT_NETLOG_MAX_BYTES") or "").strip()
    if not raw:
        return 10_000_000
    try:
        return max(10_000, int(raw))
    except ValueError:
        return 10_000_000


def _chatgpt_netlog_backup_count() -> int:
    raw = (os.environ.get("CHATGPT_NETLOG_BACKUP_COUNT") or "").strip()
    if not raw:
        return 3
    try:
        return max(0, int(raw))
    except ValueError:
        return 3


def _chatgpt_netlog_resource_types() -> set[str]:
    raw = (os.environ.get("CHATGPT_NETLOG_RESOURCE_TYPES") or "").strip()
    if not raw:
        raw = "xhr,fetch,eventsource,websocket"
    out: set[str] = set()
    for part in raw.split(","):
        key = re.sub(r"[^a-z]+", "", part.strip().lower())
        if key:
            out.add(key)
    return out


def _chatgpt_netlog_host_allowlist() -> set[str]:
    raw = (os.environ.get("CHATGPT_NETLOG_HOST_ALLOWLIST") or "").strip()
    if not raw:
        raw = "chatgpt.com,ab.chatgpt.com"
    out: set[str] = set()
    for part in raw.split(","):
        host = part.strip().lower()
        if host:
            out.add(host)
    return out


def _chatgpt_netlog_redact_query() -> bool:
    return _truthy_env("CHATGPT_NETLOG_REDACT_QUERY", True)


def _chatgpt_netlog_redact_ids() -> bool:
    return _truthy_env("CHATGPT_NETLOG_REDACT_IDS", True)

def _chatgpt_netlog_capture_model_route() -> bool:
    # Default off: even when redacted, request bodies can contain sensitive user text.
    # When enabled, we only emit a small whitelist of non-content routing fields.
    return _truthy_env("CHATGPT_NETLOG_CAPTURE_MODEL_ROUTE", False)


def _chatgpt_netlog_line_max_chars() -> int:
    raw = (os.environ.get("CHATGPT_NETLOG_LINE_MAX_CHARS") or "").strip()
    if not raw:
        return 2_000
    try:
        return max(200, int(raw))
    except ValueError:
        return 2_000


_NETLOG_LOCK = threading.Lock()
_NETLOG_LOGGER: logging.Logger | None = None

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_LONG_HEX_RE = re.compile(r"[0-9a-f]{32,}", re.I)


def _chatgpt_netlog_redact_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    if raw.startswith(("data:", "blob:", "chrome-extension:")):
        return raw[:60]
    try:
        parsed = urlparse(raw)
    except Exception:
        return raw[:200]
    scheme = (parsed.scheme or "https").strip()
    host = (parsed.netloc or "").strip()
    path = (parsed.path or "").strip()
    if _chatgpt_netlog_redact_ids() and path:
        path = _UUID_RE.sub("<uuid>", path)
        path = _LONG_HEX_RE.sub("<hex>", path)
    query = ""
    if not _chatgpt_netlog_redact_query():
        query = (parsed.query or "").strip()
    out = f"{scheme}://{host}{path}"
    if query:
        out += f"?{query}"
    if parsed.fragment and not _chatgpt_netlog_redact_query():
        out += f"#{parsed.fragment}"
    max_len = _chatgpt_netlog_line_max_chars()
    if len(out) > max_len:
        return out[: max(0, max_len - 1)] + "…"
    return out


def _chatgpt_netlog_logger() -> logging.Logger | None:
    global _NETLOG_LOGGER
    if not _chatgpt_netlog_enabled():
        return None
    if _NETLOG_LOGGER is not None:
        return _NETLOG_LOGGER
    with _NETLOG_LOCK:
        if _NETLOG_LOGGER is not None:
            return _NETLOG_LOGGER
        path = _chatgpt_netlog_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            return None
        logger = logging.getLogger("chatgpt_web_netlog")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers):
            handler = logging.handlers.RotatingFileHandler(
                str(path),
                maxBytes=_chatgpt_netlog_max_bytes(),
                backupCount=_chatgpt_netlog_backup_count(),
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
        _NETLOG_LOGGER = logger
        return logger


def _chatgpt_netlog_write(event: dict[str, Any]) -> None:
    logger = _chatgpt_netlog_logger()
    if logger is None:
        return
    try:
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return
    max_len = _chatgpt_netlog_line_max_chars()
    if max_len > 0 and len(line) > max_len:
        line = line[: max(0, max_len - 1)] + "…"
    try:
        logger.info(line)
    except Exception:
        return


def _chatgpt_netlog_sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        s = value.strip()
        if _chatgpt_netlog_redact_ids():
            s = _UUID_RE.sub("<uuid>", s)
            s = _LONG_HEX_RE.sub("<hex>", s)
        if len(s) > 300:
            s = s[:299] + "…"
        return s
    if value is None or isinstance(value, (bool, int, float)):
        return value
    # Avoid structured objects (can include prompt content); stringify defensively.
    try:
        s = str(value)
    except Exception:
        s = ""
    s = s.strip()
    if _chatgpt_netlog_redact_ids():
        s = _UUID_RE.sub("<uuid>", s)
        s = _LONG_HEX_RE.sub("<hex>", s)
    if len(s) > 300:
        s = s[:299] + "…"
    return s


def _chatgpt_netlog_extract_model_route_fields(*, post_data: str) -> dict[str, Any] | None:
    body = str(post_data or "")
    if not body.strip():
        return None
    # Hard cap to avoid large allocations (prompts/attachments live in request bodies).
    if len(body) > 1_000_000:
        return {"body_too_large": True, "body_bytes": len(body)}
    try:
        obj = json.loads(body)
    except Exception:
        return None
    return _chatgpt_netlog_extract_model_route_fields_obj(obj=obj)


def _chatgpt_netlog_extract_model_route_fields_obj(*, obj: Any) -> dict[str, Any] | None:
    if not isinstance(obj, dict):
        return None

    out: dict[str, Any] = {}

    # Whitelist only routing-ish fields; never log message content.
    for key in (
        "action",
        "conversation_id",
        "parent_message_id",
        "model",
        "model_slug",
        "default_model_slug",
        "reasoning_effort",
        "thinking_effort",
    ):
        if key in obj:
            out[key] = _chatgpt_netlog_sanitize_value(obj.get(key))

    messages = obj.get("messages")
    if isinstance(messages, list):
        out["messages_count"] = len(messages)

    return out or None


async def _chatgpt_install_netlog(page, *, tool: str, run_id: str, ctx: Context | None) -> None:
    logger = _chatgpt_netlog_logger()
    if logger is None:
        return
    started_at = time.time()
    allowed_types = _chatgpt_netlog_resource_types()
    host_allow = _chatgpt_netlog_host_allowlist()
    seq = 0

    def _ts() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    def _should_log_url(url: str) -> bool:
        try:
            host = (urlparse(str(url or "")).hostname or "").lower()
        except Exception:
            host = ""
        if not host:
            return False
        for allowed in host_allow:
            if host == allowed or host.endswith("." + allowed):
                return True
        return False

    def _base(kind: str) -> dict[str, Any]:
        return {
            "ts": _ts(),
            "kind": kind,
            "tool": str(tool or ""),
            "run_id": str(run_id or ""),
            "t_ms": round((time.time() - started_at) * 1000.0, 1),
        }

    def on_request(req) -> None:
        nonlocal seq
        try:
            rtype = str(getattr(req, "resource_type", "") or "").strip().lower()
        except Exception:
            rtype = ""
        if allowed_types and rtype and rtype not in allowed_types:
            return
        try:
            url = str(req.url or "")
        except Exception:
            url = ""
        if not _should_log_url(url):
            return
        seq += 1
        try:
            payload = _base("request")
            payload.update(
                {
                    "seq": seq,
                    "request_id": hex(id(req)),
                    "method": str(req.method or ""),
                    "resource_type": rtype,
                    "url": _chatgpt_netlog_redact_url(url),
                    "is_navigation": bool(getattr(req, "is_navigation_request", lambda: False)()),
                }
            )
            if (
                _chatgpt_netlog_capture_model_route()
                and str(payload.get("method") or "").upper() == "POST"
                and (
                    "/backend-api/conversation" in url
                    or "/backend-api/f/conversation" in url
                    or "/backend-api/sentinel/chat-requirements" in url
                )
            ):
                try:
                    post_data = ""
                    route: dict[str, Any] | None = None
                    route_err: dict[str, Any] = {}
                    try:
                        pdj = getattr(req, "post_data_json", None)
                        if callable(pdj):
                            try:
                                obj = pdj()
                                # Always record a minimal probe (top-level keys), even if no whitelisted route fields exist.
                                if isinstance(obj, dict):
                                    keys = [str(k) for k in obj.keys() if isinstance(k, str)]
                                    keys = sorted(keys)[:50]
                                    if keys:
                                        route_err["post_data_json_keys"] = keys
                                route = _chatgpt_netlog_extract_model_route_fields_obj(obj=obj)
                            except Exception as e:
                                route_err["post_data_json_error"] = type(e).__name__
                    except Exception:
                        route_err["post_data_json_error"] = "unknown"
                    try:
                        pd = getattr(req, "post_data", None)
                        post_data = str(pd() if callable(pd) else (pd or ""))
                    except Exception:
                        post_data = ""
                    if not post_data:
                        try:
                            post_data = str(req.post_data() or "")
                        except Exception:
                            post_data = ""
                    if route is None:
                        route = _chatgpt_netlog_extract_model_route_fields(post_data=post_data)
                    if route:
                        payload["conversation_route"] = route
                    else:
                        if post_data:
                            route_err.setdefault("post_data_bytes", len(post_data.encode("utf-8", errors="ignore")))
                        route_err.setdefault("no_route_fields", True)
                        if route_err:
                            payload["conversation_route_error"] = route_err
                except Exception:
                    pass
            try:
                frame = getattr(req, "frame", None)
                if frame is not None:
                    payload["frame_url"] = _chatgpt_netlog_redact_url(str(getattr(frame, "url", "") or ""))
            except Exception:
                pass
            _chatgpt_netlog_write(payload)
        except Exception:
            return

    def on_response(resp) -> None:
        try:
            req = resp.request
        except Exception:
            return
        try:
            rtype = str(getattr(req, "resource_type", "") or "").strip().lower()
        except Exception:
            rtype = ""
        if allowed_types and rtype and rtype not in allowed_types:
            return
        try:
            url = str(req.url or "")
        except Exception:
            url = ""
        if not _should_log_url(url):
            return
        try:
            payload = _base("response")
            payload.update(
                {
                    "request_id": hex(id(req)),
                    "status": int(resp.status),
                    "resource_type": rtype,
                    "url": _chatgpt_netlog_redact_url(url),
                }
            )
            _chatgpt_netlog_write(payload)
        except Exception:
            return

    def on_failed(req) -> None:
        try:
            rtype = str(getattr(req, "resource_type", "") or "").strip().lower()
        except Exception:
            rtype = ""
        if allowed_types and rtype and rtype not in allowed_types:
            return
        try:
            url = str(req.url or "")
        except Exception:
            url = ""
        if not _should_log_url(url):
            return
        try:
            failure = getattr(req, "failure", None)
            err = ""
            try:
                if isinstance(failure, dict):
                    err = str(failure.get("errorText") or "")
                elif failure:
                    err = str(failure)
            except Exception:
                err = ""
            payload = _base("request_failed")
            payload.update(
                {
                    "request_id": hex(id(req)),
                    "method": str(getattr(req, "method", "") or ""),
                    "resource_type": rtype,
                    "url": _chatgpt_netlog_redact_url(url),
                    "error": _coerce_error_text(err, limit=500),
                }
            )
            _chatgpt_netlog_write(payload)
        except Exception:
            return

    def on_console(msg) -> None:
        # Only log explicit markers we emit (avoid noisy/sensitive site console output).
        try:
            text = str(msg.text or "").strip()
        except Exception:
            return
        if not text.startswith("[chatgptrest]"):
            return
        payload = _base("console")
        payload["text"] = _coerce_error_text(text, limit=500)
        _chatgpt_netlog_write(payload)

    try:
        page.on("request", on_request)
        page.on("response", on_response)
        page.on("requestfailed", on_failed)
        page.on("console", on_console)
    except Exception as exc:
        await _ctx_info(ctx, f"Failed to install netlog hooks: {exc}")
        return
    await _ctx_info(ctx, f"ChatGPT netlog enabled: {_chatgpt_netlog_path()}")
