from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.db import connect
from chatgptrest.core.job_store import claim_next_job


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    monkeypatch.setenv("CHATGPTREST_CONVERSATION_SINGLE_FLIGHT", "1")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_create_job_blocks_when_conversation_has_active_ask(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    url = "https://chatgpt.com/c/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    r1 = client.post(
        "/v1/jobs",
        json={"kind": "chatgpt_web.ask", "input": {"question": "hi", "conversation_url": url}, "params": {"preset": "auto"}},
        headers={"Idempotency-Key": "k1"},
    )
    assert r1.status_code == 200
    job_id_1 = r1.json()["job_id"]

    r2 = client.post(
        "/v1/jobs",
        json={"kind": "chatgpt_web.ask", "input": {"question": "hi2", "conversation_url": url}, "params": {"preset": "auto"}},
        headers={"Idempotency-Key": "k2"},
    )
    assert r2.status_code == 409
    detail = r2.json().get("detail") or {}
    assert detail.get("error") == "conversation_busy"
    assert detail.get("active_job_id") == job_id_1


def test_create_job_allows_queue_when_explicit(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    url = "https://chatgpt.com/c/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    r1 = client.post(
        "/v1/jobs",
        json={"kind": "chatgpt_web.ask", "input": {"question": "hi", "conversation_url": url}, "params": {"preset": "auto"}},
        headers={"Idempotency-Key": "k1"},
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "hi2", "conversation_url": url},
            "params": {"preset": "auto", "allow_queue": True},
        },
        headers={"Idempotency-Key": "k2"},
    )
    assert r2.status_code == 200


def test_send_worker_claim_respects_single_flight(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    url = "https://chatgpt.com/c/cccccccc-cccc-cccc-cccc-cccccccccccc"

    # Create two queued jobs for the same conversation (explicit allow_queue on the second).
    r1 = client.post(
        "/v1/jobs",
        json={"kind": "chatgpt_web.ask", "input": {"question": "hi", "conversation_url": url}, "params": {"preset": "auto"}},
        headers={"Idempotency-Key": "k1"},
    )
    assert r1.status_code == 200
    job_a = r1.json()["job_id"]

    r2 = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "hi2", "conversation_url": url},
            "params": {"preset": "auto", "allow_queue": True},
        },
        headers={"Idempotency-Key": "k2"},
    )
    assert r2.status_code == 200
    job_b = r2.json()["job_id"]
    assert job_a != job_b

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w-send", lease_ttl_seconds=60, phase="send")
        conn.commit()
    assert claimed is not None
    assert claimed.job_id == job_a

    # While A is in_progress, B must not be claimed.
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed2 = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w-send2", lease_ttl_seconds=60, phase="send")
        conn.commit()
    assert claimed2 is None

    # Mark A as completed and release its lease; then B can be claimed.
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE jobs SET status = ?, lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL, updated_at = ? WHERE job_id = ?",
            ("completed", time.time(), job_a),
        )
        conn.commit()

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        claimed3 = claim_next_job(conn, artifacts_dir=env["artifacts_dir"], worker_id="w-send3", lease_ttl_seconds=60, phase="send")
        conn.commit()
    assert claimed3 is not None
    assert claimed3.job_id == job_b


def test_qwen_create_job_blocks_when_conversation_has_active_ask(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHATGPTREST_QWEN_ENABLED", "1")
    app = create_app()
    client = TestClient(app)

    url = "https://www.qianwen.com/chat/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    r1 = client.post(
        "/v1/jobs",
        json={"kind": "qwen_web.ask", "input": {"question": "hi", "conversation_url": url}, "params": {"preset": "deep_thinking"}},
        headers={"Idempotency-Key": "qk1"},
    )
    assert r1.status_code == 200
    job_id_1 = r1.json()["job_id"]

    r2 = client.post(
        "/v1/jobs",
        json={"kind": "qwen_web.ask", "input": {"question": "hi2", "conversation_url": url}, "params": {"preset": "deep_thinking"}},
        headers={"Idempotency-Key": "qk2"},
    )
    assert r2.status_code == 409
    detail = r2.json().get("detail") or {}
    assert detail.get("error") == "conversation_busy"
    assert detail.get("active_job_id") == job_id_1
