from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest


def _load_module():
    path = Path(__file__).resolve().parents[1] / "ops" / "backlog_janitor.py"
    spec = importlib.util.spec_from_file_location("backlog_janitor", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def janitor():
    return _load_module()


def test_filter_stale_issues(janitor):
    stale = janitor._filter_stale_issues(
        issues=[
            {"issue_id": "a", "last_seen_at": 100.0},
            {"issue_id": "b", "updated_at": 220.0},
            {"issue_id": "c", "last_seen_at": 50.0},
        ],
        cutoff_ts=150.0,
    )
    assert [x["issue_id"] for x in stale] == ["c", "a"]


def test_apply_issue_mitigations_respects_limit(monkeypatch: pytest.MonkeyPatch, janitor):
    calls: list[dict[str, object]] = []

    def _fake_http_json_request(**kwargs):  # noqa: ANN003
        calls.append(dict(kwargs))
        return True, {"ok": True}, 200

    monkeypatch.setattr(janitor.time, "time", lambda: 10_000.0)
    monkeypatch.setattr(janitor, "_http_json_request", _fake_http_json_request)

    updated_ids, failures = janitor._apply_issue_mitigations(
        base_url="http://127.0.0.1:18711",
        issues=[
            {"issue_id": "iss-1", "last_seen_at": 1000.0, "latest_job_id": "j1"},
            {"issue_id": "iss-2", "last_seen_at": 2000.0, "latest_job_id": "j2"},
        ],
        max_updates=1,
        actor="backlog_janitor",
        note_prefix="auto",
        timeout_seconds=2.0,
    )

    assert failures == []
    assert updated_ids == ["iss-1"]
    assert len(calls) == 1
    assert calls[0]["method"] == "POST"
    assert str(calls[0]["url"]).endswith("/v1/issues/iss-1/status")
    body = calls[0]["body"]
    assert isinstance(body, dict)
    assert body["status"] == "mitigated"
    assert body["actor"] == "backlog_janitor"


def test_query_stale_jobs(tmp_path: Path, janitor):
    db_path = tmp_path / "jobdb.sqlite3"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE jobs (
              job_id TEXT PRIMARY KEY,
              kind TEXT NOT NULL,
              status TEXT NOT NULL,
              phase TEXT,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              attempts INTEGER,
              max_attempts INTEGER,
              last_error_type TEXT,
              last_error TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO jobs(job_id,kind,status,phase,created_at,updated_at,attempts,max_attempts,last_error_type,last_error) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("j-old", "chatgpt_web.ask", "needs_followup", "wait", 100.0, 200.0, 1, 3, "RuntimeError", "x"),
        )
        conn.execute(
            "INSERT INTO jobs(job_id,kind,status,phase,created_at,updated_at,attempts,max_attempts,last_error_type,last_error) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("j-new", "chatgpt_web.ask", "needs_followup", "wait", 100.0, 900.0, 1, 3, "RuntimeError", "y"),
        )
        conn.execute(
            "INSERT INTO jobs(job_id,kind,status,phase,created_at,updated_at,attempts,max_attempts,last_error_type,last_error) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("j-completed", "chatgpt_web.ask", "completed", "wait", 100.0, 100.0, 1, 3, None, None),
        )
        conn.commit()
    finally:
        conn.close()

    rows = janitor._query_stale_jobs(
        db_path=db_path,
        statuses=["needs_followup", "blocked", "cooldown"],
        cutoff_ts=300.0,
        limit=50,
    )
    assert [x["job_id"] for x in rows] == ["j-old"]
    assert rows[0]["status"] == "needs_followup"

