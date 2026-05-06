#!/usr/bin/env python3
"""Batch fetch ChatGPT conversation exports via ChatgptREST API.

Usage:
    PYTHONPATH=. ./.venv/bin/python ops/fetch_conversations.py

Requires CHATGPTREST_API_TOKEN or OPENMIND_API_KEY in environment.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

# ── Config ──
BASE_URL = os.environ.get("CHATGPTREST_BASE_URL", "http://127.0.0.1:18711").rstrip("/")
TOKEN = os.environ.get("CHATGPTREST_API_TOKEN") or os.environ.get("OPENMIND_API_KEY", "")
TIMEOUT_SECONDS = 300
POLL_INTERVAL = 3.0
MAX_WAIT_SECONDS = 600

# Your conversation URLs
CONVERSATION_URLS = [
    "https://chatgpt.com/c/69f31386-03e0-83e8-a93a-57846b97e760",
    "https://chatgpt.com/c/69f30acc-c994-83e8-9763-4b19610fac55",
    "https://chatgpt.com/c/69f2dd9e-bfec-83e8-acab-77a18360a739",
    "https://chatgpt.com/c/69f2dd9e-dc84-83e8-aef2-e621bb4642ec",
    "https://chatgpt.com/c/69f2da65-f6c8-83e8-bd91-6c70e924ec91",
    "https://chatgpt.com/c/69f2d992-22f0-83e8-930d-a0150e32cc6d",
    "https://chatgpt.com/c/69f1e423-f958-83e8-88f3-e0d487e3cc7f",
    "https://chatgpt.com/c/69f20cd0-9ab4-83e8-9827-ac9c94728bfe",
    "https://chatgpt.com/c/69f17ad5-f254-83e8-a63b-4a43c6a064d7",
    "https://chatgpt.com/c/69f05784-b010-83e8-92ca-bc4e45a20666",
]

OUT_DIR = Path(__file__).resolve().parents[1] / "archives" / "conversations" / "2026-05-01"


def _http_json(
    *,
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 30.0,
) -> Any:
    data: bytes | None = None
    req_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(str(url), data=data, headers=req_headers, method=str(method).upper())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=float(timeout_seconds)) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        text = raw.decode("utf-8", errors="replace")
        try:
            detail = json.loads(text) if text.strip() else {}
        except Exception:
            detail = text[:1000]
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {detail}") from exc
    text = raw.decode("utf-8", errors="replace")
    return json.loads(text) if text.strip() else {}


def _auth_headers() -> dict[str, str]:
    headers = {
        "User-Agent": "chatgptrest-conversation-fetch/1.0",
        "X-Client-Name": "chatgptrest_manual_fetch",
        "X-Client-Instance": f"fetch-{uuid.uuid4().hex[:8]}",
        "X-Request-ID": f"fetch-{uuid.uuid4().hex[:12]}",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    return headers


def _conversation_id(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def _idempotency_key(url: str) -> str:
    cid = _conversation_id(url)
    return f"manual-fetch-{cid}-{uuid.uuid4().hex[:8]}"


def submit_export(url: str) -> dict[str, Any]:
    cid = _conversation_id(url)
    body = {
        "kind": "chatgpt_web.conversation_export",
        "input": {"conversation_url": url},
        "params": {
            "timeout_seconds": TIMEOUT_SECONDS,
            "backend_mode": "dom_only",
            "allow_dom_fallback": True,
            "manual_harvest": True,
            "read_only_harvest": True,
            "answer_format": "markdown",
        },
        "client": {
            "name": "chatgptrest_manual_fetch",
            "source": "ops/fetch_conversations.py",
            "conversation_url": url,
        },
    }
    headers = _auth_headers()
    headers["Idempotency-Key"] = _idempotency_key(url)
    return _http_json(
        method="POST",
        url=f"{BASE_URL}/v1/jobs",
        body=body,
        headers=headers,
        timeout_seconds=20.0,
    )


def get_job(job_id: str) -> dict[str, Any]:
    return _http_json(
        method="GET",
        url=f"{BASE_URL}/v1/jobs/{urllib.parse.quote(job_id)}",
        headers=_auth_headers(),
        timeout_seconds=20.0,
    )


def get_conversation(job_id: str, offset: int = 0, max_chars: int = 80000) -> dict[str, Any]:
    qs = urllib.parse.urlencode({"offset": offset, "max_chars": max_chars}, doseq=False)
    return _http_json(
        method="GET",
        url=f"{BASE_URL}/v1/jobs/{urllib.parse.quote(job_id)}/conversation?{qs}",
        headers=_auth_headers(),
        timeout_seconds=30.0,
    )


def wait_for_job(job_id: str) -> dict[str, Any]:
    start = time.time()
    while True:
        job = get_job(job_id)
        status = str(job.get("status") or "").strip().lower()
        if status in {"completed", "error", "canceled", "blocked", "needs_followup"}:
            return job
        elapsed = time.time() - start
        if elapsed > MAX_WAIT_SECONDS:
            raise TimeoutError(f"Job {job_id} did not complete within {MAX_WAIT_SECONDS}s")
        print(f"  ... job {job_id[:20]}... status={status}, waited {int(elapsed)}s")
        time.sleep(POLL_INTERVAL)


def save_conversation(job_id: str, cid: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{cid}.md"

    # Fetch in chunks
    all_text = ""
    offset = 0
    while True:
        chunk = get_conversation(job_id, offset=offset, max_chars=80000)
        if not isinstance(chunk, dict):
            break
        text = str(chunk.get("text") or chunk.get("content") or "")
        if not text:
            break
        all_text += text
        offset += len(text)
        # If we got less than max_chars, we're done
        if len(text) < 80000:
            break

    if not all_text:
        # Fallback: try answer endpoint
        answer = _http_json(
            method="GET",
            url=f"{BASE_URL}/v1/jobs/{urllib.parse.quote(job_id)}/answer?offset=0&max_chars=80000",
            headers=_auth_headers(),
            timeout_seconds=30.0,
        )
        if isinstance(answer, dict):
            all_text = str(answer.get("text") or answer.get("content") or answer.get("answer") or "")

    out_path.write_text(all_text, encoding="utf-8")
    return out_path


def main() -> int:
    if not TOKEN:
        print("ERROR: Set CHATGPTREST_API_TOKEN or OPENMIND_API_KEY", file=sys.stderr)
        return 1

    print(f"Output dir: {OUT_DIR}")
    print(f"Base URL: {BASE_URL}")
    print(f"Conversations to fetch: {len(CONVERSATION_URLS)}")
    print()

    results: list[dict[str, Any]] = []

    for i, url in enumerate(CONVERSATION_URLS, 1):
        cid = _conversation_id(url)
        print(f"[{i}/{len(CONVERSATION_URLS)}] Fetching {cid}...")
        try:
            job = submit_export(url)
            job_id = str(job.get("job_id") or "").strip()
            if not job_id:
                print(f"  FAILED: no job_id in response: {json.dumps(job, ensure_ascii=False)[:500]}")
                results.append({"url": url, "status": "no_job_id", "detail": job})
                continue

            print(f"  Submitted job {job_id[:24]}...")
            final_job = wait_for_job(job_id)
            status = str(final_job.get("status") or "").strip().lower()

            if status == "completed":
                out_path = save_conversation(job_id, cid)
                print(f"  SAVED -> {out_path}")
                results.append({"url": url, "status": "ok", "job_id": job_id, "path": str(out_path)})
            else:
                print(f"  FAILED: job status={status}, error={final_job.get('last_error')}")
                results.append({"url": url, "status": status, "job_id": job_id, "detail": final_job})

        except Exception as exc:
            print(f"  ERROR: {type(exc).__name__}: {exc}")
            results.append({"url": url, "status": "exception", "error": str(exc)})

        print()

    # Summary
    ok_count = sum(1 for r in results if r.get("status") == "ok")
    print(f"Done: {ok_count}/{len(CONVERSATION_URLS)} succeeded")

    summary_path = OUT_DIR / "_summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Summary: {summary_path}")
    return 0 if ok_count == len(CONVERSATION_URLS) else 1


if __name__ == "__main__":
    sys.exit(main())
