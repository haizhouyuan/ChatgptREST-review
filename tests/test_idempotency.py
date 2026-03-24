from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "50")
    return create_app()


def test_idempotency_replay(app):
    client = TestClient(app)
    payload = {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}}
    r1 = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "k1"})
    assert r1.status_code == 200
    job_id = r1.json()["job_id"]
    r2 = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "k1"})
    assert r2.status_code == 200
    assert r2.json()["job_id"] == job_id


def test_idempotency_collision(app):
    client = TestClient(app)
    r1 = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "a"}, "params": {}},
        headers={"Idempotency-Key": "k2"},
    )
    assert r1.status_code == 200
    existing_job_id = r1.json()["job_id"]
    r2 = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "b"}, "params": {}},
        headers={"Idempotency-Key": "k2"},
    )
    assert r2.status_code == 409
    body = r2.json()
    assert body["detail"]["error"] == "idempotency_collision"
    assert body["detail"]["idempotency_key"] == "k2"
    assert body["detail"]["existing_job_id"] == existing_job_id
    assert body["detail"]["existing_request_hash"]
    assert body["detail"]["request_hash"]
