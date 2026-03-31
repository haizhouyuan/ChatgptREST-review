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


def test_cancel_requested_event_includes_request_metadata(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    r = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "cancel-meta"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    c = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers={
            "User-Agent": "unit-test/1.0",
            "X-Client-Name": "homeagent",
            "X-Client-Instance": "ci-1",
            "X-Request-Id": "rid-123",
            "X-Cancel-Reason": "unit test cancel",
        },
    )
    assert c.status_code == 200
    assert c.json()["status"] == "canceled"

    ev = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=200")
    assert ev.status_code == 200
    events = ev.json()["events"]
    cancel_events = [e for e in events if e.get("type") == "cancel_requested"]
    assert cancel_events
    payload = cancel_events[-1]["payload"]
    assert isinstance(payload, dict)
    by = payload.get("by")
    assert isinstance(by, dict)
    assert by.get("transport") == "http"
    headers = by.get("headers")
    assert isinstance(headers, dict)
    assert headers.get("user_agent") == "unit-test/1.0"
    assert headers.get("x_client_name") == "homeagent"
    assert headers.get("x_client_instance") == "ci-1"
    assert headers.get("x_request_id") == "rid-123"
    assert headers.get("x_cancel_reason") == "unit test cancel"
    assert payload.get("reason") == "unit test cancel"
