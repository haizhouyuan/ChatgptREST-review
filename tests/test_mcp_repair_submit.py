from __future__ import annotations

import asyncio

from chatgptrest.mcp import server


def test_mcp_repair_check_submit_uses_shared_payload_contract(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return {"job_id": "repair-check-1", "status": "queued"}

    async def fake_notify(job, *, notify_done):
        return None

    monkeypatch.setattr(server, "chatgptrest_job_create", fake_create)
    monkeypatch.setattr(server, "_maybe_notify_done", fake_notify)

    result = asyncio.run(
        server.chatgptrest_repair_check_submit(
            idempotency_key="idem-check",
            job_id="target-1",
            symptom="timeout",
            conversation_url="https://chatgpt.com/c/1",
            mode="debug",
            timeout_seconds=90,
            probe_driver=False,
            capture_ui=True,
            recent_failures=7,
            notify_controller=False,
            notify_done=False,
        )
    )

    assert result["job_id"] == "repair-check-1"
    assert captured["kind"] == "repair.check"
    assert captured["input"] == {
        "job_id": "target-1",
        "symptom": "timeout",
        "conversation_url": "https://chatgpt.com/c/1",
    }
    assert captured["params"] == {
        "mode": "debug",
        "timeout_seconds": 90,
        "probe_driver": False,
        "capture_ui": True,
        "recent_failures": 7,
    }


def test_mcp_repair_autofix_submit_uses_shared_payload_contract(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return {"job_id": "repair-autofix-1", "status": "queued"}

    async def fake_notify(job, *, notify_done):
        return None

    monkeypatch.setattr(server, "chatgptrest_job_create", fake_create)
    monkeypatch.setattr(server, "_maybe_notify_done", fake_notify)

    result = asyncio.run(
        server.chatgptrest_repair_autofix_submit(
            idempotency_key="idem-autofix",
            job_id="target-1",
            symptom="timeout",
            conversation_url="https://chatgpt.com/c/2",
            timeout_seconds=300,
            model="gpt-5-codex",
            max_risk="medium",
            allow_actions="restart_driver",
            apply_actions=False,
            notify_controller=False,
            notify_done=False,
        )
    )

    assert result["job_id"] == "repair-autofix-1"
    assert captured["kind"] == "repair.autofix"
    assert captured["input"] == {
        "job_id": "target-1",
        "symptom": "timeout",
        "conversation_url": "https://chatgpt.com/c/2",
    }
    assert captured["params"] == {
        "timeout_seconds": 300,
        "max_risk": "medium",
        "apply_actions": False,
        "model": "gpt-5-codex",
        "allow_actions": "restart_driver",
    }
