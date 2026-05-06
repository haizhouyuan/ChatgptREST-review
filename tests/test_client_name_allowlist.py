from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.api import routes_jobs as routes
from chatgptrest.api import write_guards


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_OPS_TOKEN", "ops-token")
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _headers(*, idem: str | None = None, client_name: str | None = None, client_instance: str | None = None,
             request_id: str | None = None, cancel_reason: str | None = None) -> dict[str, str]:
    headers = {"Authorization": "Bearer ops-token"}
    if idem:
        headers["Idempotency-Key"] = idem
    if client_name:
        headers["X-Client-Name"] = client_name
    if client_instance:
        headers["X-Client-Instance"] = client_instance
    if request_id:
        headers["X-Request-ID"] = request_id
    if cancel_reason:
        headers["X-Cancel-Reason"] = cancel_reason
    return headers


def test_allowlist_blocks_create_without_client_name(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers=_headers(idem="allowlist-missing-name"),
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["error"] == "client_not_allowed"
    assert detail["allowed_client_names"] == ["chatgptrest-mcp"]


def test_allowlist_blocks_create_with_non_allowed_client_name(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers={
            **_headers(idem="allowlist-wrong-name"),
            "X-Client-Name": "chatgptrestctl",
        },
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["error"] == "client_not_allowed"
    assert detail["x_client_name"] == "chatgptrestctl"


def test_allowlist_allows_mcp_create_and_cancel(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")
    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers={
            **_headers(idem="allowlist-allowed-create"),
            "X-Client-Name": "chatgptrest-mcp",
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    blocked_cancel = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers=_headers(client_name="chatgptrestctl"),
    )
    assert blocked_cancel.status_code == 403
    assert blocked_cancel.json()["detail"]["error"] == "client_not_allowed"

    ok_cancel = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers=_headers(client_name="chatgptrest-mcp"),
    )
    assert ok_cancel.status_code == 200
    assert ok_cancel.json()["status"] == "canceled"


def test_allowlist_fallback_client_blocked_when_mcp_is_up(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")
    monkeypatch.setenv("CHATGPTREST_ALLOW_FALLBACK_WHEN_MCP_DOWN", "1")
    monkeypatch.setenv("CHATGPTREST_FALLBACK_CLIENT_NAME_ALLOWLIST_WHEN_MCP_DOWN", "chatgptrestctl")
    monkeypatch.setattr(write_guards, "_mcp_probe_reachable", lambda: True)
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers={
            **_headers(idem="allowlist-fallback-up"),
            "X-Client-Name": "chatgptrestctl",
        },
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["error"] == "client_not_allowed"
    assert detail["mcp_probe"]["reachable"] is True


def test_allowlist_fallback_client_allowed_when_mcp_is_down(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")
    monkeypatch.setenv("CHATGPTREST_ALLOW_FALLBACK_WHEN_MCP_DOWN", "1")
    monkeypatch.setenv("CHATGPTREST_FALLBACK_CLIENT_NAME_ALLOWLIST_WHEN_MCP_DOWN", "chatgptrestctl")
    monkeypatch.setattr(write_guards, "_mcp_probe_reachable", lambda: False)
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers={
            **_headers(idem="allowlist-fallback-down"),
            "X-Client-Name": "chatgptrestctl",
        },
    )
    assert r.status_code == 200
    assert r.json()["job_id"]


def test_cancel_allowlist_blocks_mcp_cancel_but_allows_ctl(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp,chatgptrestctl")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST", "chatgptrestctl")
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers={
            **_headers(idem="cancel-allowlist-create"),
            "X-Client-Name": "chatgptrest-mcp",
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    blocked = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers=_headers(client_name="chatgptrest-mcp"),
    )
    assert blocked.status_code == 403
    detail = blocked.json()["detail"]
    assert detail["error"] == "cancel_client_not_allowed"
    assert detail["x_client_name"] == "chatgptrest-mcp"
    assert detail["allowed_cancel_client_names"] == ["chatgptrestctl"]

    ok = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers=_headers(client_name="chatgptrestctl"),
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "canceled"


def test_cancel_allowlist_fallback_client_allowed_when_mcp_is_down(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")
    monkeypatch.setenv("CHATGPTREST_ALLOW_FALLBACK_WHEN_MCP_DOWN", "1")
    monkeypatch.setenv("CHATGPTREST_FALLBACK_CLIENT_NAME_ALLOWLIST_WHEN_MCP_DOWN", "chatgptrestctl")
    monkeypatch.setattr(write_guards, "_mcp_probe_reachable", lambda: False)
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers={
            **_headers(idem="cancel-fallback-down-create"),
            "X-Client-Name": "chatgptrest-mcp",
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    cancel = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers=_headers(client_name="chatgptrestctl"),
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "canceled"


def test_cancel_allowlist_fallback_client_blocked_when_mcp_is_up(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp,chatgptrestctl")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")
    monkeypatch.setenv("CHATGPTREST_ALLOW_FALLBACK_WHEN_MCP_DOWN", "1")
    monkeypatch.setenv("CHATGPTREST_FALLBACK_CLIENT_NAME_ALLOWLIST_WHEN_MCP_DOWN", "chatgptrestctl")
    monkeypatch.setattr(write_guards, "_mcp_probe_reachable", lambda: True)
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers={
            **_headers(idem="cancel-fallback-up-create"),
            "X-Client-Name": "chatgptrest-mcp",
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    blocked = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers=_headers(client_name="chatgptrestctl"),
    )
    assert blocked.status_code == 403
    detail = blocked.json()["detail"]
    assert detail["error"] == "cancel_client_not_allowed"
    assert detail["mcp_probe"]["reachable"] is True


def test_require_trace_headers_blocks_write_when_missing(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    app = create_app()
    client = TestClient(app)

    missing = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers=_headers(idem="trace-missing-1"),
    )
    assert missing.status_code == 400
    detail = missing.json()["detail"]
    assert detail["error"] == "missing_trace_headers"
    assert "X-Client-Instance" in detail["missing_headers"]
    assert "X-Request-ID" in detail["missing_headers"]

    ok = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers={
            **_headers(idem="trace-ok-1"),
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-1",
        },
    )
    assert ok.status_code == 200


def test_require_cancel_reason_and_trace_headers(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_CANCEL_REASON", "1")
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/v1/jobs",
        json={"kind": "repair.check", "input": {"symptom": "x"}, "params": {}},
        headers={
            **_headers(idem="cancel-reason-create"),
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-create-1",
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    missing_reason = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers={
            **_headers(),
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-cancel-1",
        },
    )
    assert missing_reason.status_code == 400
    assert missing_reason.json()["detail"]["error"] == "missing_cancel_reason"

    ok = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers={
            **_headers(),
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-cancel-2",
            "X-Cancel-Reason": "manual triage close",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "canceled"

    events = client.get(
        f"/v1/jobs/{job_id}/events?after_id=0&limit=200",
        headers={"Authorization": "Bearer ops-token"},
    )
    assert events.status_code == 200
    cancel_events = [e for e in events.json()["events"] if e.get("type") == "cancel_requested"]
    assert cancel_events
    payload = cancel_events[-1].get("payload") or {}
    assert payload.get("reason") == "manual triage close"
