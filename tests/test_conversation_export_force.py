from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

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
    monkeypatch.setenv("CHATGPTREST_CONVERSATION_EXPORT_OK_COOLDOWN_SECONDS", "120")
    monkeypatch.setenv("CHATGPTREST_CONVERSATION_EXPORT_GLOBAL_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("CHATGPTREST_DRIVER_MODE", "internal_mcp")
    return {"tmp_path": tmp_path, "db_path": db_path, "artifacts_dir": artifacts_dir}


def test_force_export_bypasses_ok_cooldown(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "export-force"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    export_state_path = env["artifacts_dir"] / "jobs" / job_id / "conversation_export_state.json"
    export_state_path.parent.mkdir(parents=True, exist_ok=True)
    export_state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "last_ok_at": time.time(),
                "last_export_chars": 1,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    export_content = json.dumps(
        {
            "export_kind": "dom_messages",
            "conversation_url": "https://chatgpt.com/c/test",
            "messages": [{"role": "user", "text": "hi"}, {"role": "assistant", "text": "hello"}],
        },
        ensure_ascii=False,
        indent=2,
    )

    class _DummyToolCaller:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            assert tool_name == "chatgpt_web_conversation_export"
            self.calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            dst = tool_args.get("dst_path")
            assert isinstance(dst, str) and dst
            Path(dst).write_text(export_content + "\n", encoding="utf-8")
            return {"ok": True, "export_path": dst}

    tool_caller = _DummyToolCaller()

    cfg = load_config()

    # Without force, ok_cooldown prevents any export attempt.
    asyncio.run(
        _maybe_export_conversation(
            cfg=cfg,
            job_id=job_id,
            conversation_url="https://chatgpt.com/c/test",
            tool_caller=tool_caller,  # type: ignore[arg-type]
            force=False,
        )
    )
    assert tool_caller.calls == []

    # With force, it should export even during ok_cooldown.
    asyncio.run(
        _maybe_export_conversation(
            cfg=cfg,
            job_id=job_id,
            conversation_url="https://chatgpt.com/c/test",
            tool_caller=tool_caller,  # type: ignore[arg-type]
            force=True,
        )
    )
    assert len(tool_caller.calls) == 1

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data.get("conversation_export_path")
    assert int(data.get("conversation_export_chars") or 0) > 0


def test_force_export_respects_fail_backoff(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "export-force-backoff"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    export_state_path = env["artifacts_dir"] / "jobs" / job_id / "conversation_export_state.json"
    export_state_path.parent.mkdir(parents=True, exist_ok=True)
    export_state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "consecutive_failures": 2,
                "cooldown_until": time.time() + 3600,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    class _DummyToolCaller:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            self.calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            raise AssertionError("export should be skipped during fail backoff, even with force")

    tool_caller = _DummyToolCaller()
    cfg = load_config()

    asyncio.run(
        _maybe_export_conversation(
            cfg=cfg,
            job_id=job_id,
            conversation_url="https://chatgpt.com/c/test",
            tool_caller=tool_caller,  # type: ignore[arg-type]
            force=True,
        )
    )
    assert tool_caller.calls == []
