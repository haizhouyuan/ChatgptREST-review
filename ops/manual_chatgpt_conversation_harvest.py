#!/usr/bin/env python3
"""Discover human ChatGPT Web conversations and enqueue read-only exports.

The scanner only inspects the local Chrome CDP page list and optionally submits
`chatgpt_web.conversation_export` jobs. It never sends a prompt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CHATGPT_CONVERSATION_URL_RE = re.compile(
    r"^https?://(?:chatgpt\.com|chat\.openai\.com)/c/([A-Za-z0-9_-]{8,})(?:[/?#].*)?$",
    re.IGNORECASE,
)


def _normalize_chatgpt_conversation_url(value: str) -> tuple[str, str]:
    raw = str(value or "").strip()
    match = CHATGPT_CONVERSATION_URL_RE.match(raw)
    if not match:
        raise ValueError(f"not a ChatGPT conversation URL: {raw}")
    conversation_id = str(match.group(1) or "").strip()
    return f"https://chatgpt.com/c/{conversation_id}", conversation_id


def _default_cdp_url() -> str:
    raw = str(os.environ.get("CHATGPT_CDP_URL") or "").strip()
    if raw:
        return raw.rstrip("/")
    port = str(os.environ.get("CHROME_DEBUG_PORT") or "9222").strip() or "9222"
    return f"http://127.0.0.1:{port}"


def _http_json(
    *,
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 10.0,
) -> Any:
    data: bytes | None = None
    req_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(str(url), data=data, headers=req_headers, method=str(method).upper())
    parsed = urllib.parse.urlparse(str(url))
    opener = (
        urllib.request.build_opener(urllib.request.ProxyHandler({}))
        if str(parsed.hostname or "").lower() in {"127.0.0.1", "localhost"}
        else None
    )
    try:
        if opener is None:
            with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
                raw = resp.read()
        else:
            with opener.open(req, timeout=float(timeout_seconds)) as resp:
                raw = resp.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw) if raw.strip() else {}
        except Exception:
            detail = raw[:1000]
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {detail}") from exc
    text = raw.decode("utf-8", errors="replace")
    return json.loads(text) if text.strip() else {}


def discover_open_conversations(*, cdp_url: str, timeout_seconds: float) -> list[dict[str, Any]]:
    pages = _http_json(method="GET", url=f"{cdp_url.rstrip('/')}/json/list", timeout_seconds=timeout_seconds)
    if not isinstance(pages, list):
        return []
    out: dict[str, dict[str, Any]] = {}
    for page in pages:
        if not isinstance(page, dict):
            continue
        raw_url = str(page.get("url") or "").strip()
        if not raw_url:
            continue
        try:
            normalized_url, conversation_id = _normalize_chatgpt_conversation_url(raw_url)
        except ValueError:
            continue
        out[conversation_id] = {
            "conversation_id": conversation_id,
            "conversation_url": normalized_url,
            "page_title": str(page.get("title") or "").strip(),
            "page_id": str(page.get("id") or "").strip(),
            "source": "cdp_json_list",
        }
    return sorted(out.values(), key=lambda item: item.get("conversation_id") or "")


def _load_state(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"version": 1, "conversations": {}}


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _idempotency_key(*, conversation_url: str, interval_seconds: int) -> str:
    bucket_seconds = max(60, min(int(interval_seconds or 300), 24 * 60 * 60))
    bucket = int(time.time() // bucket_seconds)
    digest = hashlib.sha256(conversation_url.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"manual-harvest-chatgpt-conversation-{digest}-{bucket}"


def _auth_headers() -> dict[str, str]:
    client_name = str(os.environ.get("CHATGPTREST_MANUAL_HARVEST_CLIENT_NAME") or "chatgptrest-mcp").strip()
    client_instance = str(os.environ.get("CHATGPTREST_CLIENT_INSTANCE") or f"manual-harvest-{uuid.uuid4().hex[:8]}").strip()
    headers = {
        "User-Agent": "chatgptrest-manual-conversation-harvest/1.0",
        "X-Client-Name": client_name,
        "X-Client-Instance": client_instance,
        "X-Request-ID": f"manual-harvest-{uuid.uuid4().hex}",
    }
    token = str(os.environ.get("CHATGPTREST_API_TOKEN") or os.environ.get("OPENMIND_API_KEY") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def submit_export_job(
    *,
    base_url: str,
    conversation_url: str,
    conversation_id: str,
    timeout_seconds: int,
    backend_mode: str,
    min_submit_interval_seconds: int,
) -> dict[str, Any]:
    mode = str(backend_mode or "dom_only").strip().lower()
    if mode not in {"dom_only", "auto"}:
        mode = "dom_only"
    body = {
        "kind": "chatgpt_web.conversation_export",
        "input": {"conversation_url": conversation_url},
        "params": {
            "timeout_seconds": int(timeout_seconds),
            "backend_mode": mode,
            "allow_dom_fallback": True,
            "manual_harvest": True,
            "read_only_harvest": True,
            "answer_format": "markdown",
        },
        "client": {
            "name": "chatgptrest_manual_conversation_harvest",
            "source": "ops/manual_chatgpt_conversation_harvest.py",
            "conversation_id": conversation_id,
            "conversation_url": conversation_url,
        },
    }
    headers = _auth_headers()
    headers["Idempotency-Key"] = _idempotency_key(
        conversation_url=conversation_url,
        interval_seconds=int(min_submit_interval_seconds),
    )
    result = _http_json(
        method="POST",
        url=f"{base_url.rstrip('/')}/v1/jobs",
        body=body,
        headers=headers,
        timeout_seconds=20.0,
    )
    if not isinstance(result, dict):
        raise RuntimeError(f"unexpected /v1/jobs response: {type(result).__name__}")
    return result


def _collect_targets(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    targets: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    cdp_urls = [str(args.cdp_url).rstrip("/")]
    fallback_cdp_url = str(args.fallback_cdp_url or "").strip().rstrip("/")
    if fallback_cdp_url and fallback_cdp_url not in cdp_urls:
        cdp_urls.append(fallback_cdp_url)
    cdp_errors: list[dict[str, Any]] = []
    for cdp_url in cdp_urls:
        try:
            for item in discover_open_conversations(cdp_url=cdp_url, timeout_seconds=float(args.cdp_timeout_seconds)):
                item["cdp_url"] = cdp_url
                targets[item["conversation_id"]] = item
            cdp_errors = []
            break
        except Exception as exc:
            cdp_errors.append(
                {
                    "stage": "cdp_discovery",
                    "cdp_url": cdp_url,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:500],
                }
            )
    errors.extend(cdp_errors[-1:])

    for raw_url in args.url or []:
        try:
            normalized_url, conversation_id = _normalize_chatgpt_conversation_url(raw_url)
            targets[conversation_id] = {
                "conversation_id": conversation_id,
                "conversation_url": normalized_url,
                "source": "explicit_url",
            }
        except Exception as exc:
            errors.append({"stage": "explicit_url", "url": raw_url, "error_type": type(exc).__name__, "error": str(exc)})

    return sorted(targets.values(), key=lambda item: item.get("conversation_id") or ""), errors


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    now = time.time()
    state_path = Path(args.state_path).expanduser()
    if not state_path.is_absolute():
        state_path = REPO_ROOT / state_path
    state = _load_state(state_path)
    conversations = state.setdefault("conversations", {})
    if not isinstance(conversations, dict):
        conversations = {}
        state["conversations"] = conversations

    targets, errors = _collect_targets(args)
    submitted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for target in targets:
        conversation_id = str(target["conversation_id"])
        conversation_url = str(target["conversation_url"])
        prior = conversations.get(conversation_id) if isinstance(conversations.get(conversation_id), dict) else {}
        last_submitted_at = float(prior.get("last_submitted_at") or 0)
        due = (now - last_submitted_at) >= int(args.min_submit_interval_seconds)
        if not args.submit:
            skipped.append({**target, "reason": "dry_run"})
            continue
        if not due:
            skipped.append(
                {
                    **target,
                    "reason": "min_submit_interval",
                    "retry_after_seconds": int(int(args.min_submit_interval_seconds) - (now - last_submitted_at)),
                    "last_job_id": prior.get("last_job_id"),
                }
            )
            continue
        try:
            job = submit_export_job(
                base_url=args.base_url,
                conversation_url=conversation_url,
                conversation_id=conversation_id,
                timeout_seconds=int(args.timeout_seconds),
                backend_mode=str(args.backend_mode),
                min_submit_interval_seconds=int(args.min_submit_interval_seconds),
            )
            item = {**target, "job_id": str(job.get("job_id") or ""), "status": str(job.get("status") or "")}
            submitted.append(item)
            conversations[conversation_id] = {
                "conversation_url": conversation_url,
                "last_seen_at": now,
                "last_submitted_at": now,
                "last_job_id": item["job_id"],
                "last_status": item["status"],
            }
        except Exception as exc:
            errors.append(
                {
                    **target,
                    "stage": "submit",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1000],
                }
            )
            conversations[conversation_id] = {
                **prior,
                "conversation_url": conversation_url,
                "last_seen_at": now,
                "last_error_at": now,
                "last_error": str(exc)[:1000],
            }

    state["updated_at"] = now
    _write_state(state_path, state)
    fatal_errors = [item for item in errors if item.get("stage") != "cdp_discovery"]
    return {
        "ok": not fatal_errors,
        "ts": now,
        "submit": bool(args.submit),
        "cdp_url": args.cdp_url,
        "target_count": len(targets),
        "submitted": submitted,
        "skipped": skipped,
        "errors": errors,
        "state_path": str(state_path),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run one scan and exit.")
    parser.add_argument("--submit", action="store_true", help="Submit read-only conversation export jobs.")
    parser.add_argument("--url", action="append", default=[], help="Explicit ChatGPT conversation URL to include.")
    parser.add_argument("--cdp-url", default=_default_cdp_url())
    parser.add_argument(
        "--fallback-cdp-url",
        default=os.environ.get("CHATGPTREST_MANUAL_HARVEST_FALLBACK_CDP_URL", "http://127.0.0.1:9226"),
    )
    parser.add_argument("--cdp-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--base-url", default=os.environ.get("CHATGPTREST_BASE_URL", "http://127.0.0.1:18711"))
    parser.add_argument(
        "--state-path",
        default="artifacts/monitor/manual_chatgpt_conversation_harvest/state.json",
    )
    parser.add_argument("--backend-mode", choices=["dom_only", "auto"], default="dom_only")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--min-submit-interval-seconds", type=int, default=300)
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.once:
        result = run_once(args)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 2

    while True:
        result = run_once(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        time.sleep(max(30, int(args.interval_seconds)))


if __name__ == "__main__":
    raise SystemExit(main())
