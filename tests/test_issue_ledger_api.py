from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.config import load_config
from chatgptrest.worker.worker import _run_once


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_issue_report_dedupes_and_reopens_mitigated(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    payload = {
        "project": "research",
        "title": "Deep Research returned tool-call JSON only",
        "severity": "P1",
        "kind": "chatgpt_web.ask",
        "symptom": "answer only contains connector/tool JSON",
        "raw_error": "no正文",
        "job_id": "job-a",
        "conversation_url": "https://chatgpt.com/c/abc",
        "artifacts_path": "jobs/job-a",
        "tags": ["deep_research", "export"],
    }
    r1 = client.post("/v1/issues/report", json=payload)
    assert r1.status_code == 200
    b1 = r1.json()
    issue_id = b1["issue_id"]
    assert b1["created"] is True
    assert b1["reopened"] is False
    assert b1["status"] == "open"
    assert b1["count"] == 1
    assert b1["latest_job_id"] == "job-a"

    payload2 = dict(payload)
    payload2["job_id"] = "job-b"
    r2 = client.post("/v1/issues/report", json=payload2)
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["issue_id"] == issue_id
    assert b2["created"] is False
    assert b2["status"] == "open"
    assert b2["count"] == 2
    assert b2["latest_job_id"] == "job-b"

    up = client.post(f"/v1/issues/{issue_id}/status", json={"status": "mitigated", "note": "added guard"})
    assert up.status_code == 200
    assert up.json()["status"] == "mitigated"

    payload3 = dict(payload)
    payload3["job_id"] = "job-c"
    r3 = client.post("/v1/issues/report", json=payload3)
    assert r3.status_code == 200
    b3 = r3.json()
    assert b3["issue_id"] == issue_id
    assert b3["created"] is False
    assert b3["reopened"] is True
    assert b3["status"] == "open"
    assert b3["count"] == 3
    assert b3["latest_job_id"] == "job-c"

    ev = client.get(f"/v1/issues/{issue_id}/events?after_id=0&limit=50")
    assert ev.status_code == 200
    types = [x["type"] for x in ev.json()["events"]]
    assert types.count("issue_reported") >= 3
    assert "issue_status_updated" in types


def test_issue_list_filters_and_pagination(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    for project, title, severity, source in [
        ("research", "Issue A", "P1", "codex"),
        ("research", "Issue B", "P2", "worker_auto"),
        ("planning", "Issue C", "P1", "codex"),
    ]:
        r = client.post(
            "/v1/issues/report",
            json={
                "project": project,
                "title": title,
                "severity": severity,
                "kind": "chatgpt_web.ask",
                "symptom": "s",
                "source": source,
            },
        )
        assert r.status_code == 200
        time.sleep(0.02)

    p1 = client.get("/v1/issues?project=research&limit=1")
    assert p1.status_code == 200
    b1 = p1.json()
    assert len(b1["issues"]) == 1
    first_issue_id = b1["issues"][0]["issue_id"]
    assert b1["issues"][0]["project"] == "research"
    assert b1["next_before_ts"] is not None
    assert b1["next_before_issue_id"] is not None

    p2 = client.get(
        f"/v1/issues?project=research&limit=5&before_ts={b1['next_before_ts']}&before_issue_id={b1['next_before_issue_id']}"
    )
    assert p2.status_code == 200
    b2 = p2.json()
    assert all(x["project"] == "research" for x in b2["issues"])
    assert all(x["issue_id"] != first_issue_id for x in b2["issues"])

    sev = client.get("/v1/issues?project=research&severity=P1&limit=10")
    assert sev.status_code == 200
    sev_issues = sev.json()["issues"]
    assert len(sev_issues) == 1
    assert sev_issues[0]["severity"] == "P1"

    src = client.get("/v1/issues?source=worker_auto&limit=10")
    assert src.status_code == 200
    src_issues = src.json()["issues"]
    assert len(src_issues) == 1
    assert src_issues[0]["title"] == "Issue B"

    kind = client.get("/v1/issues?kind=chatgpt_web.ask&limit=10")
    assert kind.status_code == 200
    kind_issues = kind.json()["issues"]
    assert len(kind_issues) == 3

    one = src_issues[0]
    fp = client.get(f"/v1/issues?fingerprint_hash={one['fingerprint_hash']}&limit=10")
    assert fp.status_code == 200
    fp_issues = fp.json()["issues"]
    assert len(fp_issues) == 1
    assert fp_issues[0]["issue_id"] == one["issue_id"]

    fp_text = client.get("/v1/issues?fingerprint_text=issue b&limit=10")
    assert fp_text.status_code == 200
    assert any(x["title"] == "Issue B" for x in fp_text.json()["issues"])

    all_resp = client.get("/v1/issues?limit=10")
    assert all_resp.status_code == 200
    all_issues = all_resp.json()["issues"]
    assert len(all_issues) == 3
    mid_updated = sorted(float(x["updated_at"]) for x in all_issues)[1]

    since_resp = client.get(f"/v1/issues?since_ts={mid_updated}&limit=10")
    assert since_resp.status_code == 200
    since_issues = since_resp.json()["issues"]
    assert since_issues
    assert all(float(x["updated_at"]) >= mid_updated for x in since_issues)

    until_resp = client.get(f"/v1/issues?until_ts={mid_updated}&limit=10")
    assert until_resp.status_code == 200
    until_issues = until_resp.json()["issues"]
    assert until_issues
    assert all(float(x["updated_at"]) <= mid_updated for x in until_issues)


def test_issue_link_evidence_and_invalid_status(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    create = client.post(
        "/v1/issues/report",
        json={
            "project": "research",
            "title": "Gemini ERR_CONNECTION_CLOSED",
            "severity": "P1",
            "kind": "gemini_web.ask",
            "symptom": "net::ERR_CONNECTION_CLOSED",
        },
    )
    assert create.status_code == 200
    issue_id = create.json()["issue_id"]

    evd = client.post(
        f"/v1/issues/{issue_id}/evidence",
        json={
            "job_id": "job-z",
            "conversation_url": "https://gemini.google.com/app/123",
            "artifacts_path": "jobs/job-z",
            "note": "reproduced in send phase",
            "source": "codex",
            "metadata": {"attempts": 20},
        },
    )
    assert evd.status_code == 200
    b = evd.json()
    assert b["latest_job_id"] == "job-z"
    assert b["latest_conversation_url"] == "https://gemini.google.com/app/123"
    assert b["latest_artifacts_path"] == "jobs/job-z"
    assert b["source"] == "codex"

    ev = client.get(f"/v1/issues/{issue_id}/events?after_id=0&limit=20")
    assert ev.status_code == 200
    assert any(x["type"] == "issue_evidence_linked" for x in ev.json()["events"])

    bad = client.post(f"/v1/issues/{issue_id}/status", json={"status": "done"})
    assert bad.status_code == 400


def test_issue_report_rejects_completed_job_by_default(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    create_job = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "ok"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "issue-completed-guard-1"},
    )
    assert create_job.status_code == 200
    job_id = create_job.json()["job_id"]
    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w-issues", lease_ttl_seconds=60))
    assert ran is True
    job = client.get(f"/v1/jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["status"] == "completed"

    report = client.post(
        "/v1/issues/report",
        json={
            "project": "research",
            "title": "mistaken stall report",
            "severity": "P2",
            "kind": "dummy.echo",
            "job_id": job_id,
            "source": "codex",
            "symptom": "looked stalled",
        },
    )
    assert report.status_code == 409
    detail = report.json().get("detail") or {}
    assert detail.get("error") == "IssueReportJobAlreadyCompleted"
    assert detail.get("job_id") == job_id


def test_issue_report_allows_completed_job_with_override(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    create_job = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "ok"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "issue-completed-guard-2"},
    )
    assert create_job.status_code == 200
    job_id = create_job.json()["job_id"]
    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w-issues", lease_ttl_seconds=60))
    assert ran is True

    report = client.post(
        "/v1/issues/report",
        json={
            "project": "research",
            "title": "postmortem for completed job",
            "severity": "P2",
            "kind": "dummy.echo",
            "job_id": job_id,
            "source": "codex",
            "symptom": "postmortem analysis",
            "metadata": {"allow_resolved_job": True},
            "tags": ["postmortem"],
        },
    )
    assert report.status_code == 200
    body = report.json()
    assert body["created"] is True
    assert body["latest_job_id"] == job_id


def test_issue_report_rejects_completed_jobs_from_metadata_job_ids(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    create_job = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "ok"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "issue-completed-guard-3"},
    )
    assert create_job.status_code == 200
    completed_job_id = create_job.json()["job_id"]
    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w-issues", lease_ttl_seconds=60))
    assert ran is True

    report = client.post(
        "/v1/issues/report",
        json={
            "project": "research",
            "title": "mistaken stall report by metadata jobs",
            "severity": "P2",
            "kind": "dummy.echo",
            "source": "codex",
            "metadata": {"job_ids": [completed_job_id]},
        },
    )
    assert report.status_code == 409
    detail = report.json().get("detail") or {}
    assert detail.get("error") == "IssueReportJobAlreadyCompleted"
    assert completed_job_id in (detail.get("job_ids") or [])


def test_issue_report_allows_mixed_metadata_job_ids(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    create_completed = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "ok"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "issue-completed-guard-4-completed"},
    )
    assert create_completed.status_code == 200
    completed_job_id = create_completed.json()["job_id"]
    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w-issues", lease_ttl_seconds=60))
    assert ran is True

    create_pending = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "pending"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "issue-completed-guard-4-pending"},
    )
    assert create_pending.status_code == 200
    pending_job_id = create_pending.json()["job_id"]

    report = client.post(
        "/v1/issues/report",
        json={
            "project": "research",
            "title": "mixed job states should still allow issue report",
            "severity": "P2",
            "kind": "dummy.echo",
            "source": "codex",
            "metadata": {"job_ids": [completed_job_id, pending_job_id]},
        },
    )
    assert report.status_code == 200
    body = report.json()
    assert body["created"] is True
    assert body["latest_job_id"] == pending_job_id


