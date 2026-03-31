from __future__ import annotations

import importlib.util
import json
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


def test_apply_stale_job_cleanup_finalizes_retryable_jobs(tmp_path: Path, janitor):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
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
              not_before REAL NOT NULL DEFAULT 0,
              attempts INTEGER,
              max_attempts INTEGER,
              last_error_type TEXT,
              last_error TEXT,
              lease_owner TEXT,
              lease_expires_at REAL,
              lease_token TEXT,
              conversation_url TEXT,
              conversation_id TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE job_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              job_id TEXT NOT NULL,
              ts REAL NOT NULL,
              type TEXT NOT NULL,
              payload_json TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO jobs(job_id,kind,status,phase,created_at,updated_at,not_before,attempts,max_attempts,last_error_type,last_error,lease_owner,lease_expires_at,lease_token,conversation_url,conversation_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "j-old",
                "chatgpt_web.ask",
                "needs_followup",
                "wait",
                100.0,
                200.0,
                0.0,
                1,
                3,
                "RuntimeError",
                "x",
                "w1",
                999.0,
                "lease-1",
                "https://chatgpt.com/c/test",
                "conv-test",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    updated_ids, failures = janitor._apply_stale_job_cleanup(
        db_path=db_path,
        artifacts_dir=artifacts_dir,
        jobs=[
            {
                "job_id": "j-old",
                "status": "needs_followup",
                "phase": "wait",
                "updated_at": 200.0,
            }
        ],
        max_updates=10,
        actor="backlog_janitor",
        note_prefix="auto finalized stale job",
    )

    assert failures == []
    assert updated_ids == ["j-old"]

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT status, last_error_type, last_error, lease_owner, lease_expires_at, lease_token FROM jobs WHERE job_id = ?",
            ("j-old",),
        ).fetchone()
        event_rows = conn.execute(
            "SELECT type, payload_json FROM job_events WHERE job_id = ? ORDER BY id ASC",
            ("j-old",),
        ).fetchall()
    finally:
        conn.close()

    assert row is not None
    assert row["status"] == "error"
    assert row["last_error_type"] == "BacklogJanitorStale"
    assert "auto finalized stale job" in str(row["last_error"] or "")
    assert row["lease_owner"] is None
    assert row["lease_expires_at"] is None
    assert row["lease_token"] is None
    assert [str(ev["type"]) for ev in event_rows] == ["status_changed", "stale_job_finalized"]

    result_path = artifacts_dir / "jobs" / "j-old" / "result.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["status"] == "error"
    assert payload["error_type"] == "BacklogJanitorStale"
