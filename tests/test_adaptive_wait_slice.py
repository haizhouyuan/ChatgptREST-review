"""Tests for adaptive wait slice (Opt-1).

Verifies that ``wait_slice_growth_factor`` correctly scales the slice budget
that ``_run_once`` passes to the executor for wait-phase jobs.
"""

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
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    monkeypatch.setenv("CHATGPTREST_WAIT_SLICE_SECONDS", "60")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _create_job(env: dict, *, idempotency_key: str = "adaptive-slice-1") -> str:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "hi"},
            "params": {"preset": "auto", "max_wait_seconds": 1800, "wait_timeout_seconds": 600},
        },
        headers={"Idempotency-Key": idempotency_key},
    )
    assert r.status_code == 200
    return r.json()["job_id"]


def _force_wait_phase(db_path: Path, job_id: str) -> None:
    """Move job to in_progress/wait so wait worker can claim it."""
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE jobs SET status = 'in_progress', phase = 'wait', "
            "lease_owner = NULL, lease_expires_at = NULL, lease_token = NULL WHERE job_id = ?",
            (job_id,),
        )
        conn.commit()


def _insert_wait_requeued_events(db_path: Path, job_id: str, count: int) -> None:
    """Insert N wait_requeued events to simulate prior wait cycles."""
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        for _ in range(count):
            conn.execute(
                "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
                (job_id, time.time(), "wait_requeued", json.dumps({"not_before": time.time()})),
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


def test_wait_slice_growth_factor_1_is_noop(env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """With growth_factor=1.0 (default), slice stays at 60s — identical to pre-change behavior."""
    monkeypatch.setenv("CHATGPTREST_WAIT_SLICE_GROWTH_FACTOR", "1.0")
    job_id = _create_job(env)
    _force_wait_phase(env["db_path"], job_id)
    _insert_wait_requeued_events(env["db_path"], job_id, 3)

    recorder = _RecorderExecutor()
    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: recorder)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True
    assert recorder.seen is not None
    assert int(recorder.seen.get("max_wait_seconds")) == 60
    assert int(recorder.seen.get("wait_timeout_seconds")) == 60


def test_wait_slice_grows_with_requeue_count(env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """With growth_factor=1.5a and 2 prior requeues, slice should be 60 * 1.5^2 = 135."""
    monkeypatch.setenv("CHATGPTREST_WAIT_SLICE_GROWTH_FACTOR", "1.5")
    job_id = _create_job(env, idempotency_key="adaptive-grow-1")
    _force_wait_phase(env["db_path"], job_id)
    _insert_wait_requeued_events(env["db_path"], job_id, 2)

    recorder = _RecorderExecutor()
    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: recorder)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True
    assert recorder.seen is not None
    # 60 * 1.5^2 = 135, capped by min(135, max(60, 1800)) = 135
    assert int(recorder.seen.get("max_wait_seconds")) == 135
    assert int(recorder.seen.get("wait_timeout_seconds")) == 135


def test_wait_slice_growth_capped_by_max_wait(env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """Slice growth cannot exceed the job's max_wait_seconds."""
    monkeypatch.setenv("CHATGPTREST_WAIT_SLICE_GROWTH_FACTOR", "2.0")
    # Create job with small max_wait_seconds to test capping.
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "hi"},
            "params": {"preset": "auto", "max_wait_seconds": 100, "wait_timeout_seconds": 100},
        },
        headers={"Idempotency-Key": "adaptive-cap-1"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    _force_wait_phase(env["db_path"], job_id)
    _insert_wait_requeued_events(env["db_path"], job_id, 5)  # 60 * 2^5 = 1920, should cap at 100

    recorder = _RecorderExecutor()
    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: recorder)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True
    assert recorder.seen is not None
    assert int(recorder.seen.get("max_wait_seconds")) == 100


def test_wait_slice_no_requeues_stays_at_base(env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """With growth_factor > 1 but 0 prior requeues, slice stays at base."""
    monkeypatch.setenv("CHATGPTREST_WAIT_SLICE_GROWTH_FACTOR", "2.0")
    job_id = _create_job(env, idempotency_key="adaptive-no-requeue-1")
    _force_wait_phase(env["db_path"], job_id)
    # No wait_requeued events inserted.

    recorder = _RecorderExecutor()
    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: recorder)

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w1", lease_ttl_seconds=60, role="wait"))
    assert ran is True
    assert recorder.seen is not None
    assert int(recorder.seen.get("max_wait_seconds")) == 60


def test_wait_slice_growth_factor_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that the env variable is read correctly."""
    monkeypatch.setenv("CHATGPTREST_WAIT_SLICE_GROWTH_FACTOR", "1.5")
    cfg = load_config()
    assert cfg.wait_slice_growth_factor == 1.5

    monkeypatch.setenv("CHATGPTREST_WAIT_SLICE_GROWTH_FACTOR", "0.5")
    cfg = load_config()
    assert cfg.wait_slice_growth_factor == 1.0  # clamped to min 1.0

    monkeypatch.delenv("CHATGPTREST_WAIT_SLICE_GROWTH_FACTOR", raising=False)
    cfg = load_config()
    assert cfg.wait_slice_growth_factor == 1.0  # default
