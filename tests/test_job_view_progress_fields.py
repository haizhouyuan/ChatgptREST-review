from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.db import connect
from chatgptrest.core.job_store import claim_next_job, store_answer_result


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "32")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _create_chatgpt_job(client: TestClient, *, idempotency_key: str) -> str:
    r = client.post(
        "/v1/jobs",
        json={"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {"preset": "auto"}},
        headers={"Idempotency-Key": idempotency_key},
    )
    assert r.status_code == 200
    return str(r.json()["job_id"])


def _claim_job(env: dict[str, Path]) -> object:
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w1", lease_ttl_seconds=60)
        conn.commit()
    assert job is not None
    return job


def test_job_view_exposes_prompt_and_answer_ready_progress(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    job_id = _create_chatgpt_job(client, idempotency_key="job-view-progress-1")
    claimed = _claim_job(env)
    assert str(claimed.job_id) == job_id

    with connect(env["db_path"]) as conn:
        conn.execute(
            "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
            (job_id, 100.0, "prompt_sent", None),
        )
        conn.commit()

    send_view = client.get(f"/v1/jobs/{job_id}").json()
    assert send_view["status"] == "in_progress"
    assert send_view["phase"] == "send"
    assert send_view["phase_detail"] == "awaiting_assistant_answer"
    assert send_view["action_hint"] == "wait_for_assistant_answer"
    assert send_view["last_event_type"] == "prompt_sent"
    assert send_view["prompt_sent_at"] == 100.0
    assert send_view["assistant_answer_ready_at"] is None

    with connect(env["db_path"]) as conn:
        conn.execute(
            "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
            (job_id, 200.0, "assistant_answer_ready", None),
        )
        conn.execute(
            "UPDATE jobs SET phase = ?, updated_at = ? WHERE job_id = ?",
            ("wait", float(time.time()), job_id),
        )
        conn.commit()

    wait_view = client.get(f"/v1/jobs/{job_id}").json()
    assert wait_view["status"] == "in_progress"
    assert wait_view["phase"] == "wait"
    assert wait_view["phase_detail"] == "awaiting_export_reconciliation"
    assert wait_view["action_hint"] == "wait_for_export_reconciliation"
    assert wait_view["last_event_type"] == "assistant_answer_ready"
    assert wait_view["prompt_sent_at"] == 100.0
    assert wait_view["assistant_answer_ready_at"] == 200.0


def test_job_result_marks_short_completed_answers_for_review(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    job_id = _create_chatgpt_job(client, idempotency_key="job-view-progress-2")
    claimed = _claim_job(env)
    assert str(claimed.job_id) == job_id

    answer = "short answer"
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        store_answer_result(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=job_id,
            worker_id="w1",
            lease_token=str(claimed.lease_token or ""),
            answer=answer,
            answer_format="markdown",
        )
        conn.execute(
            "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
            (
                job_id,
                300.0,
                "completion_guard_completed_under_min_chars",
                json.dumps({"answer_chars": len(answer) + 1, "min_chars_required": 800}, ensure_ascii=False),
            ),
        )
        conn.commit()

    result = client.get(f"/v1/jobs/{job_id}/result").json()
    assert result["status"] == "completed"
    assert result["answer_chars"] == len(answer) + 1
    assert result["completion_quality"] == "completed_under_min_chars"
    assert result["phase_detail"] == "completed_under_min_chars"
    assert result["action_hint"] == "review_completed_answer"
    assert result["last_event_type"] == "completion_guard_completed_under_min_chars"

