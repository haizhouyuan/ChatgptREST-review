#!/usr/bin/env python3
"""Batch fetch ChatGPT conversations via MCP automation_conversation_fetch.

Usage:
    PYTHONPATH=/vol1/1000/projects/ChatgptREST ./.venv/bin/python ops/fetch_conversations_mcp.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession

BASE_URL = "http://127.0.0.1:18712/mcp"
OUT_DIR = Path(__file__).resolve().parents[1] / "archives" / "conversations" / "2026-05-01"

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

POLL_INTERVAL = 3.0
MAX_WAIT_SECONDS = 600


def _cid(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


async def _call_tool(session: ClientSession, name: str, arguments: dict[str, Any]) -> Any:
    result = await session.call_tool(name, arguments=arguments)
    # Extract text content from result
    for content in result.content:
        if content.type == "text":
            return json.loads(content.text)
    return {}


async def fetch_conversation(session: ClientSession, url: str) -> dict[str, Any]:
    cid = _cid(url)
    print(f"Fetching {cid}...")

    # 1. Submit export job via MCP
    result = await _call_tool(session, "automation_conversation_fetch", {
        "conversation_url": url,
        "timeout_seconds": 120,
        "backend_mode": "dom_only",
        "auto_wait": True,
        "notify_done": True,
    })

    job_id = str(result.get("job_id") or "").strip()
    if not job_id:
        print(f"  FAILED: no job_id in response: {json.dumps(result, ensure_ascii=False)[:300]}")
        return {"url": url, "status": "no_job_id", "detail": result}

    print(f"  Submitted job {job_id[:24]}...")

    # 2. Wait for completion
    start = time.time()
    final_status = ""
    while True:
        status_result = await _call_tool(session, "automation_job_status", {"job_id": job_id})
        status = str(status_result.get("status") or "").strip().lower()
        final_status = status
        if status in {"completed", "error", "canceled", "blocked", "needs_followup"}:
            break
        elapsed = time.time() - start
        if elapsed > MAX_WAIT_SECONDS:
            return {"url": url, "status": "timeout", "job_id": job_id}
        print(f"  ... status={status}, waited {int(elapsed)}s")
        await asyncio.sleep(POLL_INTERVAL)

    if final_status != "completed":
        print(f"  FAILED: job status={final_status}")
        return {"url": url, "status": final_status, "job_id": job_id}

    # 3. Fetch conversation chunks using automation_conversation_get
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{cid}.json"

    all_text = ""
    offset = 0
    chunk_count = 0
    while True:
        chunk_result = await _call_tool(session, "automation_conversation_get", {
            "job_id": job_id,
            "offset": offset,
            "max_chars": 80000,
        })
        chunk_count += 1
        chunk = str(chunk_result.get("chunk") or chunk_result.get("text") or chunk_result.get("content") or "")
        if not chunk:
            break
        all_text += chunk
        next_offset = chunk_result.get("next_offset")
        done = bool(chunk_result.get("done"))
        if done or next_offset is None:
            break
        offset = int(next_offset)
        # Safety: if we got less than max_chars and no next_offset, break on next loop
        if chunk_count > 100:
            print(f"  WARNING: too many chunks, breaking")
            break

    if not all_text:
        # Fallback to automation_result
        result_data = await _call_tool(session, "automation_result", {
            "job_id": job_id,
            "include_answer": True,
            "max_answer_chars": 24000,
        })
        all_text = str(result_data.get("answer") or result_data.get("text") or result_data.get("content") or "")

    out_path.write_text(all_text, encoding="utf-8")
    print(f"  SAVED -> {out_path} ({len(all_text)} chars, {chunk_count} chunks)")

    # Validate JSON if it looks like JSON
    quality = {"chars": len(all_text), "chunks": chunk_count}
    if all_text.strip().startswith("{"):
        try:
            parsed = json.loads(all_text)
            quality["json_valid"] = True
            if "conversation_id" in parsed:
                quality["has_conversation_id"] = True
            if "mapping" in parsed or "title" in parsed:
                quality["has_structure"] = True
        except json.JSONDecodeError as exc:
            quality["json_valid"] = False
            quality["json_error"] = str(exc)
            print(f"  WARNING: JSON parse error: {exc}")
    else:
        quality["json_valid"] = False
        quality["note"] = "Not JSON (likely markdown)"

    return {"url": url, "status": "ok", "job_id": job_id, "path": str(out_path), "quality": quality}


async def main() -> int:
    print(f"Output dir: {OUT_DIR}")
    print(f"MCP URL: {BASE_URL}")
    print(f"Conversations to fetch: {len(CONVERSATION_URLS)}")
    print()

    results: list[dict[str, Any]] = []

    async with streamable_http_client(BASE_URL) as (read_stream, write_stream, _get_sid):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"Connected. Available tools: {len(tools.tools)}")
            tool_names = [t.name for t in tools.tools]
            if "automation_conversation_fetch" not in tool_names:
                print("ERROR: automation_conversation_fetch not available in MCP tools")
                return 1
            print()

            for i, url in enumerate(CONVERSATION_URLS, 1):
                print(f"[{i}/{len(CONVERSATION_URLS)}] {url}")
                try:
                    result = await fetch_conversation(session, url)
                    results.append(result)
                except Exception as exc:
                    print(f"  ERROR: {type(exc).__name__}: {exc}")
                    results.append({"url": url, "status": "exception", "error": str(exc)})
                print()

    ok_count = sum(1 for r in results if r.get("status") == "ok")
    print(f"Done: {ok_count}/{len(CONVERSATION_URLS)} succeeded")

    summary_path = OUT_DIR / "_summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Summary: {summary_path}")

    # Print quality report
    print("\n--- Quality Report ---")
    for r in results:
        cid = _cid(r["url"])
        if r.get("status") == "ok":
            q = r.get("quality", {})
            status_emoji = "OK" if q.get("json_valid") else "WARN"
            print(f"  {status_emoji} {cid}: {q.get('chars', 0)} chars, {q.get('chunks', 0)} chunks")
        else:
            print(f"  FAIL {cid}: {r.get('status')} - {r.get('error', '')}")

    return 0 if ok_count == len(CONVERSATION_URLS) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
