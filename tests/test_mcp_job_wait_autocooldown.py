from __future__ import annotations

import asyncio
import time

import pytest


def _load_mcp_server_module():
    import chatgptrest.mcp.server as mod

    return mod


def test_mcp_job_wait_keeps_waiting_through_cooldown(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()

    responses = [
        {"ok": True, "job_id": "j1", "kind": "chatgpt_web.ask", "status": "cooldown", "retry_after_seconds": 0},
        {"ok": True, "job_id": "j1", "kind": "chatgpt_web.ask", "status": "cooldown", "retry_after_seconds": 0},
        {"ok": True, "job_id": "j1", "kind": "chatgpt_web.ask", "status": "completed"},
    ]
    calls: list[str] = []

    def fake_http_json(*, method: str, url: str, **_kwargs):  # noqa: ARG001
        calls.append(f"{method} {url}")
        return responses.pop(0)

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    async def fake_sleep(_seconds: float):  # noqa: ARG001
        return None

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)

    job = asyncio.run(mod.chatgptrest_job_wait("j1", timeout_seconds=10, poll_seconds=0.2))
    assert job["status"] == "completed"
    assert len(calls) == 3


def test_mcp_job_wait_returns_cooldown_if_retry_after_exceeds_deadline(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()

    def fake_http_json(*, method: str, url: str, **_kwargs):  # noqa: ARG001
        return {"ok": True, "job_id": "j1", "kind": "chatgpt_web.ask", "status": "cooldown", "retry_after_seconds": 120}

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    sleeps: list[float] = []

    async def fake_sleep(seconds: float):
        sleeps.append(float(seconds))

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)

    job = asyncio.run(mod.chatgptrest_job_wait("j1", timeout_seconds=1, poll_seconds=0.2))
    assert job["status"] == "cooldown"
    assert sleeps == []


def test_mcp_job_wait_keeps_waiting_through_in_progress(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()

    responses = [
        {"ok": True, "job_id": "j1", "kind": "chatgpt_web.ask", "status": "in_progress"},
        {"ok": True, "job_id": "j1", "kind": "chatgpt_web.ask", "status": "completed"},
    ]
    calls: list[str] = []

    def fake_http_json(*, method: str, url: str, **_kwargs):  # noqa: ARG001
        calls.append(f"{method} {url}")
        return responses.pop(0)

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)

    job = asyncio.run(mod.chatgptrest_job_wait("j1", timeout_seconds=10, poll_seconds=0.2))
    assert job["status"] == "completed"
    assert len(calls) == 2


def test_mcp_job_wait_auto_codex_autofix_submits_repair_job(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()

    responses = [
        {
            "ok": True,
            "job_id": "j1",
            "kind": "chatgpt_web.ask",
            "status": "cooldown",
            "reason_type": "InfraError",
            "reason": "CDP connect failed",
            "retry_after_seconds": 0,
            "conversation_url": "https://chatgpt.com/c/00000000-0000-0000-0000-000000000000",
        },
        {"ok": True, "job_id": "j1", "kind": "chatgpt_web.ask", "status": "completed"},
    ]
    calls: list[tuple[str, str, object]] = []

    def fake_http_json(*, method: str, url: str, body=None, **_kwargs):  # noqa: ANN001,ARG001
        calls.append((method, url, body))
        if method == "POST" and url.endswith("/v1/jobs"):
            assert isinstance(body, dict)
            assert body.get("kind") == "repair.autofix"
            return {"ok": True, "job_id": "r1", "kind": "repair.autofix", "status": "queued"}
        return responses.pop(0)

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    async def fake_sleep(_seconds: float):  # noqa: ARG001
        return None

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)

    job = asyncio.run(mod.chatgptrest_job_wait("j1", timeout_seconds=10, poll_seconds=0.2))
    assert job["status"] == "completed"
    assert any(method == "POST" and url.endswith("/v1/jobs") for method, url, _body in calls)


def test_mcp_job_wait_auto_background_handoff_for_long_wait(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()
    monkeypatch.setenv("CHATGPTREST_MCP_WAIT_AUTO_BACKGROUND", "1")
    monkeypatch.setenv("CHATGPTREST_MCP_WAIT_AUTO_BACKGROUND_THRESHOLD_SECONDS", "30")
    monkeypatch.setenv("CHATGPTREST_MCP_WAIT_MAX_FOREGROUND_SECONDS", "20")

    started_calls: list[dict] = []
    http_calls: list[str] = []

    async def fake_bg_start(**kwargs):  # noqa: ANN003
        started_calls.append(dict(kwargs))
        return {
            "ok": True,
            "watch_id": "wait-1",
            "job_id": "j1",
            "watch_status": "running",
            "running": True,
            "already_running": False,
        }

    def fake_http_json(*, method: str, url: str, **_kwargs):  # noqa: ARG001
        http_calls.append(f"{method} {url}")
        assert method == "GET"
        assert url.endswith("/v1/jobs/j1")
        return {"ok": True, "job_id": "j1", "kind": "gemini_web.ask", "status": "in_progress"}

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    monkeypatch.setattr(mod, "_background_wait_start", fake_bg_start)
    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)

    job = asyncio.run(mod.chatgptrest_job_wait("j1", timeout_seconds=300, poll_seconds=0.2))
    assert job["wait_mode"] == "background"
    assert job["background_wait_started"] is True
    assert job["watch_id"] == "wait-1"
    assert job["status"] == "in_progress"
    assert job["requested_timeout_seconds"] == 300
    assert isinstance(job.get("next_action"), dict)
    assert job["next_action"]["tool"] == "chatgptrest_job_wait_background_get"
    assert job["next_action"]["args"]["watch_id"] == "wait-1"
    assert len(started_calls) == 1
    assert len(http_calls) == 1


