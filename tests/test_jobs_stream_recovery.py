from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.db import connect


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _create_dummy_job(client: TestClient, *, idempotency_key: str) -> str:
    r = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "hi"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": idempotency_key},
    )
    assert r.status_code == 200
    return str(r.json()["job_id"])


def _create_gemini_job(client: TestClient, *, idempotency_key: str) -> str:
    r = client.post(
        "/v1/jobs",
        json={"kind": "gemini_web.ask", "input": {"question": "hi"}, "params": {"preset": "pro"}},
        headers={"Idempotency-Key": idempotency_key},
    )
    assert r.status_code == 200
    return str(r.json()["job_id"])


def _collect_sse(response: TestClient) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    current_event: str | None = None
    current_data: str | None = None
    for raw_line in response.iter_lines():
        line = raw_line.strip()
        if not line:
            if current_event is not None and current_data is not None:
                events.append((current_event, json.loads(current_data)))
            current_event = None
            current_data = None
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            current_data = line.split(":", 1)[1].strip()
    if current_event is not None and current_data is not None:
        events.append((current_event, json.loads(current_data)))
    return events


def test_job_view_exposes_recovery_fields_for_cooldown(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    job_id = _create_dummy_job(client, idempotency_key="recovery-cooldown-1")

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE jobs SET status='cooldown', not_before=?, last_error_type=?, last_error=? WHERE job_id=?",
            (2000000000.0, "DriveUploadNotReady", "drive upload pending", job_id),
        )
        conn.commit()

    view = client.get(f"/v1/jobs/{job_id}").json()
    assert view["status"] == "cooldown"
    assert view["recovery_status"] == "recovering"
    assert view["safe_next_action"] == "wait"
    assert "auto-retry" in str(view["recovery_detail"] or "")


def test_job_view_escalates_provider_login_followup(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    job_id = _create_gemini_job(client, idempotency_key="recovery-login-1")

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE jobs SET status='needs_followup', last_error_type=?, last_error=? WHERE job_id=?",
            ("GeminiNotLoggedIn", "Gemini requires login", job_id),
        )
        conn.commit()

    view = client.get(f"/v1/jobs/{job_id}").json()
    assert view["status"] == "needs_followup"
    assert view["recovery_status"] == "needs_human"
    assert view["safe_next_action"] == "escalate"
    assert "Provider issue" in str(view["recovery_detail"] or "")


def test_job_stream_emits_status_events_and_done_for_terminal_job(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)
    job_id = _create_dummy_job(client, idempotency_key="stream-terminal-1")

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE jobs SET status='cooldown', not_before=?, last_error_type=?, last_error=? WHERE job_id=?",
            (2000000000.0, "DriveUploadNotReady", "drive upload pending", job_id),
        )
        conn.execute(
            "INSERT INTO job_events(job_id, ts, type, payload_json) VALUES (?,?,?,?)",
            (job_id, 123.0, "status_changed", json.dumps({"from": "in_progress", "to": "cooldown"})),
        )
        conn.commit()

    with client.stream("GET", f"/v1/jobs/{job_id}/stream") as response:
        assert response.status_code == 200
        events = _collect_sse(response)

    assert events[0][0] == "status"
    assert events[-1] == ("done", {"status": "cooldown", "job_id": job_id})
    status_payload = events[0][1]
    assert status_payload["status"] == "cooldown"
    assert status_payload["recovery_status"] == "recovering"
    assert status_payload["safe_next_action"] == "wait"
    job_events = [payload for event, payload in events if event == "job_event"]
    assert any(payload["type"] == "status_changed" for payload in job_events)
    status_changed = next(payload for payload in job_events if payload["type"] == "status_changed")
    assert status_changed["payload"] == {"from": "in_progress", "to": "cooldown"}
