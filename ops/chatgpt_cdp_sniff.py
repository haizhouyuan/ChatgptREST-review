#!/usr/bin/env python3
"""
CDP network sniffer for ChatGPT Web routing diagnostics.

Goal: capture enough backend request/response metadata to debug cases where the UI shows
"Pro + Extended thinking" selected, but the response appears to be routed differently
(e.g., "instant" answers without a thinking footer).

This script intentionally avoids writing sensitive data to disk:
- Does NOT persist cookies / Authorization headers.
- Does NOT persist user message text (prompt content).
- Extracts and persists only whitelisted routing fields from request/response bodies.

Usage (default):
  python3 ops/chatgpt_cdp_sniff.py --timeout-seconds 600 --max-conversation-posts 6

Notes:
- Playwright may fail to attach to newer Chrome builds unless Chrome is started with
  `--remote-allow-origins=*`. This script uses a direct CDP websocket connection and
  suppresses the Origin header to work with stricter defaults.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import websocket  # websocket-client


def _now_ms() -> int:
    return int(time.time() * 1000)


def _utc_ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.gmtime())


def _read_json_url(url: str, *, timeout_s: float = 2.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "chatgptrest-cdp-sniffer/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.load(resp)


def _resolve_cdp_ws_url(cdp_url: str) -> str:
    raw = (cdp_url or "").strip().rstrip("/")
    if not raw:
        raise ValueError("cdp_url is required")
    if raw.startswith(("ws://", "wss://")):
        return raw
    version = _read_json_url(f"{raw}/json/version")
    if not isinstance(version, dict):
        raise RuntimeError(f"Unexpected CDP /json/version payload: {type(version).__name__}")
    ws_url = str(version.get("webSocketDebuggerUrl") or "").strip()
    if not ws_url:
        raise RuntimeError("CDP /json/version missing webSocketDebuggerUrl")
    return ws_url


def _safe_header_key(key: str) -> str:
    return str(key or "").strip().lower()


_DROP_HEADER_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-csrf-token",
    "x-xsrf-token",
    "x-openai-xsrf-token",
    "x-openai-auth",
    "x-openai-session",
    "oai-device-id",
}


def _sanitize_headers(headers: Any) -> dict[str, str]:
    if not isinstance(headers, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in headers.items():
        kk = _safe_header_key(k)
        if not kk:
            continue
        if kk in _DROP_HEADER_KEYS or kk == "x-conduit-token" or kk.startswith("openai-sentinel-"):
            continue
        vv = str(v) if v is not None else ""
        if len(vv) > 500:
            vv = vv[:500] + "..."
        out[kk] = vv
    return out


def _safe_int(x: Any) -> int | None:
    try:
        return int(x)
    except Exception:
        return None


_ROUTE_KEYS_ALLOWLIST = {
    "model",
    "model_slug",
    "default_model_slug",
    "resolved_model_slug",
    "thinking_effort",
    "reasoning_effort",
    "conversation_id",
    "parent_message_id",
    "timezone_offset_min",
    "conversation_mode",
    "web_search",
    "web_search_enabled",
    "web_search_mode",
}


def _extract_route_fields_from_obj(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict):
        return {}
    out: dict[str, Any] = {}
    for key in sorted(_ROUTE_KEYS_ALLOWLIST):
        if key not in obj:
            continue
        val = obj.get(key)
        if isinstance(val, (str, int, float, bool)) or val is None:
            out[key] = val
        elif isinstance(val, dict):
            # Keep only shallow scalar sub-fields.
            sub: dict[str, Any] = {}
            for sk, sv in val.items():
                if isinstance(sv, (str, int, float, bool)) or sv is None:
                    sub[str(sk)] = sv
            if sub:
                out[key] = sub
        else:
            # For lists/complex structures: record only the type/size.
            if isinstance(val, list):
                out[key] = {"_type": "list", "len": len(val)}
            else:
                out[key] = {"_type": type(val).__name__}
    return out


def _extract_request_route(post_data: str) -> dict[str, Any]:
    """
    Extract safe routing fields from a ChatGPT /backend-api/conversation POST body.
    """
    if not post_data:
        return {}
    try:
        obj = json.loads(post_data)
    except Exception:
        return {"post_data_parse_error": True, "post_data_bytes": len(post_data.encode("utf-8", errors="ignore"))}

    route = _extract_route_fields_from_obj(obj)

    # ChatGPT UI bodies include `messages` with user content. We do not persist it, but we keep sizes.
    messages = obj.get("messages")
    if isinstance(messages, list):
        route["messages_len"] = len(messages)

    # Some UIs nest reasoning under `metadata`.
    metadata = obj.get("metadata")
    if isinstance(metadata, dict):
        md_route = _extract_route_fields_from_obj(metadata)
        if md_route:
            route["metadata"] = md_route

    return route



def _iter_sse_json_objects(body_text: str):
    # Best-effort: ChatGPT streaming responses are text/event-stream with lines like 'data: {...}'.
    for line in (body_text or '').splitlines():
        if not line.startswith('data:'):
            continue
        payload = line[5:].strip()
        if not payload or payload == '[DONE]':
            continue
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        yield obj

def _extract_response_meta(body_text: str) -> dict[str, Any]:
    """
    Extract safe model-routing fields from a ChatGPT conversation response.
    """
    if not body_text:
        return {}
    try:
        obj = json.loads(body_text)
    except Exception:
        # Try parsing streaming SSE frames.
        out = {"response_bytes": len(body_text.encode("utf-8", errors="ignore"))}
        for obj in _iter_sse_json_objects(body_text):
            if not isinstance(obj, dict):
                continue
            # Match the non-streaming schema when possible.
            conv_id = obj.get("conversation_id")
            if isinstance(conv_id, str) and conv_id and "conversation_id" not in out:
                out["conversation_id"] = conv_id
            msg = obj.get("message")
            if isinstance(msg, dict):
                mid = msg.get("id")
                if isinstance(mid, str) and mid and "message_id" not in out:
                    out["message_id"] = mid
                metadata = msg.get("metadata")
                if isinstance(metadata, dict) and "message_metadata" not in out:
                    md_route = _extract_route_fields_from_obj(metadata)
                    if md_route:
                        out["message_metadata"] = md_route
            # Some frames use top-level metadata.
            md = obj.get("metadata")
            if isinstance(md, dict) and "frame_metadata" not in out:
                md_route = _extract_route_fields_from_obj(md)
                if md_route:
                    out["frame_metadata"] = md_route
            if any(k in out for k in ("conversation_id", "message_id", "message_metadata")):
                break
        if len(out) > 1:
            return out
        return {"response_parse_error": True, **out}

    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        conv_id = obj.get("conversation_id")
        if isinstance(conv_id, str) and conv_id:
            out["conversation_id"] = conv_id

        msg = obj.get("message")
        if isinstance(msg, dict):
            mid = msg.get("id")
            if isinstance(mid, str) and mid:
                out["message_id"] = mid
            metadata = msg.get("metadata")
            if isinstance(metadata, dict):
                md_route = _extract_route_fields_from_obj(metadata)
                if md_route:
                    out["message_metadata"] = md_route

    return out


@dataclass(frozen=True)
class TargetInfo:
    target_id: str
    url: str
    title: str


class CDPClient:
    def __init__(self, ws_url: str, *, events_q: "queue.Queue[dict[str, Any]]", source: str):
        self._ws = websocket.create_connection(
            ws_url,
            timeout=30,
            suppress_origin=True,  # Critical for newer Chrome devtools origin checks
        )
        self._events_q = events_q
        self._source = str(source or "").strip() or "cdp"
        self._next_id = 0
        self._pending: dict[int, "queue.Queue[dict[str, Any]]"] = {}
        self._closed = False

        import threading

        self._rx_thread = threading.Thread(target=self._rx_loop, name="cdp-rx", daemon=True)
        self._rx_thread.start()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._ws.close()
        except Exception:
            pass

    def _send(self, *, method: str, params: dict[str, Any], session_id: str | None, pending_q: "queue.Queue[dict[str, Any]]" | None) -> int:
        self._next_id += 1
        req_id = self._next_id
        if pending_q is not None:
            # Register before send to avoid a race where the response arrives immediately.
            self._pending[req_id] = pending_q
        msg: dict[str, Any] = {"id": req_id, "method": method, "params": params}
        if session_id:
            msg["sessionId"] = session_id
        self._ws.send(json.dumps(msg, ensure_ascii=False))
        return req_id

    def call(self, method: str, params: dict[str, Any] | None = None, *, session_id: str | None = None, timeout_s: float = 10.0) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("CDP client closed")
        q: "queue.Queue[dict[str, Any]]" = queue.Queue(maxsize=1)
        req_id = self._send(method=method, params=params or {}, session_id=session_id, pending_q=q)
        try:
            resp = q.get(timeout=timeout_s)
        except queue.Empty as exc:
            raise TimeoutError(f"CDP call timeout: {method}") from exc
        finally:
            self._pending.pop(req_id, None)
        if "error" in resp:
            err = resp.get("error") or {}
            raise RuntimeError(f"CDP error calling {method}: {err}")
        result = resp.get("result")
        if not isinstance(result, dict):
            # Some CDP methods return null; normalize to {}.
            return {}
        return result

    def notify(self, method: str, params: dict[str, Any] | None = None, *, session_id: str | None = None) -> None:
        """
        Fire-and-forget CDP command (do not wait for a response).
        Useful when a target is flaky: we still want to try enabling a domain
        without turning a missing ACK into a hard failure.
        """
        if self._closed:
            return
        try:
            self._send(method=method, params=params or {}, session_id=session_id, pending_q=None)
        except Exception:
            return

    def _rx_loop(self) -> None:
        while not self._closed:
            try:
                raw = self._ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                break
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue

            if isinstance(msg, dict) and "id" in msg:
                req_id = _safe_int(msg.get("id"))
                if req_id is not None:
                    q = self._pending.get(req_id)
                    if q is not None:
                        try:
                            q.put_nowait(msg)
                        except Exception:
                            pass
                        continue

            if isinstance(msg, dict) and "method" in msg:
                try:
                    tagged = dict(msg)
                    tagged["_source"] = self._source
                    self._events_q.put_nowait(tagged)
                except Exception:
                    pass


def _write_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False, sort_keys=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Sniff ChatGPT Web routing fields via CDP.")
    ap.add_argument(
        "--cdp-url",
        default=os.environ.get("CHATGPT_CDP_URL") or "http://127.0.0.1:9222",
        help="CDP HTTP endpoint (http://host:port) or websocket URL (ws://...). Default: CHATGPT_CDP_URL or http://127.0.0.1:9222",
    )
    ap.add_argument(
        "--target-url-regex",
        default=r"https?://(www\.)?chatgpt\.com/.*",
        help="Regex to select page targets to attach to (default matches chatgpt.com).",
    )
    ap.add_argument(
        "--timeout-seconds",
        type=int,
        default=600,
        help="Stop after this many seconds (default: 600).",
    )
    ap.add_argument(
        "--max-conversation-posts",
        type=int,
        default=6,
        help="Stop after capturing this many /backend-api/conversation POST requests (default: 6).",
    )
    ap.add_argument(
        "--out-dir",
        default="",
        help="Output directory (default: artifacts/probe_thinking/cdp_sniff_<utc_ts>).",
    )
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="Also log non-backend-api requests (still sanitized).",
    )
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    try:
        target_re = re.compile(args.target_url_regex)
    except re.error as exc:
        print(f"Invalid --target-url-regex: {exc}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir) if args.out_dir else Path("artifacts/probe_thinking") / f"cdp_sniff_{_utc_ts()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    events_q: "queue.Queue[dict[str, Any]]" = queue.Queue(maxsize=10_000)

    cdp_url = str(args.cdp_url).strip()
    http_base = _resolve_http_base_from_ws(cdp_url) if cdp_url.startswith(("ws://", "wss://")) else cdp_url.rstrip("/")
    _write_json(out_dir / "cdp_endpoint.json", {"cdp_url": cdp_url, "http_base": http_base, "captured_at_ms": _now_ms()})
    try:
        _write_json(out_dir / "cdp_version.json", _read_json_url(f"{http_base}/json/version"))
    except Exception:
        # Best-effort only.
        pass

    clients: dict[str, CDPClient] = {}
    attached_targets: dict[str, TargetInfo] = {}
    enable_errors: dict[str, Any] = {}

    try:
        if cdp_url.startswith(("ws://", "wss://")):
            source = "page_ws"
            client = CDPClient(cdp_url, events_q=events_q, source=source)
            clients[source] = client
            attached_targets[source] = TargetInfo(target_id=source, url=cdp_url, title="")
            client.call("Network.enable", {}, timeout_s=5.0)
        else:
            targets_list = _read_json_url(f"{http_base}/json/list")
            if not isinstance(targets_list, list):
                targets_list = []
            _write_json(out_dir / "cdp_targets.json", targets_list)

            for ti in targets_list:
                if not isinstance(ti, dict):
                    continue
                if ti.get("type") != "page":
                    continue
                url = str(ti.get("url") or "")
                if not url or not target_re.search(url):
                    continue
                ws = str(ti.get("webSocketDebuggerUrl") or "").strip()
                if not ws:
                    continue
                target_id = str(ti.get("id") or "").strip()
                if not target_id:
                    continue
                title = str(ti.get("title") or "")

                source = target_id
                client = CDPClient(ws, events_q=events_q, source=source)
                clients[source] = client
                attached_targets[source] = TargetInfo(target_id=target_id, url=url, title=title)
                try:
                    client.call("Network.enable", {}, timeout_s=3.0)
                except Exception as exc:
                    enable_errors[source] = {"error_type": type(exc).__name__, "error": str(exc)[:500]}
                    client.notify("Network.enable", {})

        _write_json(
            out_dir / "attached_targets.json",
            {
                "attached_at_ms": _now_ms(),
                "target_url_regex": args.target_url_regex,
                "targets": {sid: {"target_id": t.target_id, "url": t.url, "title": t.title} for sid, t in attached_targets.items()},
                "network_enable_errors": enable_errors,
            },
        )

        if not attached_targets:
            print("No matching chatgpt.com page targets found. Open ChatGPT in the CDP Chrome first.", file=sys.stderr)
            return 3

        events_path = out_dir / "net_events.jsonl"
        conv_path = out_dir / "conversation_posts.jsonl"

        conv_posts = 0
        max_posts = max(1, int(args.max_conversation_posts))
        observed: dict[tuple[str, str], dict[str, Any]] = {}  # (source, requestId) -> info

        deadline = time.time() + max(1, int(args.timeout_seconds))
        while time.time() < deadline:
            try:
                msg = events_q.get(timeout=0.25)
            except queue.Empty:
                if conv_posts >= max_posts and not observed:
                    break
                continue
            if not isinstance(msg, dict):
                continue

            method = str(msg.get("method") or "")
            params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
            source = str(msg.get("_source") or "").strip()
            if not source or source not in clients:
                continue
            client = clients[source]

            if method == "Network.requestWillBeSent":
                req = params.get("request") if isinstance(params.get("request"), dict) else {}
                url = str(req.get("url") or "")
                http_method = str(req.get("method") or "")
                request_id = str(params.get("requestId") or "")
                if not url or not request_id:
                    continue

                parsed = _classify_url(url)
                if not args.verbose and not parsed["is_backend_api"]:
                    continue

                ev = {
                    "t_ms": _now_ms(),
                    "kind": "request",
                    "source": source,
                    "target_url": attached_targets.get(source).url if source in attached_targets else None,
                    "request_id": request_id,
                    "method": http_method,
                    "url": url,
                    "backend_api": parsed["is_backend_api"],
                    "path": parsed["path"],
                    "headers": _sanitize_headers(req.get("headers")),
                }
                _write_jsonl(events_path, ev)

                if parsed["is_conversation"] and http_method.upper() == "POST":
                    # Extract safe route fields from request body.
                    route: dict[str, Any] = {}
                    try:
                        post = client.call("Network.getRequestPostData", {"requestId": request_id}, timeout_s=5.0)
                        post_data = str(post.get("postData") or "")
                        route = _extract_request_route(post_data)
                    except Exception as exc:
                        route = {"post_data_error": type(exc).__name__}

                    conv_posts += 1
                    observed[(source, request_id)] = {"index": conv_posts, "url": url, "sent_at_ms": _now_ms(), "route": route}
                    _write_jsonl(
                        conv_path,
                        {
                            "t_ms": _now_ms(),
                            "kind": "conversation_post",
                            "index": conv_posts,
                            "source": source,
                            "request_id": request_id,
                            "url": url,
                            "request_route": route,
                        },
                    )

            elif method == "Network.responseReceived":
                request_id = str(params.get("requestId") or "")
                if not request_id:
                    continue
                resp = params.get("response") if isinstance(params.get("response"), dict) else {}
                url = str(resp.get("url") or "")
                parsed = _classify_url(url)
                if not args.verbose and not parsed["is_backend_api"]:
                    continue

                ev = {
                    "t_ms": _now_ms(),
                    "kind": "response",
                    "source": source,
                    "request_id": request_id,
                    "url": url,
                    "status": resp.get("status"),
                    "status_text": resp.get("statusText"),
                    "headers": _sanitize_headers(resp.get("headers")),
                    "backend_api": parsed["is_backend_api"],
                    "path": parsed["path"],
                }
                _write_jsonl(events_path, ev)

                key = (source, request_id)
                if parsed["is_conversation"] and key in observed:
                    observed[key]["status"] = resp.get("status")

            elif method == "Network.loadingFinished":
                request_id = str(params.get("requestId") or "")
                if not request_id:
                    continue
                key = (source, request_id)
                info = observed.get(key)
                if not info:
                    continue

                # Pull response body at completion to extract resolved model routing fields.
                resp_meta: dict[str, Any] = {}
                try:
                    body = client.call("Network.getResponseBody", {"requestId": request_id}, timeout_s=8.0)
                    body_text = str(body.get("body") or "")
                    resp_meta = _extract_response_meta(body_text)
                except Exception as exc:
                    resp_meta = {"response_body_error": type(exc).__name__}

                _write_jsonl(
                    conv_path,
                    {
                        "t_ms": _now_ms(),
                        "kind": "conversation_response_meta",
                        "index": info.get("index"),
                        "source": source,
                        "request_id": request_id,
                        "response_meta": resp_meta,
                        "http_status": info.get("status"),
                    },
                )
                # Prevent repeated body pulls if extra loadingFinished events fire.
                observed.pop(key, None)

            if conv_posts >= max_posts and not observed:
                break

        _write_json(
            out_dir / "summary.json",
            {
                "finished_at_ms": _now_ms(),
                "timeout_seconds": int(args.timeout_seconds),
                "max_conversation_posts": int(args.max_conversation_posts),
                "captured_conversation_posts": conv_posts,
                "out_dir": str(out_dir),
            },
        )

        report_lines = [
            "# ChatGPT CDP Sniff Report",
            "",
            f"- Output: `{out_dir}`",
            f"- Attached targets: `{out_dir / 'attached_targets.json'}`",
            f"- Events: `{out_dir / 'net_events.jsonl'}`",
            f"- Conversation posts: `{out_dir / 'conversation_posts.jsonl'}`",
            "",
            "Next:",
            "- Inspect `conversation_posts.jsonl` for `request_route.thinking_effort`/`reasoning_effort` and compare with `response_meta.message_metadata.resolved_model_slug`.",
        ]
        (out_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    finally:
        for c in clients.values():
            c.close()

    print(str(out_dir))
    return 0


def _resolve_http_base_from_ws(ws_url: str) -> str:
    # ws://host:port/devtools/browser/<id> -> http://host:port
    lower = ws_url.lower()
    if not lower.startswith(("ws://", "wss://")):
        return "http://127.0.0.1:9222"
    scheme = "http" if lower.startswith("ws://") else "https"
    rest = ws_url.split("://", 1)[1]
    hostport = rest.split("/", 1)[0]
    return f"{scheme}://{hostport}"


def _classify_url(url: str) -> dict[str, Any]:
    # Keep it tiny: we only need path classification for ChatGPT backend-api.
    try:
        from urllib.parse import urlparse

        p = urlparse(url)
        path = p.path or ""
    except Exception:
        path = ""
    is_backend = "/backend-api/" in path
    norm = path.rstrip("/")
    is_conversation = is_backend and norm in {"/backend-api/conversation", "/backend-api/f/conversation"}
    return {
        "path": path,
        "is_backend_api": is_backend,
        "is_conversation": is_conversation,
    }


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
