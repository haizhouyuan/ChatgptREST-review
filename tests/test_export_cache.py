"""Tests for export result caching (Opt-2).

Verifies that the ``cache`` parameter on ``_maybe_export_conversation`` prevents
duplicate MCP calls within a single ``_run_once`` cycle.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.config import load_config
from chatgptrest.worker.worker import _maybe_export_conversation


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "1")
    monkeypatch.setenv("CHATGPTREST_CONVERSATION_EXPORT_OK_COOLDOWN_SECONDS", "0")
    monkeypatch.setenv("CHATGPTREST_CONVERSATION_EXPORT_GLOBAL_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("CHATGPTREST_DRIVER_MODE", "internal_mcp")
    return {"tmp_path": tmp_path, "db_path": db_path, "artifacts_dir": artifacts_dir}


def _make_export_content() -> str:
    return json.dumps(
        {
            "export_kind": "dom_messages",
            "conversation_url": "https://chatgpt.com/c/test",
            "messages": [
                {"role": "user", "text": "hi"},
                {"role": "assistant", "text": "hello world"},
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


class _CountingToolCaller:
    """Tracks how many export calls were actually made."""

    def __init__(self) -> None:
        self.call_count = 0

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
        assert tool_name == "chatgpt_web_conversation_export"
        self.call_count += 1
        dst = tool_args.get("dst_path")
        assert isinstance(dst, str) and dst
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        Path(dst).write_text(_make_export_content() + "\n", encoding="utf-8")
        return {"ok": True, "export_path": dst}


def test_export_cache_prevents_duplicate_call(env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """Second non-force call with a populated cache should skip MCP entirely."""
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}},
        headers={"Idempotency-Key": "cache-test-1"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    cfg = load_config()
    tool_caller = _CountingToolCaller()
    cache: dict[str, Any] = {}

    # First call — should actually export.
    asyncio.run(
        _maybe_export_conversation(
            cfg=cfg,
            job_id=job_id,
            conversation_url="https://chatgpt.com/c/test",
            tool_caller=tool_caller,  # type: ignore[arg-type]
            cache=cache,
        )
    )
    assert tool_caller.call_count == 1
    assert cache.get("ok") is True

    # Second call (non-force) — should skip due to cache.
    asyncio.run(
        _maybe_export_conversation(
            cfg=cfg,
            job_id=job_id,
            conversation_url="https://chatgpt.com/c/test",
            tool_caller=tool_caller,  # type: ignore[arg-type]
            cache=cache,
        )
    )
    assert tool_caller.call_count == 1  # Still 1, no new call.


def test_export_cache_force_bypasses(env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """force=True should bypass cache and make an actual MCP call."""
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}},
        headers={"Idempotency-Key": "cache-test-force-1"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    cfg = load_config()
    tool_caller = _CountingToolCaller()
    cache: dict[str, Any] = {"ok": True}  # Pre-populated cache.

    # force=True — ignore cache, call MCP.
    asyncio.run(
        _maybe_export_conversation(
            cfg=cfg,
            job_id=job_id,
            conversation_url="https://chatgpt.com/c/test",
            tool_caller=tool_caller,  # type: ignore[arg-type]
            force=True,
            cache=cache,
        )
    )
    assert tool_caller.call_count == 1


def test_export_no_cache_param_works(env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling without cache= (legacy) still works fine."""
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}},
        headers={"Idempotency-Key": "cache-test-none-1"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    cfg = load_config()
    tool_caller = _CountingToolCaller()

    # No cache param — should not crash.
    asyncio.run(
        _maybe_export_conversation(
            cfg=cfg,
            job_id=job_id,
            conversation_url="https://chatgpt.com/c/test",
            tool_caller=tool_caller,  # type: ignore[arg-type]
        )
    )
    assert tool_caller.call_count == 1
