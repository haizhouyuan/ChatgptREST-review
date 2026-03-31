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
        conn.execute(
            "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
            (
                job_id,
                301.0,
                "status_changed",
                json.dumps({"from": "in_progress", "to": "completed"}, ensure_ascii=False),
            ),
        )
        conn.commit()

    result = client.get(f"/v1/jobs/{job_id}/result").json()
    assert result["status"] == "completed"
    assert result["answer_chars"] == len(answer) + 1
    assert result["completion_quality"] == "completed_under_min_chars"
    assert result["phase_detail"] == "completed_under_min_chars"
    assert result["action_hint"] == "review_completed_answer"
    assert result["last_event_type"] == "status_changed"
    assert result["completion_contract"]["answer_state"] == "provisional"
    assert result["completion_contract"]["finality_reason"] == "completed_under_min_chars"


def test_job_result_resolves_authoritative_followup_child_without_marking_parent_final(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    parent_id = _create_chatgpt_job(client, idempotency_key="job-view-progress-parent")
    parent_claimed = _claim_job(env)
    assert str(parent_claimed.job_id) == parent_id

    short_answer = "short answer"
    conversation_url = "https://chatgpt.com/c/11111111-1111-1111-1111-111111111111"
    conversation_id = "11111111-1111-1111-1111-111111111111"
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        store_answer_result(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=parent_id,
            worker_id="w1",
            lease_token=str(parent_claimed.lease_token or ""),
            answer=short_answer,
            answer_format="markdown",
        )
        conn.execute(
            "UPDATE jobs SET conversation_url = ?, conversation_id = ? WHERE job_id = ?",
            (conversation_url, conversation_id, parent_id),
        )
        conn.execute(
            "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
            (
                parent_id,
                300.0,
                "completion_guard_completed_under_min_chars",
                json.dumps({"answer_chars": len(short_answer) + 1, "min_chars_required": 800}, ensure_ascii=False),
            ),
        )
        conn.execute(
            "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
            (
                parent_id,
                301.0,
                "status_changed",
                json.dumps({"from": "in_progress", "to": "completed"}, ensure_ascii=False),
            ),
        )
        conn.commit()

    child_resp = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "continue", "conversation_url": conversation_url, "parent_job_id": parent_id},
            "params": {"preset": "auto"},
        },
        headers={"Idempotency-Key": "job-view-progress-child"},
    )
    assert child_resp.status_code == 200
    child_id = str(child_resp.json()["job_id"])

    child_claimed = _claim_job(env)
    assert str(child_claimed.job_id) == child_id

    long_answer = (
        "# Final Report\n\n"
        "This is the authoritative child answer with enough detail to count as a real final response. "
        "It includes several concrete sentences that summarize the current state, explain the governing constraint, "
        "and confirm the next action without falling back to meta commentary. "
        "It also includes enough surrounding detail to stay above the legacy short-answer fallback threshold that "
        "older result readers still apply while the canonical contract is rebuilt from the answer artifact.\n\n"
        "- Finding: the child answer supersedes the provisional parent.\n"
        "- Action: use this answer as the authoritative response.\n"
    )
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        store_answer_result(
            conn,
            artifacts_dir=env["artifacts_dir"],
            job_id=child_id,
            worker_id="w1",
            lease_token=str(child_claimed.lease_token or ""),
            answer=long_answer,
            answer_format="markdown",
        )
        conn.commit()

    payload = client.get(f"/v1/jobs/{parent_id}/result").json()
    assert payload["status"] == "completed"
    assert payload["completion_quality"] == "completed_under_min_chars"
    assert payload["completion_contract"]["answer_state"] == "provisional"
    assert payload["completion_contract"]["authoritative_job_id"] == child_id
    assert payload["completion_contract"]["authoritative_answer_path"] == f"jobs/{child_id}/answer.md"
    assert payload["canonical_answer"]["ready"] is False
    assert payload["canonical_answer"]["authoritative_job_id"] == child_id
    assert payload["action_hint"] == "fetch_authoritative_answer"

    parent_answer = client.get(f"/v1/jobs/{parent_id}/answer?offset=0&max_chars=200")
    assert parent_answer.status_code == 409
    detail = parent_answer.json()["detail"]
    assert detail["status"] == "completed"
    assert detail["answer_state"] == "provisional"
    assert detail["canonical_ready"] is False
    assert detail["authoritative_job_id"] == child_id
    assert detail["authoritative_answer_path"] == f"jobs/{child_id}/answer.md"
    assert detail["action_hint"] == "fetch_authoritative_answer"


def test_job_result_exposes_canonical_completion_contract(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    job_id = _create_chatgpt_job(client, idempotency_key="job-view-progress-3")
    claimed = _claim_job(env)
    assert str(claimed.job_id) == job_id

    answer = (
        "# Final Report\n\n"
        "This is the grounded final answer. It contains multiple substantive sentences so the quality classifier "
        "treats it as a real deliverable rather than a short placeholder. It also keeps enough structure to remain "
        "obviously final when the result view rebuilds the completion contract. "
        "To avoid tripping the legacy under-400-character fallback, this fixture deliberately carries extra grounded "
        "detail about scope, status, evidence, and next-step framing instead of stopping at a terse confirmation.\n\n"
        "- Scope: final report\n"
        "- Status: complete\n"
        "- Evidence: grounded answer artifact present\n"
        "- Next step: await user follow-up only\n"
    )
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
        conn.commit()

    result = client.get(f"/v1/jobs/{job_id}/result").json()
    contract = result["completion_contract"]
    canonical = result["canonical_answer"]
    assert contract["answer_state"] == "final"
    assert contract["finality_reason"] == "completed"
    assert contract["authoritative_answer_path"] == result["path"]
    assert contract["answer_chars"] == result["answer_chars"]
    assert canonical["ready"] is True
    assert canonical["answer_state"] == "final"
    assert canonical["authoritative_answer_path"] == result["path"]
