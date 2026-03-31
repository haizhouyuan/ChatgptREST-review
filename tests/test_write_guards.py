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
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _job_payload() -> dict[str, object]:
    return {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}}


def test_create_job_enforces_client_allowlist(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "allowed-client")
    app = create_app()
    client = TestClient(app)

    denied = client.post("/v1/jobs", json=_job_payload(), headers={"Idempotency-Key": "allowlist-denied"})
    assert denied.status_code == 403
    detail = denied.json()["detail"]
    assert detail["error"] == "client_not_allowed"

    ok = client.post(
        "/v1/jobs",
        json=_job_payload(),
        headers={"Idempotency-Key": "allowlist-ok", "X-Client-Name": "allowed-client"},
    )
    assert ok.status_code == 200
    assert str(ok.json()["job_id"]).strip()


def test_create_job_enforces_trace_headers_for_write(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    app = create_app()
    client = TestClient(app)

    denied = client.post(
        "/v1/jobs",
        json=_job_payload(),
        headers={"Idempotency-Key": "trace-denied"},
    )
    assert denied.status_code == 400
    detail = denied.json()["detail"]
    assert detail["error"] == "missing_trace_headers"
    assert detail["operation"] == "create_job"

    ok = client.post(
        "/v1/jobs",
        json=_job_payload(),
        headers={
            "Idempotency-Key": "trace-ok",
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-1",
        },
    )
    assert ok.status_code == 200
    assert str(ok.json()["job_id"]).strip()


def test_cancel_job_enforces_trace_headers_for_write(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    app = create_app()
    client = TestClient(app)

    create = client.post(
        "/v1/jobs",
        json=_job_payload(),
        headers={
            "Idempotency-Key": "cancel-trace-create",
            "X-Client-Instance": "ci-create",
            "X-Request-ID": "rid-create",
        },
    )
    assert create.status_code == 200
    job_id = str(create.json()["job_id"])

    denied = client.post(f"/v1/jobs/{job_id}/cancel")
    assert denied.status_code == 400
    detail = denied.json()["detail"]
    assert detail["error"] == "missing_trace_headers"
    assert detail["operation"] == "cancel_job"

    ok = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers={"X-Client-Instance": "ci-cancel", "X-Request-ID": "rid-cancel"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "canceled"
