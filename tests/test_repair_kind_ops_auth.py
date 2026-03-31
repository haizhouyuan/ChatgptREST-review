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
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_repair_kind_rejects_generic_api_token(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "api-token")
    monkeypatch.setenv("CHATGPTREST_OPS_TOKEN", "ops-token")

    client = TestClient(create_app())
    r = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers={
            "Authorization": "Bearer api-token",
            "Idempotency-Key": "repair-auth-api-token",
        },
    )

    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "repair_kind_requires_ops_token"


def test_repair_kind_accepts_ops_token(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "api-token")
    monkeypatch.setenv("CHATGPTREST_OPS_TOKEN", "ops-token")

    client = TestClient(create_app())
    r = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers={
            "Authorization": "Bearer ops-token",
            "Idempotency-Key": "repair-auth-ops-token",
        },
    )

    assert r.status_code == 200
    assert r.json()["job_id"]


def test_repair_kind_requires_ops_token_configuration(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "api-token")
    monkeypatch.delenv("CHATGPTREST_OPS_TOKEN", raising=False)

    client = TestClient(create_app())
    r = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers={
            "Authorization": "Bearer api-token",
            "Idempotency-Key": "repair-auth-missing-ops",
        },
    )

    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "repair_kind_ops_token_not_configured"

