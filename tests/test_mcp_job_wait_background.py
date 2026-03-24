from __future__ import annotations

import asyncio
import importlib
import os

import pytest


def _load_mcp_server_module():
    os.environ["FASTMCP_STATELESS_HTTP"] = "0"
    import chatgptrest.mcp.server as mod

    return importlib.reload(mod)


def test_mcp_job_wait_background_start_and_get(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()
    notifications: list[str] = []

    async def fake_wait(**_kwargs):  # noqa: ANN003
        return {
            "ok": True,
            "job_id": "j1",
            "kind": "chatgpt_web.ask",
            "status": "completed",
            "path": "/tmp/answer.md",
        }

    monkeypatch.setattr(mod, "_chatgptrest_job_wait_impl", fake_wait)
    monkeypatch.setattr(mod, "_tmux_notify", lambda msg: notifications.append(str(msg)))

    async def scenario() -> None:
        started = await mod.chatgptrest_job_wait_background_start(
            "j1",
            timeout_seconds=30,
            poll_seconds=0.2,
            notify_controller=True,
            notify_done=True,
        )
        assert started["ok"] is True
        assert started["watch_status"] == "running"

        final = started
        for _ in range(20):
            final = await mod.chatgptrest_job_wait_background_get(watch_id=str(started["watch_id"]))
            if final.get("watch_status") != "running":
                break
            await asyncio.sleep(0)

        assert final["watch_status"] == "completed"
        assert final["terminal"] is True
        assert final["job_status"] == "completed"
        assert isinstance(final.get("result_job"), dict)
        assert final["result_job"]["status"] == "completed"

        listed = await mod.chatgptrest_job_wait_background_list(include_done=True)
        assert listed["ok"] is True
        assert any(x.get("watch_id") == started["watch_id"] for x in listed.get("watches", []))

    asyncio.run(scenario())
    assert any("background wait started" in x for x in notifications)
    assert any("background wait done" in x for x in notifications)


def test_mcp_job_wait_background_start_reuses_running_watch(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()
    gate: dict[str, asyncio.Event] = {}

    async def fake_wait(**_kwargs):  # noqa: ANN003
        await gate["event"].wait()
        return {"ok": True, "job_id": "j1", "status": "completed"}

    monkeypatch.setattr(mod, "_chatgptrest_job_wait_impl", fake_wait)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    async def scenario() -> None:
        gate["event"] = asyncio.Event()
        started = await mod.chatgptrest_job_wait_background_start(
            "j1",
            timeout_seconds=60,
            poll_seconds=0.2,
            notify_controller=False,
            notify_done=False,
        )
        reused = await mod.chatgptrest_job_wait_background_start(
            "j1",
            timeout_seconds=60,
            poll_seconds=0.2,
            notify_controller=False,
            notify_done=False,
        )
        assert started["ok"] is True
        assert reused["ok"] is True
        assert reused["already_running"] is True
        assert reused["watch_id"] == started["watch_id"]

        gate["event"].set()
        for _ in range(20):
            current = await mod.chatgptrest_job_wait_background_get(watch_id=str(started["watch_id"]))
            if current.get("watch_status") != "running":
                break
            await asyncio.sleep(0)
        assert current["watch_status"] == "completed"

    asyncio.run(scenario())


def test_mcp_job_wait_background_cancel(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()

    async def fake_wait(**_kwargs):  # noqa: ANN003
        await asyncio.sleep(60.0)
        return {"ok": True, "job_id": "j1", "status": "completed"}

    monkeypatch.setattr(mod, "_chatgptrest_job_wait_impl", fake_wait)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    async def scenario() -> None:
        started = await mod.chatgptrest_job_wait_background_start(
            "j1",
            timeout_seconds=60,
            poll_seconds=0.2,
            notify_controller=False,
            notify_done=False,
        )
        canceled = await mod.chatgptrest_job_wait_background_cancel(watch_id=str(started["watch_id"]))
        assert canceled["ok"] is True
        assert canceled["watch_status"] == "canceled"
        assert canceled["terminal"] is False

        fetched = await mod.chatgptrest_job_wait_background_get(job_id="j1")
        assert fetched["ok"] is True
        assert fetched["watch_status"] == "canceled"

    asyncio.run(scenario())


def test_mcp_job_wait_background_get_auto_resumes_missing_watch(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()
    monkeypatch.setenv("CHATGPTREST_MCP_WAIT_BACKGROUND_AUTO_RESUME", "1")

    async def fake_job_get(_job_id: str, ctx=None):  # noqa: ANN001,ARG001
        return {"ok": True, "job_id": "j1", "status": "in_progress"}

    async def fake_bg_start(**_kwargs):  # noqa: ANN003
        return {
            "ok": True,
            "watch_id": "wait-autoresume-1",
            "job_id": "j1",
            "watch_status": "running",
            "running": True,
            "done": False,
            "terminal": False,
            "already_running": False,
        }

    monkeypatch.setattr(mod, "chatgptrest_job_get", fake_job_get)
    monkeypatch.setattr(mod, "_background_wait_start", fake_bg_start)

    async def scenario() -> None:
        out = await mod.chatgptrest_job_wait_background_get(job_id="j1")
        assert out["ok"] is True
        assert out["watch_id"] == "wait-autoresume-1"
        assert out["auto_resumed"] is True
        assert out["job_snapshot_status"] == "in_progress"

    asyncio.run(scenario())


def test_mcp_job_wait_background_runner_disables_foreground_cap(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()
    captured: dict[str, object] = {}

    async def fake_wait(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return {"ok": True, "job_id": "j1", "status": "completed"}

    monkeypatch.setattr(mod, "_chatgptrest_job_wait_impl", fake_wait)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    async def scenario() -> None:
        started = await mod.chatgptrest_job_wait_background_start(
            "j1",
            timeout_seconds=600,
            poll_seconds=1.0,
            notify_controller=False,
            notify_done=False,
        )
        assert started["ok"] is True

        for _ in range(20):
            current = await mod.chatgptrest_job_wait_background_get(watch_id=str(started["watch_id"]))
            if current.get("watch_status") != "running":
                break
            await asyncio.sleep(0)

        assert captured.get("allow_auto_background") is False
        assert captured.get("apply_foreground_cap") is False

    asyncio.run(scenario())
