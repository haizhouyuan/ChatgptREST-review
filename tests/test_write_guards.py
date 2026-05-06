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
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _job_payload() -> dict[str, object]:
    return {"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}}


def _audit_rows(artifacts_dir: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted((artifacts_dir / "monitor" / "api_rejections").glob("*.jsonl")):
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return rows


def test_create_job_enforces_client_allowlist(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "allowed-client")
    app = create_app()
    client = TestClient(app)

    denied = client.post("/v1/jobs", json=_job_payload(), headers={"Idempotency-Key": "allowlist-denied"})
    assert denied.status_code == 403
    detail = denied.json()["detail"]
    assert detail["error"] == "client_not_allowed"
    rows = _audit_rows(env["artifacts_dir"])
    assert rows[-1]["status_code"] == 403
    assert rows[-1]["path"] == "/v1/jobs"
    assert rows[-1]["idempotency_key"] == "allowlist-denied"
    assert rows[-1]["detail"]["error"] == "client_not_allowed"

    ok = client.post(
        "/v1/jobs",
        json=_job_payload(),
        headers={"Idempotency-Key": "allowlist-ok", "X-Client-Name": "allowed-client"},
    )
    assert ok.status_code == 200
    assert str(ok.json()["job_id"]).strip()


def test_auth_middleware_records_rejection_audit(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "test-api-token")
    app = create_app()
    client = TestClient(app)

    denied = client.post("/v1/jobs", json=_job_payload(), headers={"Idempotency-Key": "auth-denied"})

    assert denied.status_code == 401
    rows = _audit_rows(env["artifacts_dir"])
    assert rows[-1]["status_code"] == 401
    assert rows[-1]["source"] == "auth_middleware"
    assert rows[-1]["idempotency_key"] == "auth-denied"
    assert rows[-1]["authorization_present"] is False
    assert rows[-1]["detail"]["error"] == "unauthorized"


def test_public_ingress_is_blocked_before_auth(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "test-api-token")
    monkeypatch.setenv("CHATGPTREST_REJECT_PUBLIC_INGRESS", "1")
    app = create_app()
    client = TestClient(app, client=("127.0.0.1", 50000))

    denied = client.post(
        "/v1/jobs",
        json=_job_payload(),
        headers={"Idempotency-Key": "public-ingress-denied", "X-Forwarded-For": "8.8.8.8"},
    )

    assert denied.status_code == 403
    detail = denied.json()["detail"]
    assert detail["error"] == "public_ingress_blocked"
    assert detail["client_ip"] == "8.8.8.8"
    rows = _audit_rows(env["artifacts_dir"])
    assert rows[-1]["source"] == "public_ingress_middleware"
    assert rows[-1]["detail"]["error"] == "public_ingress_blocked"


def test_tunnel_or_tailscale_ingress_is_allowed(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_REJECT_PUBLIC_INGRESS", "1")
    app = create_app()
    client = TestClient(app, client=("127.0.0.1", 50000))

    ok = client.post(
        "/v1/jobs",
        json=_job_payload(),
        headers={"Idempotency-Key": "tailscale-ingress-ok", "X-Forwarded-For": "100.124.54.52"},
    )

    assert ok.status_code == 200
    assert ok.json()["kind"] == "dummy.echo"


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
