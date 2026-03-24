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
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_create_job_enforces_allowlist_and_trace_headers(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "allowed-client")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    app = create_app()
    client = TestClient(app)

    r1 = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "x"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "wg-create-1"},
    )
    assert r1.status_code == 403
    assert r1.json()["detail"]["error"] == "client_not_allowed"

    r2 = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "x"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "wg-create-2", "X-Client-Name": "allowed-client"},
    )
    assert r2.status_code == 400
    assert r2.json()["detail"]["error"] == "missing_trace_headers"

    r3 = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "x"}, "params": {"repeat": 1}},
        headers={
            "Idempotency-Key": "wg-create-3",
            "X-Client-Name": "allowed-client",
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-1",
        },
    )
    assert r3.status_code == 200
    assert isinstance(r3.json().get("job_id"), str)


def test_cancel_job_enforces_cancel_allowlist_and_reason(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "allowed-client,cancel-client")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST", "cancel-client")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_CANCEL_REASON", "1")

    app = create_app()
    client = TestClient(app)

    create = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "x"}, "params": {"repeat": 1}},
        headers={
            "Idempotency-Key": "wg-cancel-1",
            "X-Client-Name": "allowed-client",
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-1",
        },
    )
    assert create.status_code == 200
    job_id = create.json()["job_id"]

    denied = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers={
            "X-Client-Name": "allowed-client",
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-2",
            "X-Cancel-Reason": "stop",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "cancel_client_not_allowed"

    missing_reason = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers={
            "X-Client-Name": "cancel-client",
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-3",
        },
    )
    assert missing_reason.status_code == 400
    assert missing_reason.json()["detail"]["error"] == "missing_cancel_reason"

    ok = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers={
            "X-Client-Name": "cancel-client",
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-4",
            "X-Cancel-Reason": "manual-stop",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "canceled"
