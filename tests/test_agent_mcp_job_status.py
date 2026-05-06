from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace


def _load_agent_mcp_module():
    import chatgptrest.mcp.agent_mcp as mod

    return importlib.reload(mod)


def test_automation_job_status_delegates_to_canonical_job_kernel(monkeypatch):
    mod = _load_agent_mcp_module()
    captured = {}

    async def fake_job_get(job_id: str, ctx=None):  # noqa: ANN001
        captured["job_id"] = job_id
        captured["ctx"] = ctx
        return {"ok": True, "job_id": job_id, "status": "in_progress"}

    monkeypatch.setattr(
        mod,
        "_job_kernel_module",
        lambda: SimpleNamespace(chatgptrest_job_get=fake_job_get),
    )

    ctx = object()
    result = asyncio.run(mod.automation_job_status(ctx=ctx, job_id=" job-status-1 "))

    assert result == {"ok": True, "job_id": "job-status-1", "status": "in_progress"}
    assert captured == {"job_id": "job-status-1", "ctx": ctx}


def test_automation_conversation_fetch_submits_read_only_export(monkeypatch):
    mod = _load_agent_mcp_module()
    captured = {}

    async def fake_job_create(**kwargs):  # noqa: ANN003
        captured["job_create"] = kwargs
        return {"job_id": "conversation-export-1", "status": "queued"}

    async def fake_wait_background(**kwargs):  # noqa: ANN003
        captured["wait_background"] = kwargs
        return {"ok": True, "watch_id": "watch-1"}

    monkeypatch.setattr(
        mod,
        "_job_kernel_module",
        lambda: SimpleNamespace(
            chatgptrest_job_create=fake_job_create,
            chatgptrest_job_wait_background_start=fake_wait_background,
        ),
    )

    result = asyncio.run(
        mod.automation_conversation_fetch(
            ctx=None,
            conversation_url="https://chat.openai.com/c/abc123456?model=gpt-5",
            idempotency_key="manual-fetch-1",
            backend_mode="auto",
        )
    )

    assert result["job_id"] == "conversation-export-1"
    assert result["conversation_url"] == "https://chatgpt.com/c/abc123456"
    assert result["conversation_id"] == "abc123456"
    assert result["backend_mode"] == "auto"
    assert result["next_action"]["fallback_tools"] == [
        "automation_result",
        "automation_conversation_get",
        "automation_conversation_find",
        "automation_job_events",
    ]

    create_kwargs = captured["job_create"]
    assert create_kwargs["kind"] == "chatgpt_web.conversation_export"
    assert create_kwargs["input"] == {"conversation_url": "https://chatgpt.com/c/abc123456"}
    assert create_kwargs["params"]["backend_mode"] == "auto"
    assert create_kwargs["params"]["manual_harvest"] is True
    assert create_kwargs["params"]["read_only_harvest"] is True
    assert create_kwargs["client"]["name"] == "chatgptrest_manual_conversation_fetch"
    assert captured["wait_background"]["job_id"] == "conversation-export-1"
    assert captured["wait_background"]["auto_codex_autofix"] is False


def test_automation_conversation_get_delegates_to_conversation_export(monkeypatch):
    mod = _load_agent_mcp_module()
    captured = {}

    async def fake_conversation_get(job_id: str, offset: int, max_chars: int, ctx=None):  # noqa: ANN001
        captured.update({"job_id": job_id, "offset": offset, "max_chars": max_chars, "ctx": ctx})
        return {"ok": True, "job_id": job_id, "text": "conversation"}

    monkeypatch.setattr(
        mod,
        "_job_kernel_module",
        lambda: SimpleNamespace(chatgptrest_conversation_get=fake_conversation_get),
    )

    ctx = object()
    result = asyncio.run(
        mod.automation_conversation_get(ctx=ctx, job_id=" export-job-1 ", offset=10, max_chars=1234)
    )

    assert result == {"ok": True, "job_id": "export-job-1", "text": "conversation"}
    assert captured == {"job_id": "export-job-1", "offset": 10, "max_chars": 1234, "ctx": ctx}


def test_automation_conversation_find_normalizes_url_and_delegates(monkeypatch):
    mod = _load_agent_mcp_module()
    captured = {}

    def fake_find_jobs(*, conversation_url: str, conversation_id: str, limit: int):
        captured.update(
            {
                "conversation_url": conversation_url,
                "conversation_id": conversation_id,
                "limit": limit,
            }
        )
        return [{"job_id": "export-job-1"}]

    monkeypatch.setattr(mod, "_manual_conversation_find_jobs", fake_find_jobs)

    result = asyncio.run(
        mod.automation_conversation_find(
            ctx=None,
            conversation_url="https://chat.openai.com/c/abc123456?foo=1",
            limit=5,
        )
    )

    assert result["ok"] is True
    assert result["conversation_url"] == "https://chatgpt.com/c/abc123456"
    assert result["count"] == 1
    assert result["matches"] == [{"job_id": "export-job-1"}]
    assert captured == {
        "conversation_url": "https://chatgpt.com/c/abc123456",
        "conversation_id": "abc123456",
        "limit": 5,
    }
