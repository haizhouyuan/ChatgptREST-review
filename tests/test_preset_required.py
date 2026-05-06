from __future__ import annotations

import json
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
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_chatgpt_web_ask_requires_preset(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "chatgpt_web.ask", "input": {"question": "hi"}, "params": {}},
        headers={"Idempotency-Key": "missing-preset-chatgpt"},
    )
    assert r.status_code == 400
    detail = r.json().get("detail") or {}
    assert detail.get("error") == "missing_preset"


def test_chatgpt_web_ask_accepts_deep_research_preset_alias(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "请给出三条可执行的系统设计建议并写出权衡"},
            "params": {"preset": "deep_research"},
        },
        headers={"Idempotency-Key": "chatgpt-deep-research-preset-alias"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    req_path = env["artifacts_dir"] / "jobs" / job_id / "request.json"
    payload = json.loads(req_path.read_text(encoding="utf-8"))
    assert payload["params"]["preset"] == "thinking_heavy"
    assert payload["params"]["deep_research"] is True


def test_gemini_web_ask_requires_preset(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "gemini_web.ask", "input": {"question": "hi"}, "params": {}},
        headers={"Idempotency-Key": "missing-preset-gemini"},
    )
    assert r.status_code == 400
    detail = r.json().get("detail") or {}
    assert detail.get("error") == "missing_preset"


def test_qwen_web_ask_requires_preset(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "qwen_web.ask", "input": {"question": "hi"}, "params": {}},
        headers={"Idempotency-Key": "missing-preset-qwen"},
    )
    assert r.status_code == 409
    detail = r.json().get("detail") or {}
    assert detail.get("error") == "provider_removed"


def test_qwen_web_ask_enabled_then_requires_preset(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_QWEN_ENABLED", "1")
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "qwen_web.ask", "input": {"question": "hi"}, "params": {}},
        headers={"Idempotency-Key": "missing-preset-qwen-enabled"},
    )
    assert r.status_code == 409
    detail = r.json().get("detail") or {}
    assert detail.get("error") == "provider_removed"


def test_gemini_generate_image_does_not_require_preset(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "gemini_web.generate_image", "input": {"prompt": "a cat"}, "params": {}},
        headers={"Idempotency-Key": "no-preset-gemini-image"},
    )
    assert r.status_code == 200
