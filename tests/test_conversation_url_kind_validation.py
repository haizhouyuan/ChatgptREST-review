from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    monkeypatch.setenv("CHATGPTREST_QWEN_ENABLED", "1")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_rejects_chatgpt_kind_with_gemini_conversation_url(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "hi", "conversation_url": "https://gemini.google.com/app/abc123def456"},
        "params": {"preset": "pro_extended"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "conv-kind-1"})
    assert r.status_code == 400
    assert "gemini" in r.text.lower()


def test_rejects_gemini_kind_with_chatgpt_conversation_url(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "hi", "conversation_url": "https://chatgpt.com/c/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
        "params": {"preset": "pro"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "conv-kind-2"})
    assert r.status_code == 400
    assert "chatgpt" in r.text.lower()


def test_rejects_qwen_kind_with_chatgpt_conversation_url(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "qwen_web.ask",
        "input": {"question": "hi", "conversation_url": "https://chatgpt.com/c/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
        "params": {"preset": "deep_thinking"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "conv-kind-3"})
    assert r.status_code == 400
    assert "qwen" in r.text.lower()


def test_rejects_chatgpt_kind_with_qwen_conversation_url(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    payload = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "hi", "conversation_url": "https://www.qianwen.com/chat/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
        "params": {"preset": "pro_extended"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "conv-kind-4"})
    assert r.status_code == 400
    assert "qwen" in r.text.lower()


def test_rejects_cross_provider_parent_job_id_followup(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    parent = {
        "kind": "gemini_web.ask",
        "input": {"question": "hi", "conversation_url": "https://gemini.google.com/app/abc123def456"},
        "params": {"preset": "pro"},
    }
    r = client.post("/v1/jobs", json=parent, headers={"Idempotency-Key": "conv-kind-parent-1"})
    assert r.status_code == 200
    parent_id = r.json()["job_id"]

    child = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "hi", "parent_job_id": parent_id},
        "params": {"preset": "pro_extended"},
    }
    r2 = client.post("/v1/jobs", json=child, headers={"Idempotency-Key": "conv-kind-child-1"})
    assert r2.status_code == 400
    assert "parent_job_id kind mismatch" in r2.text.lower()


def test_rejects_qwen_parent_job_id_cross_provider_followup(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    parent = {
        "kind": "qwen_web.ask",
        "input": {"question": "hi", "conversation_url": "https://www.qianwen.com/chat/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
        "params": {"preset": "deep_thinking"},
    }
    r = client.post("/v1/jobs", json=parent, headers={"Idempotency-Key": "conv-kind-parent-2"})
    assert r.status_code == 200
    parent_id = r.json()["job_id"]

    child = {
        "kind": "gemini_web.ask",
        "input": {"question": "hi", "parent_job_id": parent_id},
        "params": {"preset": "pro"},
    }
    r2 = client.post("/v1/jobs", json=child, headers={"Idempotency-Key": "conv-kind-child-2"})
    assert r2.status_code == 400
    assert "parent_job_id kind mismatch" in r2.text.lower()
