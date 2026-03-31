from __future__ import annotations

import asyncio
import importlib


def _load_mcp_server_module():
    import chatgptrest.mcp.server as mod

    return importlib.reload(mod)


def test_mcp_gemini_ask_submit_passes_deep_research(monkeypatch):
    mod = _load_mcp_server_module()
    captured: dict[str, object] = {}

    async def fake_job_create(*, idempotency_key, kind, input, params, client, ctx=None):  # noqa: ANN001,ARG001,A002
        captured["idempotency_key"] = idempotency_key
        captured["kind"] = kind
        captured["input"] = input
        captured["params"] = params
        captured["client"] = client
        return {
            "ok": True,
            "job_id": "job-gemini-1",
            "kind": kind,
            "status": "queued",
        }

    monkeypatch.setattr(mod, "chatgptrest_job_create", fake_job_create)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_gemini_ask_submit(
            idempotency_key="idem-gemini-dr-1",
            question="请做调研",
            preset="pro",
            deep_research=True,
            notify_controller=False,
            notify_done=False,
        )
    )

    assert out["ok"] is True
    assert captured["kind"] == "gemini_web.ask"
    params = captured["params"]
    assert isinstance(params, dict)
    assert params.get("deep_research") is True

