from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.config import load_config
from chatgptrest.core.db import connect
from chatgptrest.executors.base import ExecutorResult
from chatgptrest.worker import worker as worker_mod
from chatgptrest.worker.worker import _run_once


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    monkeypatch.setenv("CHATGPTREST_WAIT_SLICE_SECONDS", "60")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_wait_slice_limits_executor_budget(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "hi"},
            "params": {"preset": "auto", "max_wait_seconds": 1800, "wait_timeout_seconds": 600},
        },
        headers={"Idempotency-Key": "wait-slice-1"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    # Mimic send->wait handoff state.
    with connect(env["db_path"]) as conn:
        conn.execute(
            "UPDATE jobs SET status = 'in_progress', phase = 'wait', lease_owner = NULL, lease_expires_at = NULL, lease_token = NULL WHERE job_id = ?",
            (job_id,),
        )
        conn.commit()

    class _RecorderExecutor:
        def __init__(self) -> None:
            self.seen: dict | None = None

        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            self.seen = dict(params)
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/test", "retry_after_seconds": 0},
            )

    recorder = _RecorderExecutor()
    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: recorder)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True
    assert recorder.seen is not None
    assert int(recorder.seen.get("max_wait_seconds")) == 60
    assert int(recorder.seen.get("wait_timeout_seconds")) == 60
