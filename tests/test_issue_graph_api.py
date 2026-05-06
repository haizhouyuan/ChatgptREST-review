from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core import client_issues
from chatgptrest.core.db import connect
from chatgptrest.core import issue_graph
from ops import export_issue_graph


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    canonical_db = tmp_path / "canonical.sqlite3"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_CANONICAL_DB_PATH", str(canonical_db))
    return {"db_path": db_path, "artifacts_dir": artifacts_dir, "canonical_db": canonical_db}


def _insert_completed_job(conn, *, job_id: str, kind: str, client_name: str, ts: float, answer_chars: int = 128) -> None:
    conn.execute(
        """
        INSERT INTO jobs(
          job_id, kind, input_json, params_json, client_json, phase, status,
          created_at, updated_at, not_before, attempts, max_attempts,
          answer_chars, conversation_url
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            job_id,
            kind,
            "{\"question\":\"继续在同一会话里深挖。\"}",
            "{\"preset\":\"deepthink\"}",
            json.dumps({"name": client_name}, ensure_ascii=False),
            "wait",
            "completed",
            ts,
            ts,
            0.0,
            1,
            3,
            answer_chars,
            f"https://gemini.google.com/app/{job_id}",
        ),
    )


def test_issue_verification_usage_and_graph_query_roundtrip(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    report = client.post(
        "/v1/issues/report",
        json={
            "project": "chatgptrest-mcp",
            "title": "Gemini follow-up cannot continue in same conversation",
            "severity": "P1",
            "kind": "gemini_web.ask",
            "symptom": "conversation_url_conflict",
            "source": "worker_auto",
            "job_id": "job-fail",
            "artifacts_path": "jobs/job-fail",
        },
    )
    assert report.status_code == 200
    issue_id = report.json()["issue_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        _insert_completed_job(conn, job_id="job-ok-1", kind="gemini_web.ask", client_name="chatgptrest-mcp", ts=1_100.0)
        _insert_completed_job(conn, job_id="job-ok-2", kind="gemini_web.ask", client_name="chatgptrest-mcp", ts=1_200.0)
        _insert_completed_job(conn, job_id="job-ok-3", kind="gemini_web.ask", client_name="chatgptrest-mcp", ts=1_300.0)
        conn.commit()

    mitigated = client.post(
        f"/v1/issues/{issue_id}/status",
        json={
            "status": "mitigated",
            "note": "live verifier passed on latest worker",
            "actor": "codex",
            "linked_job_id": "job-ok-1",
            "metadata": {
                "verification_type": "live",
                "verification": {
                    "type": "live",
                    "status": "passed",
                    "verifier": "codex",
                    "job_id": "job-ok-1",
                    "conversation_url": "https://gemini.google.com/app/job-ok-1",
                    "artifacts_path": "jobs/job-ok-1",
                    "metadata": {"lane": "live-smoke"},
                }
            },
        },
    )
    assert mitigated.status_code == 200
    assert mitigated.json()["status"] == "mitigated"

    closed = client.post(
        f"/v1/issues/{issue_id}/status",
        json={
            "status": "closed",
            "note": "3 client successes after mitigated",
            "actor": "openclaw_guardian",
            "linked_job_id": "job-ok-3",
            "metadata": {
                "qualifying_success_job_ids": ["job-ok-1", "job-ok-2", "job-ok-3"],
                "qualifying_successes": [
                    {"job_id": "job-ok-1", "client_name": "chatgptrest-mcp", "kind": "gemini_web.ask", "status": "completed", "answer_chars": 128, "created_at": 1_100.0},
                    {"job_id": "job-ok-2", "client_name": "chatgptrest-mcp", "kind": "gemini_web.ask", "status": "completed", "answer_chars": 128, "created_at": 1_200.0},
                    {"job_id": "job-ok-3", "client_name": "chatgptrest-mcp", "kind": "gemini_web.ask", "status": "completed", "answer_chars": 128, "created_at": 1_300.0},
                ],
            },
        },
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    verifications = client.get(f"/v1/issues/{issue_id}/verification")
    assert verifications.status_code == 200
    verification_rows = verifications.json()["verifications"]
    assert len(verification_rows) == 1
    assert verification_rows[0]["verification_type"] == "live"
    assert verification_rows[0]["job_id"] == "job-ok-1"

    usage = client.get(f"/v1/issues/{issue_id}/usage")
    assert usage.status_code == 200
    usage_rows = usage.json()["usage"]
    assert [row["job_id"] for row in usage_rows] == ["job-ok-3", "job-ok-2", "job-ok-1"]

    graph = client.post(
        "/v1/issues/graph/query",
        json={"issue_id": issue_id, "include_closed": True, "limit": 5, "neighbor_depth": 2},
    )
    assert graph.status_code == 200
    payload = graph.json()
    assert payload["summary"]["read_plane"] == "canonical"
    assert payload["summary"]["match_count"] == 1
    node_kinds = {node["kind"] for node in payload["nodes"]}
    assert {"issue", "family", "verification", "usage", "job"}.issubset(node_kinds)
    edge_types = {edge["type"] for edge in payload["edges"]}
    assert {"belongs_to_family", "validated_by", "proven_by_usage"}.issubset(edge_types)

    snapshot = client.get("/v1/issues/graph/snapshot?include_closed=true&limit=20")
    assert snapshot.status_code == 200
    assert snapshot.json()["summary"]["read_plane"] == "canonical"
    assert snapshot.json()["summary"]["issue_count"] >= 1


def test_export_issue_graph_writes_snapshot(env: dict[str, Path], tmp_path: Path) -> None:
    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        issue, _, _ = client_issues.report_issue(
            conn,
            project="chatgptrest-mcp",
            title="ChatGPT upload retries exhausted",
            severity="P2",
            kind="chatgpt_web.ask",
            symptom="MaxAttemptsExceeded",
            source="worker_auto",
            job_id="job-a",
            now=1_000.0,
        )
        client_issues.record_issue_verification(
            conn,
            issue_id=issue.issue_id,
            verification_type="regression",
            verifier="codex",
            note="regression suite passed",
            job_id="job-a",
            now=1_010.0,
        )
        _insert_completed_job(conn, job_id="job-success", kind="chatgpt_web.ask", client_name="chatgptrest-mcp", ts=1_020.0)
        client_issues.record_issue_usage_evidence(
            conn,
            issue_id=issue.issue_id,
            job_id="job-success",
            client_name="chatgptrest-mcp",
            kind="chatgpt_web.ask",
            now=1_020.0,
        )
        conn.commit()

    json_out = tmp_path / "issue_graph.json"
    md_out = tmp_path / "issue_graph.md"
    rc = export_issue_graph.main(
        [
            "--db-path",
            str(env["db_path"]),
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
            "--max-issues",
            "100",
        ]
    )
    assert rc == 0
    snapshot = json.loads(json_out.read_text(encoding="utf-8"))
    assert snapshot["summary"]["read_plane"] == "canonical"
    assert snapshot["summary"]["issue_count"] == 1
    assert snapshot["summary"]["verification_count"] == 1
    assert snapshot["summary"]["usage_evidence_count"] == 1
    kinds = {node["kind"] for node in snapshot["nodes"]}
    assert {"issue", "family", "verification", "usage", "job"}.issubset(kinds)
    md = md_out.read_text(encoding="utf-8")
    assert "# Issue Knowledge Graph Snapshot" in md
    assert issue.issue_id in md


def test_issue_graph_harvests_legacy_status_events_and_normalizes_query(env: dict[str, Path]) -> None:
    with connect(env["db_path"]) as conn:
        issue, _, _ = client_issues.report_issue(
            conn,
            project="chatgptrest-mcp",
            title="Gemini follow-up cannot continue in same conversation",
            severity="P1",
            kind="gemini_web.ask",
            symptom="conversation_url_conflict",
            source="worker_auto",
            job_id="legacy-job-fail",
            now=1_000.0,
        )
        conn.execute("DELETE FROM client_issue_events WHERE issue_id = ?", (issue.issue_id,))
        conn.execute(
            """
            INSERT INTO client_issue_events(issue_id, ts, type, payload_json)
            VALUES (?,?,?,?)
            """,
            (
                issue.issue_id,
                1_100.0,
                "issue_status_updated",
                json.dumps(
                    {
                        "from": "open",
                        "to": "mitigated",
                        "note": "legacy live verifier passed",
                        "actor": "codex",
                        "linked_job_id": "legacy-job-ok-1",
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        conn.execute(
            """
            INSERT INTO client_issue_events(issue_id, ts, type, payload_json)
            VALUES (?,?,?,?)
            """,
            (
                issue.issue_id,
                1_200.0,
                "issue_status_updated",
                json.dumps(
                    {
                        "from": "mitigated",
                        "to": "closed",
                        "note": "legacy 3-client-success close",
                        "actor": "openclaw_guardian",
                        "linked_job_id": "legacy-job-ok-3",
                        "metadata": {
                            "qualifying_success_job_ids": [
                                "legacy-job-ok-1",
                                "legacy-job-ok-2",
                                "legacy-job-ok-3",
                            ]
                        },
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        _insert_completed_job(conn, job_id="legacy-job-ok-1", kind="gemini_web.ask", client_name="chatgptrest-mcp", ts=1_100.0)
        _insert_completed_job(conn, job_id="legacy-job-ok-2", kind="gemini_web.ask", client_name="chatgptrest-mcp", ts=1_150.0)
        _insert_completed_job(conn, job_id="legacy-job-ok-3", kind="gemini_web.ask", client_name="chatgptrest-mcp", ts=1_200.0)
        conn.commit()

        snapshot = issue_graph.build_issue_graph_snapshot(conn, include_closed=True, max_issues=20)

    assert snapshot["summary"]["verification_count"] >= 1
    assert snapshot["summary"]["usage_evidence_count"] >= 3
    query = issue_graph.query_issue_graph(
        snapshot,
        q="gemini followup same conversation",
        include_closed=True,
        limit=10,
        neighbor_depth=2,
    )
    assert query["summary"]["match_count"] == 1
    kinds = {node["kind"] for node in query["nodes"]}
    assert {"issue", "verification", "usage", "job"}.issubset(kinds)
