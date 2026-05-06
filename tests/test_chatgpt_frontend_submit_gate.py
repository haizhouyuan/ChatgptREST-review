from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.client_request_auth import build_registered_client_hmac_headers
from chatgptrest.core.chatgpt_web_hold import set_chatgpt_web_hold
from chatgptrest.core.rate_limit import set_cooldown_until


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    blocked_state_file = tmp_path / "driver" / "chatgpt_blocked_state.json"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "0")
    monkeypatch.setenv("CHATGPTREST_ASK_GUARD_CODEX_ENABLED", "0")
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT", "maint-secret")
    monkeypatch.setenv("CHATGPTREST_CHATGPT_FRONTEND_BLOCK_STATE_FILE", str(blocked_state_file))
    return {
        "db_path": db_path,
        "artifacts_dir": artifacts_dir,
        "blocked_state_file": blocked_state_file,
    }


def _signed_headers(*, body: dict[str, object], idempotency_key: str, nonce: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": "curl/8.7.1",
        "X-Client-Name": "chatgptrestctl-maint",
        "X-Client-Instance": "frontend-gate-test",
        "Idempotency-Key": idempotency_key,
    }
    headers.update(
        build_registered_client_hmac_headers(
            client_lookup="chatgptrestctl-maint",
            client_instance="frontend-gate-test",
            method="POST",
            path="/v1/jobs",
            body_payload=body,
            environ={"CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT": "maint-secret"},
            nonce=str(nonce or f"{idempotency_key}-nonce"),
        )
    )
    return headers


def _chatgpt_body() -> dict[str, object]:
    return {
        "kind": "chatgpt_web.ask",
        "input": {"question": "Review this implementation plan and identify the top engineering risks."},
        "params": {"preset": "pro_extended"},
    }


def _chatgpt_export_body() -> dict[str, object]:
    return {
        "kind": "chatgpt_web.conversation_export",
        "input": {"conversation_url": "https://chatgpt.com/c/69ec8ddd-f254-83e8-90d3-9fd55d7b7248"},
        "params": {"timeout_seconds": 60},
    }


def test_chatgpt_frontend_block_state_rejects_new_chatgpt_submit(env: dict[str, Path]) -> None:
    blocked_state_file = env["blocked_state_file"]
    blocked_state_file.parent.mkdir(parents=True, exist_ok=True)
    blocked_state_file.write_text(
        json.dumps(
            {
                "reason": "frontend_rate_limit",
                "blocked_until": time.time() + 600,
                "source": "unit_test",
            }
        ),
        encoding="utf-8",
    )

    app = create_app()
    client = TestClient(app)
    body = _chatgpt_body()

    res = client.post(
        "/v1/jobs",
        json=body,
        headers=_signed_headers(body=body, idempotency_key="frontend-block-new-submit"),
    )

    assert res.status_code == 429
    detail = res.json()["detail"]
    assert detail["error"] == "chatgpt_frontend_rate_limit_active"
    assert detail["job_created"] is False
    assert detail["source"] == "unit_test"

    conn = sqlite3.connect(env["db_path"])
    try:
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM idempotency").fetchone()[0] == 0
    finally:
        conn.close()


def test_chatgpt_frontend_db_cooldown_rejects_new_chatgpt_submit(env: dict[str, Path]) -> None:
    from chatgptrest.core.db import connect

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        set_cooldown_until(
            conn,
            key="chatgpt_web_frontend_rate_limit",
            until_ts=time.time() + 300,
            reason="frontend_rate_limit",
            payload={"source": "unit_test"},
        )
        conn.commit()

    app = create_app()
    client = TestClient(app)
    body = _chatgpt_body()

    res = client.post(
        "/v1/jobs",
        json=body,
        headers=_signed_headers(body=body, idempotency_key="frontend-block-db-cooldown"),
    )

    assert res.status_code == 429
    detail = res.json()["detail"]
    assert detail["error"] == "chatgpt_frontend_rate_limit_active"
    assert detail["source"] == "db_cooldown"


def test_chatgpt_frontend_block_rejects_direct_conversation_export_submit(env: dict[str, Path]) -> None:
    blocked_state_file = env["blocked_state_file"]
    blocked_state_file.parent.mkdir(parents=True, exist_ok=True)
    blocked_state_file.write_text(
        json.dumps({"reason": "frontend_rate_limit", "blocked_until": time.time() + 600}),
        encoding="utf-8",
    )

    app = create_app()
    client = TestClient(app)
    body = _chatgpt_export_body()

    res = client.post(
        "/v1/jobs",
        json=body,
        headers=_signed_headers(body=body, idempotency_key="frontend-block-direct-export-submit"),
    )

    assert res.status_code == 429
    detail = res.json()["detail"]
    assert detail["error"] == "chatgpt_frontend_rate_limit_active"
    assert detail["job_created"] is False

    conn = sqlite3.connect(env["db_path"])
    try:
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM idempotency").fetchone()[0] == 0
    finally:
        conn.close()


