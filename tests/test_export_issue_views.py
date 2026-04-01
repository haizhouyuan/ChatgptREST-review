from __future__ import annotations

import json
from pathlib import Path

import pytest

from chatgptrest.core import client_issues, issue_canonical
from chatgptrest.core.db import connect, init_db
from ops import export_issue_views


def test_export_issue_views_writes_open_list_and_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    canonical_db = tmp_path / "canonical.sqlite3"
    json_out = tmp_path / "artifacts" / "latest.json"
    md_out = tmp_path / "artifacts" / "latest.md"
    hist_json_out = tmp_path / "artifacts" / "history.json"
    hist_md_out = tmp_path / "artifacts" / "history.md"
    init_db(db_path)
    monkeypatch.setenv("CHATGPTREST_CANONICAL_DB_PATH", str(canonical_db))

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        issue_a, _, _ = client_issues.report_issue(
            conn,
            project="ChatgptREST",
            title="Gemini wait timeout on follow-up",
            severity="P1",
            kind="gemini_web.ask",
            symptom="WaitNoThreadUrlTimeout",
            source="worker_auto",
            job_id="job-a",
            now=1_000.0,
        )
        issue_b, _, _ = client_issues.report_issue(
            conn,
            project="ChatgptREST",
            title="ChatGPT upload retries exhausted",
            severity="P2",
            kind="chatgpt_web.ask",
            symptom="MaxAttemptsExceeded",
            source="worker_auto",
            job_id="job-b",
            now=1_100.0,
        )
        client_issues.update_issue_status(
            conn,
            issue_id=issue_b.issue_id,
            status=client_issues.CLIENT_ISSUE_STATUS_MITIGATED,
            note="live verifier passed",
            actor="codex",
            now=1_200.0,
        )
        client_issues.link_issue_evidence(
            conn,
            issue_id=issue_a.issue_id,
            artifacts_path="jobs/job-a",
            note="still reproducible",
            source="codex",
            now=1_300.0,
        )
        conn.commit()

    rc = export_issue_views.main(
        [
            "--db-path",
            str(db_path),
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
            "--history-json-out",
            str(hist_json_out),
            "--history-md-out",
            str(hist_md_out),
            "--active-limit",
            "20",
            "--recent-limit",
            "20",
            "--history-limit",
            "20",
        ]
    )
    assert rc == 0

    snapshot = json.loads(json_out.read_text(encoding="utf-8"))
    assert snapshot["summary"]["read_plane"] == "canonical"
    assert snapshot["summary"]["total_issues"] == 2
    assert snapshot["summary"]["active_issues"] == 1
    assert snapshot["summary"]["recently_settled"] == 1
    assert snapshot["active_issues"][0]["issue_id"] == issue_a.issue_id
    assert snapshot["recently_settled"][0]["issue_id"] == issue_b.issue_id

    md = md_out.read_text(encoding="utf-8")
    assert "# Open Issue List" in md
    assert issue_a.issue_id in md
    assert "Gemini wait timeout on follow-up" in md

    history = json.loads(hist_json_out.read_text(encoding="utf-8"))
    assert history["event_count"] >= 4
    event_types = [row["type"] for row in history["events"]]
    assert "issue_status_updated" in event_types
    assert "issue_evidence_linked" in event_types

    hist_md = hist_md_out.read_text(encoding="utf-8")
    assert "# Issue History Evolution Snapshot" in hist_md
    assert "issue_status_updated" in hist_md


def test_export_issue_views_falls_back_without_canonical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    json_out = tmp_path / "artifacts" / "latest.json"
    md_out = tmp_path / "artifacts" / "latest.md"
    hist_json_out = tmp_path / "artifacts" / "history.json"
    hist_md_out = tmp_path / "artifacts" / "history.md"
    init_db(db_path)
    monkeypatch.delenv("CHATGPTREST_CANONICAL_DB_PATH", raising=False)
    monkeypatch.setattr(
        issue_canonical,
        "build_issue_views_snapshot_from_canonical",
        lambda **_: (_ for _ in ()).throw(issue_canonical.IssueCanonicalUnavailable("canonical unavailable")),
    )

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        client_issues.report_issue(
            conn,
            project="ChatgptREST",
            title="Fallback open issue list",
            severity="P2",
            kind="chatgpt_web.ask",
            symptom="MaxAttemptsExceeded",
            source="worker_auto",
            job_id="job-fallback",
            now=2_000.0,
        )
        conn.commit()

    rc = export_issue_views.main(
        [
            "--db-path",
            str(db_path),
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
            "--history-json-out",
            str(hist_json_out),
            "--history-md-out",
            str(hist_md_out),
        ]
    )
    assert rc == 0
    snapshot = json.loads(json_out.read_text(encoding="utf-8"))
    assert snapshot["summary"]["read_plane"] == "legacy_fallback"