def test_issue_report_allows_completed_not_final_research_job(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    create_job = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "ok"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "issue-completed-not-final"},
    )
    assert create_job.status_code == 200
    job_id = create_job.json()["job_id"]
    ran = asyncio.run(_run_once(cfg=load_config(), worker_id="w-issues", lease_ttl_seconds=60))
    assert ran is True

    result_path = env["artifacts_dir"] / "jobs" / job_id / "result.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload["completion_contract"]["answer_state"] = "provisional"
    payload["completion_contract"]["finality_reason"] = "completed_under_min_chars"
    payload["canonical_answer"] = {
        "record_version": "v1",
        "ready": False,
        "answer_state": "provisional",
        "finality_reason": "completed_under_min_chars",
        "authoritative_answer_path": payload["path"],
        "answer_chars": payload["answer_chars"],
        "answer_format": payload["answer_format"],
        "answer_provenance": {"contract_class": "research"},
        "export_available": False,
        "widget_export_available": False,
    }
    result_path.write_text(json.dumps(payload), encoding="utf-8")

    report = client.post(
        "/v1/issues/report",
        json={
            "project": "research",
            "title": "completed but not final research answer",
            "severity": "P2",
            "kind": "dummy.echo",
            "job_id": job_id,
            "source": "codex",
            "symptom": "still waiting for authoritative final answer",
        },
    )
    assert report.status_code == 200
    body = report.json()
    assert body["created"] is True
    assert body["latest_job_id"] == job_id