def test_chatgpt_manual_pro_hold_rejects_new_chatgpt_submit(env: dict[str, Path]) -> None:
    blocked_state_file = env["blocked_state_file"]
    blocked_state_file.parent.mkdir(parents=True, exist_ok=True)
    blocked_state_file.write_text(
        json.dumps(
            {
                "reason": "manual_pro_session",
                "blocked_until": time.time() + 600,
                "source": "unit_test_manual_pro",
            }
        ),
        encoding="utf-8",
    )

    app = create_app()
    client = TestClient(app)
    body = _chatgpt_body()

    res = client.post(
        "/v1/jobs",
        json=body,
        headers=_signed_headers(body=body, idempotency_key="manual-pro-hold-new-submit"),
    )

    assert res.status_code == 429
    detail = res.json()["detail"]
    assert detail["error"] == "chatgpt_web_automation_hold_active"
    assert detail["reason"] == "manual_pro_session"
    assert detail["job_created"] is False
    assert detail["source"] == "unit_test_manual_pro"

    conn = sqlite3.connect(env["db_path"])
    try:
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM idempotency").fetchone()[0] == 0
    finally:
        conn.close()


def test_chatgpt_db_manual_pro_hold_rejects_new_chatgpt_submit(env: dict[str, Path]) -> None:
    from chatgptrest.core.db import connect

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        set_chatgpt_web_hold(
            conn,
            reason="manual_pro_session",
            until_ts=time.time() + 600,
            source="unit_test_db_hold",
            note="human using Pro",
        )
        conn.commit()

    app = create_app()
    client = TestClient(app)
    body = _chatgpt_body()

    res = client.post(
        "/v1/jobs",
        json=body,
        headers=_signed_headers(body=body, idempotency_key="manual-pro-db-hold-new-submit"),
    )

    assert res.status_code == 429
    detail = res.json()["detail"]
    assert detail["error"] == "chatgpt_web_automation_hold_active"
    assert detail["reason"] == "manual_pro_session"
    assert detail["source"] == "unit_test_db_hold"
    assert detail["job_created"] is False

    conn = sqlite3.connect(env["db_path"])
    try:
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM idempotency").fetchone()[0] == 0
    finally:
        conn.close()


def test_chatgpt_frontend_block_preserves_idempotent_replay(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    body = _chatgpt_body()
    idem = "frontend-block-idempotent-replay"
    headers = _signed_headers(body=body, idempotency_key=idem, nonce="frontend-block-idempotent-replay-1")

    first = client.post("/v1/jobs", json=body, headers=headers)
    assert first.status_code == 200
    first_job_id = first.json()["job_id"]

    blocked_state_file = env["blocked_state_file"]
    blocked_state_file.parent.mkdir(parents=True, exist_ok=True)
    blocked_state_file.write_text(
        json.dumps({"reason": "frontend_rate_limit", "blocked_until": time.time() + 600}),
        encoding="utf-8",
    )

    replay = client.post(
        "/v1/jobs",
        json=body,
        headers=_signed_headers(body=body, idempotency_key=idem, nonce="frontend-block-idempotent-replay-2"),
    )
    assert replay.status_code == 200
    assert replay.json()["job_id"] == first_job_id


def test_chatgpt_frontend_block_does_not_reject_gemini_submit(env: dict[str, Path]) -> None:
    blocked_state_file = env["blocked_state_file"]
    blocked_state_file.parent.mkdir(parents=True, exist_ok=True)
    blocked_state_file.write_text(
        json.dumps({"reason": "frontend_rate_limit", "blocked_until": time.time() + 600}),
        encoding="utf-8",
    )

    app = create_app()
    client = TestClient(app)
    body = {
        "kind": "gemini_web.ask",
        "input": {"question": "Review this implementation plan and identify the top engineering risks."},
        "params": {"preset": "pro"},
    }

    res = client.post(
        "/v1/jobs",
        json=body,
        headers=_signed_headers(body=body, idempotency_key="frontend-block-gemini-submit"),
    )

    assert res.status_code == 200
    assert res.json()["kind"] == "gemini_web.ask"
