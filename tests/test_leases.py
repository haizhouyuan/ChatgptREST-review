from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.db import connect
from chatgptrest.core.job_store import claim_next_job, store_retryable_result
from chatgptrest.core.state_machine import JobStatus


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_reclaim_expired_in_progress_lease(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "lease-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job1 = claim_next_job(
            conn,
            artifacts_dir=env["artifacts_dir"],
            worker_id="w1",
            lease_ttl_seconds=60,
        )
        conn.commit()
    assert job1 is not None
    assert job1.job_id == job_id
    assert job1.lease_owner == "w1"
    assert job1.attempts == 1

    with connect(env["db_path"]) as conn:
        conn.execute("UPDATE jobs SET lease_expires_at = ? WHERE job_id = ?", (time.time() - 1, job_id))
        conn.commit()

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job2 = claim_next_job(
            conn,
            artifacts_dir=env["artifacts_dir"],
            worker_id="w2",
            lease_ttl_seconds=60,
        )
        conn.commit()
    assert job2 is not None
    assert job2.job_id == job_id
    assert job2.lease_owner == "w2"
    # Reclaiming an expired lease should not consume attempts; attempts are meant to cap
    # repeated send-side effects, not recoverable worker crashes/timeouts.
    assert job2.attempts == 1


def test_wait_phase_does_not_consume_attempts(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "lease-wait-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        row = conn.execute("SELECT max_attempts FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        assert row is not None
        max_attempts = int(row["max_attempts"])
        conn.execute("UPDATE jobs SET phase = 'wait', attempts = ? WHERE job_id = ?", (max_attempts, job_id))
        conn.commit()

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job1 = claim_next_job(
            conn,
            artifacts_dir=env["artifacts_dir"],
            worker_id="w1",
            lease_ttl_seconds=60,
            phase="wait",
        )
        conn.commit()
    assert job1 is not None
    assert job1.job_id == job_id
    assert job1.attempts == max_attempts

    with connect(env["db_path"]) as conn:
        conn.execute("UPDATE jobs SET lease_expires_at = ? WHERE job_id = ?", (time.time() - 1, job_id))
        conn.commit()

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job2 = claim_next_job(
            conn,
            artifacts_dir=env["artifacts_dir"],
            worker_id="w2",
            lease_ttl_seconds=60,
            phase="wait",
        )
        conn.commit()
    assert job2 is not None
    assert job2.job_id == job_id
    assert job2.lease_owner == "w2"
    assert job2.attempts == max_attempts


def test_cancel_wait_phase_with_active_lease_finalizes_immediately(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "cancel-wait-active"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed = claim_next_job(
            conn,
            artifacts_dir=env["artifacts_dir"],
            worker_id="wait-w1",
            lease_ttl_seconds=60,
        )
        conn.execute("UPDATE jobs SET phase = 'wait' WHERE job_id = ?", (job_id,))
        conn.commit()
    assert claimed is not None
    assert claimed.job_id == job_id

    cancel = client.post(f"/v1/jobs/{job_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "canceled"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT status, cancel_requested_at, last_error_type, last_error FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    assert row is not None
    assert row["status"] == "canceled"
    assert row["cancel_requested_at"] is not None
    assert row["last_error_type"] == "Canceled"
    assert "cancel requested" in str(row["last_error"] or "")

    result_path = env["artifacts_dir"] / "jobs" / job_id / "result.json"
    payload_out = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload_out["status"] == "canceled"
    assert payload_out["canceled"] is True


def test_cancel_wait_phase_with_expired_lease_finalizes_immediately(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "cancel-wait-expired"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed = claim_next_job(
            conn,
            artifacts_dir=env["artifacts_dir"],
            worker_id="wait-w1",
            lease_ttl_seconds=60,
        )
        conn.execute(
            "UPDATE jobs SET phase = 'wait', lease_expires_at = ? WHERE job_id = ?",
            (time.time() - 1, job_id),
        )
        conn.commit()
    assert claimed is not None
    assert claimed.job_id == job_id

    cancel = client.post(f"/v1/jobs/{job_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "canceled"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT status, lease_owner, lease_expires_at, lease_token FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    assert row is not None
    assert row["status"] == "canceled"
    assert row["lease_owner"] is None
    assert row["lease_expires_at"] is None
    assert row["lease_token"] is None


@pytest.mark.parametrize("retryable_status", [JobStatus.NEEDS_FOLLOWUP, JobStatus.COOLDOWN, JobStatus.BLOCKED])
def test_cancel_nonrunning_intermediate_status_finalizes_immediately(
    env: dict[str, Path],
    retryable_status: JobStatus,
):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": f"cancel-{retryable_status.value}"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed = claim_next_job(
            conn,
            artifacts_dir=env["artifacts_dir"],
            worker_id="send-w1",
            lease_ttl_seconds=60,
        )
        stored = store_retryable_result(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=job_id,
            worker_id="send-w1",
            lease_token=str(claimed.lease_token or ""),
            status=retryable_status,
            not_before=time.time() + 30,
            error_type="RetryableError",
            error="transient condition",
        )
        conn.commit()
    assert claimed is not None
    assert stored.status == retryable_status

    cancel = client.post(f"/v1/jobs/{job_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "canceled"

    with connect(env["db_path"]) as conn:
        row = conn.execute(
            "SELECT status, cancel_requested_at, last_error_type, last_error, lease_owner, lease_expires_at, lease_token FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    assert row is not None
    assert row["status"] == "canceled"
    assert row["cancel_requested_at"] is not None
    assert row["last_error_type"] == "Canceled"
    assert "cancel requested" in str(row["last_error"] or "")
    assert row["lease_owner"] is None
    assert row["lease_expires_at"] is None
    assert row["lease_token"] is None

    result_path = env["artifacts_dir"] / "jobs" / job_id / "result.json"
    payload_out = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload_out["status"] == "canceled"
    assert payload_out["canceled"] is True


def test_retryable_result_at_max_attempts_becomes_error(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "lease-max-attempts-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        row = conn.execute("SELECT max_attempts FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        assert row is not None
        max_attempts = int(row["max_attempts"])
    assert max_attempts >= 1

    for _ in range(max_attempts - 1):
        with connect(env["db_path"]) as conn:
            conn.execute("BEGIN IMMEDIATE")
            job = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
            conn.commit()
        assert job is not None
        assert job.job_id == job_id

        with connect(env["db_path"]) as conn:
            conn.execute("BEGIN IMMEDIATE")
            stored = store_retryable_result(
                conn,
                artifacts_dir=env["artifacts_dir"],
                job_id=job_id,
                worker_id="w1",
                lease_token=str(job.lease_token or ""),
                status=JobStatus.COOLDOWN,
                not_before=time.time() - 1,
                error_type="RetryableError",
                error="transient failure",
            )
            conn.commit()
        assert stored.status == JobStatus.COOLDOWN

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        last_job = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
    assert last_job is not None
    assert last_job.job_id == job_id
    assert last_job.attempts == max_attempts

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        stored = store_retryable_result(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=job_id,
            worker_id="w1",
            lease_token=str(last_job.lease_token or ""),
            status=JobStatus.COOLDOWN,
            not_before=time.time() - 1,
            error_type="RetryableError",
            error="transient failure",
        )
        conn.commit()
    assert stored.status == JobStatus.ERROR

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w2", lease_ttl_seconds=60)
        conn.commit()
    assert job is None


def test_retryable_ask_extends_max_attempts(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_RETRYABLE_SEND_ATTEMPTS_CAP", "5")
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "请分析当前实现中的两个主要回归风险并给出缓解建议。"},
        "params": {"preset": "pro"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "lease-ask-extend-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        row = conn.execute("SELECT max_attempts FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        assert row is not None
        max_attempts = int(row["max_attempts"])
    assert max_attempts >= 1

    for _ in range(max_attempts - 1):
        with connect(env["db_path"]) as conn:
            conn.execute("BEGIN IMMEDIATE")
            job = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
            conn.commit()
        assert job is not None

        with connect(env["db_path"]) as conn:
            conn.execute("BEGIN IMMEDIATE")
            stored = store_retryable_result(
                conn,
                artifacts_dir=env["artifacts_dir"],
                job_id=job_id,
                worker_id="w1",
                lease_token=str(job.lease_token or ""),
                status=JobStatus.COOLDOWN,
                not_before=time.time() - 1,
                error_type="InfraError",
                error="CDP connect failed",
            )
            conn.commit()
        assert stored.status == JobStatus.COOLDOWN

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        last_job = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
    assert last_job is not None
    assert last_job.attempts == max_attempts

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        stored = store_retryable_result(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=job_id,
            worker_id="w1",
            lease_token=str(last_job.lease_token or ""),
            status=JobStatus.COOLDOWN,
            not_before=time.time() - 1,
            error_type="InfraError",
            error="CDP connect failed",
        )
        row = conn.execute("SELECT status, attempts, max_attempts FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        ev = conn.execute(
            "SELECT 1 FROM job_events WHERE job_id = ? AND type = ? LIMIT 1",
            (job_id, "max_attempts_extended"),
        ).fetchone()
        conn.commit()
    assert stored.status == JobStatus.COOLDOWN
    assert row is not None
    assert str(row["status"]) == JobStatus.COOLDOWN.value
    assert int(row["attempts"]) == max_attempts
    assert int(row["max_attempts"]) == max_attempts + 1
    assert ev is not None


def test_retryable_ask_sticky_upload_closed_does_not_extend(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_RETRYABLE_SEND_ATTEMPTS_CAP", "10")
    monkeypatch.setenv("CHATGPTREST_RETRYABLE_SEND_MAX_EXTENSIONS", "5")
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "lease-ask-sticky-upload-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    with connect(env["db_path"]) as conn:
        row = conn.execute("SELECT max_attempts FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        assert row is not None
        max_attempts = int(row["max_attempts"])
    assert max_attempts >= 1

    sticky_error = (
        "Locator.set_input_files: Target page, context or browser has been closed\n"
        "Call log:\n"
        "  - waiting for locator(\"form:has(#prompt-textarea) input[type='file']\").first"
    )

    for _ in range(max_attempts - 1):
        with connect(env["db_path"]) as conn:
            conn.execute("BEGIN IMMEDIATE")
            job = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
            conn.commit()
        assert job is not None

        with connect(env["db_path"]) as conn:
            conn.execute("BEGIN IMMEDIATE")
            stored = store_retryable_result(
                conn,
                artifacts_dir=env["artifacts_dir"],
                job_id=job_id,
                worker_id="w1",
                lease_token=str(job.lease_token or ""),
                status=JobStatus.COOLDOWN,
                not_before=time.time() - 1,
                error_type="TargetClosedError",
                error=sticky_error,
            )
            conn.commit()
        assert stored.status == JobStatus.COOLDOWN

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        last_job = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
    assert last_job is not None
    assert last_job.attempts == max_attempts

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        stored = store_retryable_result(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=job_id,
            worker_id="w1",
            lease_token=str(last_job.lease_token or ""),
            status=JobStatus.COOLDOWN,
            not_before=time.time() - 1,
            error_type="TargetClosedError",
            error=sticky_error,
        )
        row = conn.execute("SELECT status, max_attempts, last_error_type, last_error FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        ev_ext = conn.execute(
            "SELECT 1 FROM job_events WHERE job_id = ? AND type = ? LIMIT 1",
            (job_id, "max_attempts_extended"),
        ).fetchone()
        ev_skip = conn.execute(
            "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id DESC LIMIT 1",
            (job_id, "max_attempts_extension_skipped"),
        ).fetchone()
        conn.commit()

    assert stored.status == JobStatus.ERROR
    assert row is not None
    assert str(row["status"]) == JobStatus.ERROR.value
    assert int(row["max_attempts"]) == max_attempts
    assert str(row["last_error_type"] or "") == "MaxAttemptsExceeded"
    assert "sticky_upload_surface_closed" in str(row["last_error"] or "")
    assert ev_ext is None
    assert ev_skip is not None
    payload_obj = json.loads(str(ev_skip["payload_json"] or "{}"))
    assert payload_obj.get("guard_reason") == "sticky_upload_surface_closed"


def test_retryable_qwen_submission_is_rejected_as_removed_provider(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_QWEN_ENABLED", "1")
    monkeypatch.setenv("CHATGPTREST_RETRYABLE_SEND_ATTEMPTS_CAP", "10")
    monkeypatch.setenv("CHATGPTREST_RETRYABLE_SEND_MAX_EXTENSIONS", "0")
    app = create_app()
    client = TestClient(app)
    payload = {"kind": "qwen_web.ask", "input": {"question": "hi"}, "params": {"preset": "deep_thinking"}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "lease-qwen-cdp-limit-needs-followup"})
    assert r.status_code == 409
    detail = r.json().get("detail") or {}
    assert detail.get("error") == "provider_removed"
