from __future__ import annotations

import asyncio
import json
import time
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
    return {"db_path": db_path}


def _force_wait_in_progress(
    *,
    db_path: Path,
    job_id: str,
    age_seconds: float,
    conversation_url: str | None,
) -> None:
    now = time.time()
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE jobs
            SET status = 'in_progress',
                phase = 'wait',
                not_before = 0,
                created_at = ?,
                updated_at = ?,
                lease_owner = NULL,
                lease_expires_at = NULL,
                lease_token = NULL,
                conversation_url = ?,
                conversation_id = NULL
            WHERE job_id = ?
            """,
            (now - float(age_seconds), now - float(age_seconds), conversation_url, job_id),
        )
        conn.commit()


def test_wait_no_progress_guard_exception_is_audited(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS", "3600")

    app = create_app()
    client = TestClient(app)
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "wait-guard-exception-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    _force_wait_in_progress(
        db_path=env["db_path"],
        job_id=job_id,
        age_seconds=30,
        conversation_url="https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc",
    )

    class _InProgressExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="in_progress",
                answer="",
                answer_format="text",
                meta={"conversation_url": "https://chatgpt.com/c/12345678-1234-1234-1234-123456789abc", "retry_after_seconds": 0},
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _InProgressExecutor())

    def _boom(*, conn, job, kind, params, conversation_url, now_ts):  # noqa: ANN001
        raise RuntimeError("decision query failed")

    monkeypatch.setattr(worker_mod, "_wait_no_progress_timeout_decision", _boom)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    data = job.json()
    assert data["status"] == "in_progress"
    assert data.get("phase") == "wait"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "wait_no_progress_guard_eval_failed"),
        ).fetchone()
    assert row is not None
    payload_obj = json.loads(str(row["payload_json"] or "{}"))
    assert payload_obj.get("reason") == "guard_eval_exception"
    assert payload_obj.get("error_type") == "RuntimeError"