def test_mcp_job_wait_clamps_foreground_when_auto_background_disabled(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()
    monkeypatch.setenv("CHATGPTREST_MCP_WAIT_AUTO_BACKGROUND", "0")
    monkeypatch.setenv("CHATGPTREST_MCP_WAIT_MAX_FOREGROUND_SECONDS", "5")

    seen_urls: list[str] = []

    def fake_http_json(*, method: str, url: str, **_kwargs):  # noqa: ARG001
        seen_urls.append(url)
        return {"ok": True, "job_id": "j1", "kind": "chatgpt_web.ask", "status": "completed"}

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)

    job = asyncio.run(mod.chatgptrest_job_wait("j1", timeout_seconds=120, poll_seconds=0.2))
    assert job["status"] == "completed"
    assert job["wait_clamped"] is True
    assert job["requested_timeout_seconds"] == 120
    assert job["effective_timeout_seconds"] == 5
    wait_url = next((u for u in seen_urls if "/wait?" in u), "")
    assert "timeout_seconds=" in wait_url
    wait_timeout = int(wait_url.split("timeout_seconds=", 1)[1].split("&", 1)[0])
    assert 1 <= wait_timeout <= 5


def test_mcp_job_wait_can_disable_foreground_wait_completely(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()
    monkeypatch.setenv("CHATGPTREST_MCP_WAIT_FOREGROUND_ENABLED", "0")
    monkeypatch.setenv("CHATGPTREST_MCP_WAIT_AUTO_BACKGROUND", "1")

    started_calls: list[dict] = []
    seen_urls: list[str] = []

    async def fake_bg_start(**kwargs):  # noqa: ANN003
        started_calls.append(dict(kwargs))
        return {
            "ok": True,
            "watch_id": "wait-nofg-1",
            "job_id": "j1",
            "watch_status": "running",
            "running": True,
            "already_running": False,
        }

    def fake_http_json(*, method: str, url: str, **_kwargs):  # noqa: ARG001
        seen_urls.append(url)
        assert method == "GET"
        assert "/wait?" not in url
        return {"ok": True, "job_id": "j1", "kind": "chatgpt_web.ask", "status": "in_progress"}

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    monkeypatch.setattr(mod, "_background_wait_start", fake_bg_start)
    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)

    job = asyncio.run(mod.chatgptrest_job_wait("j1", timeout_seconds=5, poll_seconds=0.2))
    assert job["wait_mode"] == "background"
    assert job["foreground_disabled"] is True
    assert job["background_wait_started"] is True
    assert job["watch_id"] == "wait-nofg-1"
    assert job["next_action"]["tool"] == "chatgptrest_job_wait_background_get"
    assert job["next_action"]["args"]["watch_id"] == "wait-nofg-1"
    assert len(started_calls) == 1
    assert seen_urls and all("/wait?" not in u for u in seen_urls)


def test_mcp_job_wait_falls_back_to_foreground_when_background_start_fails(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()
    monkeypatch.setenv("CHATGPTREST_MCP_WAIT_FOREGROUND_ENABLED", "0")
    monkeypatch.setenv("CHATGPTREST_MCP_WAIT_AUTO_BACKGROUND", "1")

    started_calls: list[dict] = []
    seen_urls: list[str] = []

    async def fake_bg_start(**kwargs):  # noqa: ANN003
        started_calls.append(dict(kwargs))
        return {
            "ok": False,
            "error_type": "BackgroundWaitUnsupported",
            "error": "background wait requires stateful runtime",
        }

    def fake_http_json(*, method: str, url: str, **_kwargs):  # noqa: ARG001
        seen_urls.append(url)
        if "/wait?" in url:
            return {"ok": True, "job_id": "j1", "kind": "chatgpt_web.ask", "status": "completed"}
        return {"ok": True, "job_id": "j1", "kind": "chatgpt_web.ask", "status": "in_progress"}

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    monkeypatch.setattr(mod, "_background_wait_start", fake_bg_start)
    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)

    job = asyncio.run(mod.chatgptrest_job_wait("j1", timeout_seconds=5, poll_seconds=0.2))
    assert job["status"] == "completed"
    assert isinstance(job.get("wait_warnings"), list)
    assert job["wait_warnings"][0]["type"] == "background_wait_start_failed"
    assert job["wait_warnings"][0]["stage"] == "foreground_disabled"
    assert len(started_calls) == 1
    assert any("/wait?" in u for u in seen_urls)
