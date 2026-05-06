from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.config import load_config
from chatgptrest.executors.base import ExecutorResult
from chatgptrest.worker import worker as worker_mod
from chatgptrest.worker.worker import _run_once


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    monkeypatch.setenv("CHATGPTREST_ISSUE_AUTOREPORT_ENABLED", "1")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_worker_auto_reports_error_into_issue_ledger(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    payload = {
        "kind": "dummy.error_meta",
        "input": {},
        "params": {},
        "client": {"project": "research"},
    }
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "auto-issue-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w-auto", lease_ttl_seconds=60))
    assert ran is True

    issues_resp = client.get("/v1/issues?source=worker_auto&limit=10")
    assert issues_resp.status_code == 200
    issues = issues_resp.json()["issues"]
    assert len(issues) == 1
    issue = issues[0]
    assert issue["project"] == "research"
    assert issue["kind"] == "dummy.error_meta"
    assert issue["latest_job_id"] == job_id
    assert issue["source"] == "worker_auto"
    assert issue["count"] == 1
    assert issue["title"].startswith("dummy.error_meta error")
    assert "meta error" in str(issue.get("raw_error") or "")

    issues_all_resp = client.get("/v1/issues?limit=10")
    assert issues_all_resp.status_code == 200
    assert len(issues_all_resp.json()["issues"]) == 1

    executor_resp = client.get("/v1/issues?source=executor_auto&limit=10")
    assert executor_resp.status_code == 200
    assert executor_resp.json()["issues"] == []

    events_resp = client.get(f"/v1/jobs/{job_id}/events?after_id=0&limit=50")
    assert events_resp.status_code == 200
    assert any(evt["type"] == "issue_auto_reported" for evt in events_resp.json()["events"])


def test_worker_auto_report_status_filter(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_ISSUE_AUTOREPORT_STATUSES", "blocked")
    app = create_app()
    client = TestClient(app)

    payload = {"kind": "dummy.error_meta", "input": {}, "params": {}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "auto-issue-filter-1"})
    assert r.status_code == 200

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w-auto", lease_ttl_seconds=60))
    assert ran is True

    issues_resp = client.get("/v1/issues?source=worker_auto&limit=10")
    assert issues_resp.status_code == 200
    assert issues_resp.json()["issues"] == []


def test_worker_auto_report_uses_final_db_status_on_max_attempts(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_MAX_ATTEMPTS", "1")
    app = create_app()
    client = TestClient(app)

    payload = {"kind": "dummy.echo", "input": {"text": "x"}, "params": {"repeat": 1}}
    r = client.post("/v1/jobs", json=payload, headers={"Idempotency-Key": "auto-issue-max-attempts-1"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    class _CooldownExecutor:
        async def run(self, *, job_id: str, kind: str, input: dict, params: dict):  # noqa: A002
            return ExecutorResult(
                status="cooldown",
                answer="",
                answer_format="text",
                meta={"error_type": "RuntimeError", "error": "temporary upstream failure", "retry_after_seconds": 1},
            )

    monkeypatch.setattr(worker_mod, "_executor_for_job", lambda cfg, kind, tool_caller=None: _CooldownExecutor())

    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w-auto", lease_ttl_seconds=60))
    assert ran is True

    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["status"] == "error"
    assert job.json()["reason_type"] == "MaxAttemptsExceeded"

    issues_resp = client.get("/v1/issues?source=worker_auto&limit=10")
    assert issues_resp.status_code == 200
    issues = issues_resp.json()["issues"]
    assert len(issues) == 1
    assert issues[0]["latest_job_id"] == job_id
    assert "maxattemptsexceeded" in issues[0]["title"].lower()


def test_error_signature_fragment_normalizes_dynamic_url_and_uuid() -> None:
    e1 = worker_mod._error_signature_fragment(  # noqa: SLF001
        error_type="RuntimeError",
        error="wait failed for https://chatgpt.com/c/6999f70a-7920-83a2-be3e-b16a183f9def with token 123456",
    )
    e2 = worker_mod._error_signature_fragment(  # noqa: SLF001
        error_type="RuntimeError",
        error="wait failed for https://chatgpt.com/c/11111111-2222-3333-4444-555555555555 with token 999999",
    )
    assert e1 == e2
