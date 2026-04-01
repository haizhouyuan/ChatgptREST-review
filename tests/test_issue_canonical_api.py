from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core import client_issues, issue_canonical
from chatgptrest.core.db import connect


def _insert_completed_job(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    kind: str,
    client_name: str,
    ts: float,
    answer_chars: int = 128,
) -> None:
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
            "{\"question\":\"继续在同一会话里追问。\"}",
            "{\"preset\":\"deepthink\"}",
            f'{{"name":"{client_name}"}}',
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


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    canonical_db = tmp_path / "canonical.sqlite3"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_CANONICAL_DB_PATH", str(canonical_db))
    return {"db_path": db_path, "artifacts_dir": artifacts_dir, "canonical_db": canonical_db}


def test_issue_canonical_query_and_export_roundtrip(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    report = client.post(
        "/v1/issues/report",
        json={
            "project": "ChatgptREST",
            "title": "Gemini wait timeout on follow-up",
            "severity": "P1",
            "kind": "gemini_web.ask",
            "symptom": "WaitNoThreadUrlTimeout",
            "source": "worker_auto",
            "job_id": "job-fail",
            "artifacts_path": "jobs/job-fail",
        },
    )
    assert report.status_code == 200
    issue_id = report.json()["issue_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        _insert_completed_job(
            conn,
            job_id="job-ok-1",
            kind="gemini_web.ask",
            client_name="chatgptrest-mcp",
            ts=1_100.0,
        )
        client_issues.record_issue_verification(
            conn,
            issue_id=issue_id,
            verification_type="live",
            verifier="codex",
            note="live verifier passed",
            job_id="job-ok-1",
            conversation_url="https://gemini.google.com/app/job-ok-1",
            artifacts_path="jobs/job-ok-1",
            metadata={"lane": "live-smoke"},
            now=1_101.0,
        )
        client_issues.record_issue_usage_evidence(
            conn,
            issue_id=issue_id,
            job_id="job-ok-1",
            client_name="chatgptrest-mcp",
            kind="gemini_web.ask",
            status="completed",
            answer_chars=128,
            metadata={"lane": "live-smoke"},
            now=1_102.0,
        )
        conn.commit()

    query = client.post(
        "/v1/issues/canonical/query",
        json={"issue_id": issue_id, "status": "open", "limit": 10},
    )
    assert query.status_code == 200
    payload = query.json()
    assert payload["summary"]["domain"] == "issue_domain"
    assert payload["summary"]["read_plane"] == "canonical"
    assert payload["summary"]["match_count"] == 1
    assert payload["matches"][0]["issue_id"] == issue_id
    obj = payload["objects"][0]
    assert obj["object_id"] == f"issue:{issue_id}"
    assert obj["status"] == "open"
    assert obj["payload"]["verification_count"] == 1
    assert obj["payload"]["usage_count"] == 1
    projection_names = {row["projection_name"] for row in obj["projections"]}
    assert projection_names == {"graph", "ledger_ref"}
    graph_projection = next(row for row in obj["projections"] if row["projection_name"] == "graph")
    assert graph_projection["payload"]["kind"] == "issue"

    export = client.get("/v1/issues/canonical/export?status=open&limit=20")
    assert export.status_code == 200
    export_payload = export.json()
    assert export_payload["summary"]["read_plane"] == "canonical"
    assert export_payload["summary"]["object_count"] == 1
    assert export_payload["summary"]["projection_counts"]["graph"] == 1
    assert export_payload["summary"]["projection_counts"]["ledger_ref"] == 1

    with sqlite3.connect(str(env["canonical_db"])) as conn:
        issue_count = conn.execute(
            "SELECT COUNT(*) FROM canonical_objects WHERE domain = 'issue_domain' AND object_type = 'Issue'"
        ).fetchone()[0]
        verification_count = conn.execute(
            "SELECT COUNT(*) FROM canonical_objects WHERE domain = 'issue_domain' AND object_type = 'Verification'"
        ).fetchone()[0]
        usage_count = conn.execute(
            "SELECT COUNT(*) FROM canonical_objects WHERE domain = 'issue_domain' AND object_type = 'UsageEvidence'"
        ).fetchone()[0]
    assert issue_count == 1
    assert verification_count == 1
    assert usage_count == 1


def test_issue_canonical_export_handles_list_metadata_values(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    report = client.post(
        "/v1/issues/report",
        json={
            "project": "ChatgptREST",
            "title": "Canonical export handles list metadata",
            "severity": "P2",
            "kind": "chatgpt_web.ask",
            "symptom": "Issue family matcher should not crash on list metadata",
            "source": "worker_auto",
            "metadata": {
                "related_jobs": ["job-a", "job-b"],
                "surface": "canonical-export-smoke",
            },
        },
    )
    assert report.status_code == 200

    export = client.get("/v1/issues/canonical/export?status=open&limit=20")
    assert export.status_code == 200
    payload = export.json()
    assert payload["summary"]["read_plane"] == "canonical"
    assert payload["summary"]["object_count"] >= 1


def test_issue_graph_query_uses_canonical_when_available(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    report = client.post(
        "/v1/issues/report",
        json={
            "project": "ChatgptREST",
            "title": "Legacy graph route now prefers canonical",
            "severity": "P2",
            "kind": "chatgpt_web.ask",
            "symptom": "MaxAttemptsExceeded",
            "source": "worker_auto",
            "job_id": "job-legacy",
        },
    )
    assert report.status_code == 200
    issue_id = report.json()["issue_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        _insert_completed_job(
            conn,
            job_id="job-legacy-success",
            kind="chatgpt_web.ask",
            client_name="chatgptrest-mcp",
            ts=2_000.0,
        )
        client_issues.record_issue_verification(
            conn,
            issue_id=issue_id,
            verification_type="regression",
            verifier="codex",
            note="graph route canonical smoke",
            job_id="job-legacy-success",
            now=2_001.0,
        )
        conn.commit()

    graph = client.post(
        "/v1/issues/graph/query",
        json={"issue_id": issue_id, "include_closed": True, "limit": 5, "neighbor_depth": 2},
    )
    assert graph.status_code == 200
    graph_payload = graph.json()
    assert graph_payload["summary"]["read_plane"] == "canonical"
    assert graph_payload["summary"]["match_count"] == 1
    assert any(node["kind"] == "verification" for node in graph_payload["nodes"])
    snapshot = client.get("/v1/issues/graph/snapshot?include_closed=true&limit=20")
    assert snapshot.status_code == 200
    assert snapshot.json()["summary"]["read_plane"] == "canonical"


def test_issue_graph_query_falls_back_without_canonical_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.delenv("CHATGPTREST_CANONICAL_DB_PATH", raising=False)
    monkeypatch.setattr(
        issue_canonical,
        "query_issue_graph_preferred",
        lambda **_: (_ for _ in ()).throw(issue_canonical.IssueCanonicalUnavailable("canonical unavailable")),
    )

    app = create_app()
    client = TestClient(app)
    report = client.post(
        "/v1/issues/report",
        json={
            "project": "ChatgptREST",
            "title": "Fallback graph route still works",
            "severity": "P2",
            "kind": "chatgpt_web.ask",
            "symptom": "MaxAttemptsExceeded",
            "source": "worker_auto",
            "job_id": "job-fallback",
        },
    )
    assert report.status_code == 200
    issue_id = report.json()["issue_id"]

    graph = client.post(
        "/v1/issues/graph/query",
        json={"issue_id": issue_id, "include_closed": True, "limit": 5, "neighbor_depth": 1},
    )
    assert graph.status_code == 200
    payload = graph.json()
    assert payload["summary"]["read_plane"] == "legacy_fallback"
    assert payload["summary"]["match_count"] == 1


def test_issue_canonical_sync_ignores_query_limit_for_coverage(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    total_issues = 242
    for idx in range(total_issues):
        report = client.post(
            "/v1/issues/report",
            json={
                "project": "ChatgptREST",
                "title": f"Historical issue {idx}",
                "severity": "P2",
                "kind": "gemini_web.ask",
                "symptom": f"WaitNoThreadUrlTimeout family sample {idx}",
                "source": "worker_auto",
                "job_id": f"job-{idx:03d}",
            },
        )
        assert report.status_code == 200

    export = client.get("/v1/issues/canonical/export?limit=10")
    assert export.status_code == 200
    payload = export.json()
    assert payload["summary"]["read_plane"] == "canonical"
    assert payload["summary"]["authoritative_issue_count"] == total_issues
    assert payload["summary"]["canonical_issue_count"] == total_issues
    assert payload["summary"]["coverage_gap_count"] == 0
    assert payload["summary"]["missing_issue_ids"] == []
    assert payload["summary"]["object_count"] == 10

    with sqlite3.connect(str(env["canonical_db"])) as conn:
        issue_count = conn.execute(
            "SELECT COUNT(*) FROM canonical_objects WHERE domain = 'issue_domain' AND object_type = 'Issue'"
        ).fetchone()[0]
    assert issue_count == total_issues


def test_issue_canonical_marks_synthesized_evidence_provenance(env: dict[str, Path]) -> None:
    app = create_app()
    client = TestClient(app)

    report = client.post(
        "/v1/issues/report",
        json={
            "project": "ChatgptREST",
            "title": "Gemini wait family historical close path",
            "severity": "P1",
            "kind": "gemini_web.ask",
            "symptom": "WaitNoProgressTimeout",
            "source": "worker_auto",
            "job_id": "job-historical",
        },
    )
    assert report.status_code == 200
    issue_id = report.json()["issue_id"]

    with connect(env["db_path"]) as conn:
        conn.execute("BEGIN IMMEDIATE")
        _insert_completed_job(
            conn,
            job_id="job-historical-ok-1",
            kind="gemini_web.ask",
            client_name="chatgptrest-mcp",
            ts=3_000.0,
        )
        conn.execute(
            """
            UPDATE client_issues
            SET status = ?, updated_at = ?, closed_at = ?, latest_job_id = ?
            WHERE issue_id = ?
            """,
            (
                client_issues.CLIENT_ISSUE_STATUS_CLOSED,
                3_002.0,
                3_002.0,
                "job-historical-ok-1",
                issue_id,
            ),
        )
        conn.execute(
            """
            INSERT INTO client_issue_events(issue_id, ts, type, payload_json)
            VALUES (?,?,?,?)
            """,
            (
                issue_id,
                3_001.0,
                "issue_status_updated",
                json.dumps(
                    {
                        "from": "open",
                        "to": "mitigated",
                        "note": "legacy live verifier passed",
                        "actor": "codex",
                        "linked_job_id": "job-historical-ok-1",
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
                issue_id,
                3_002.0,
                "issue_status_updated",
                json.dumps(
                    {
                        "from": "mitigated",
                        "to": "closed",
                        "note": "legacy 3-client-success close",
                        "actor": "openclaw_guardian",
                        "linked_job_id": "job-historical-ok-1",
                        "metadata": {"qualifying_success_job_ids": ["job-historical-ok-1"]},
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        conn.commit()

    export = client.get(f"/v1/issues/canonical/export?status=closed&limit=20")
    assert export.status_code == 200

    with sqlite3.connect(str(env["canonical_db"])) as conn:
        conn.row_factory = sqlite3.Row
        verification_row = conn.execute(
            """
            SELECT authority_level, payload_json
            FROM canonical_objects
            WHERE domain = 'issue_domain'
              AND object_type = 'Verification'
            ORDER BY object_id ASC
            LIMIT 1
            """
        ).fetchone()
        verification_source = conn.execute(
            """
            SELECT source_table, source_pk, payload_json
            FROM object_sources
            WHERE object_id = (
              SELECT object_id
              FROM canonical_objects
              WHERE domain = 'issue_domain'
                AND object_type = 'Verification'
              ORDER BY object_id ASC
              LIMIT 1
            )
            """
        ).fetchone()
        usage_row = conn.execute(
            """
            SELECT authority_level, payload_json
            FROM canonical_objects
            WHERE domain = 'issue_domain'
              AND object_type = 'UsageEvidence'
            ORDER BY object_id ASC
            LIMIT 1
            """
        ).fetchone()
        usage_source = conn.execute(
            """
            SELECT source_table, source_pk, payload_json
            FROM object_sources
            WHERE object_id = (
              SELECT object_id
              FROM canonical_objects
              WHERE domain = 'issue_domain'
                AND object_type = 'UsageEvidence'
              ORDER BY object_id ASC
              LIMIT 1
            )
            """
        ).fetchone()

    assert verification_row is not None
    assert verification_source is not None
    verification_payload = json.loads(str(verification_row["payload_json"]))
    verification_source_payload = json.loads(str(verification_source["payload_json"]))
    assert verification_row["authority_level"] == "derived"
    assert verification_source["source_table"] == "client_issue_events"
    assert verification_payload["evidence_provenance"]["synthetic"] is True
    assert verification_payload["evidence_provenance"]["derived_from"]["event_type"] == "issue_status_updated"
    assert verification_source_payload["metadata"]["synthetic"] is True

    assert usage_row is not None
    assert usage_source is not None
    usage_payload = json.loads(str(usage_row["payload_json"]))
    usage_source_payload = json.loads(str(usage_source["payload_json"]))
    assert usage_row["authority_level"] == "derived"
    assert usage_source["source_table"] == "client_issue_events"
    assert usage_payload["evidence_provenance"]["synthetic"] is True
    assert usage_payload["evidence_provenance"]["derived_from"]["event_type"] == "issue_status_updated"
    assert usage_source_payload["metadata"]["synthetic"] is True


def test_issue_canonical_family_registry_and_doc_evidence(
    env: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir(parents=True, exist_ok=True)
    (docs_root / "provider_contract.md").write_text(
        "provider_job_kind_contract_drift: Unknown job kind remediation checklist\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CHATGPTREST_DOCS_ROOT", str(docs_root))

    app = create_app()
    client = TestClient(app)

    for idx in range(2):
        report = client.post(
            "/v1/issues/report",
            json={
                "project": "ChatgptREST",
                "title": f"Qwen provider contract drift {idx}",
                "severity": "P2",
                "kind": "qwen_web.ask",
                "symptom": "ValueError: Unknown job kind: qwen_web.ask",
                "source": "worker_auto",
                "job_id": f"job-qwen-{idx}",
            },
        )
        assert report.status_code == 200

    export = client.get("/v1/issues/canonical/export?status=open&limit=20")
    assert export.status_code == 200
    export_payload = export.json()
    assert {obj["payload"]["family_id"] for obj in export_payload["objects"]} == {"provider_job_kind_contract_drift"}

    snapshot = client.get("/v1/issues/graph/snapshot?include_closed=true&limit=20")
    assert snapshot.status_code == 200
    payload = snapshot.json()
    assert payload["summary"]["read_plane"] == "canonical"
    assert payload["summary"]["family_count"] == 1
    assert payload["summary"]["doc_evidence_count"] >= 1

    doc_nodes = [node for node in payload["nodes"] if node["kind"] == "document_evidence"]
    assert doc_nodes
    doc_attrs = doc_nodes[0]["attrs"]
    assert doc_attrs["source_locator"] == "L1"
    assert "Unknown job kind remediation checklist" in doc_attrs["excerpt"]
    assert doc_attrs["content_hash"]
