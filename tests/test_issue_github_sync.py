from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from chatgptrest.core import client_issues
from chatgptrest.core.db import connect


def _load_sync_module():
    path = Path(__file__).resolve().parents[1] / "chatgptrest" / "ops_shared" / "issue_github_sync.py"
    spec = importlib.util.spec_from_file_location("issue_github_sync", str(path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    return {"db_path": db_path}


def test_sync_issue_creates_github_issue_and_persists_metadata(env: dict[str, Path]):
    mod = _load_sync_module()
    with connect(env["db_path"]) as conn:
        issue, _created, _info = client_issues.report_issue(
            conn,
            project="chatgptrest",
            title="Gemini ask path unstable",
            severity="P1",
            kind="gemini_web.ask",
            symptom="needs_followup loop",
            raw_error="WaitNoProgressTimeout",
            source="worker_auto",
            job_id="job-1",
        )
        conn.commit()

        calls: list[list[str]] = []

        def fake_gh(args):  # noqa: ANN001
            calls.append(list(args))
            return {
                "number": 501,
                "html_url": "https://github.com/haizhouyuan/ChatgptREST/issues/501",
                "state": "open",
            }

        out = mod.sync_issue_to_github(
            conn,
            issue=issue,
            repo="haizhouyuan/ChatgptREST",
            gh_api=fake_gh,
            dry_run=False,
        )
        conn.commit()
        updated = client_issues.get_issue(conn, issue_id=issue.issue_id)

    assert out["action"] == "created"
    assert updated is not None
    assert isinstance(updated.metadata, dict)
    gh_meta = updated.metadata["github_issue"]
    assert gh_meta["number"] == 501
    assert gh_meta["repo"] == "haizhouyuan/ChatgptREST"
    assert gh_meta["synced_status"] == "open"
    assert any("repos/haizhouyuan/ChatgptREST/issues" in arg for arg in calls[0])
    assert "labels[]=P1" in calls[0]
    assert "labels[]=domain/gemini" in calls[0]


def test_sync_issue_closes_existing_github_issue_when_ledger_closes(env: dict[str, Path]):
    mod = _load_sync_module()
    with connect(env["db_path"]) as conn:
        issue, _created, _info = client_issues.report_issue(
            conn,
            project="chatgptrest",
            title="Background wait stuck",
            severity="P1",
            kind="mcp.wait",
            symptom="watch never resumes",
            raw_error="RemoteDisconnected",
            source="worker_auto",
        )
        updated = mod._store_issue_metadata(  # noqa: SLF001
            conn,
            issue=issue,
            patch={
                "github_issue": {
                    "repo": "haizhouyuan/ChatgptREST",
                    "number": 777,
                    "url": "https://github.com/haizhouyuan/ChatgptREST/issues/777",
                    "state": "open",
                    "synced_status": "open",
                }
            },
            event_type="seed",
            payload={"seed": True},
        )
        issue = client_issues.update_issue_status(
            conn,
            issue_id=updated.issue_id,
            status="closed",
            note="fixed in mainline",
        )
        calls: list[list[str]] = []

        def fake_gh(args):  # noqa: ANN001
            calls.append(list(args))
            return {"ok": True}

        out = mod.sync_issue_to_github(
            conn,
            issue=issue,
            repo="haizhouyuan/ChatgptREST",
            gh_api=fake_gh,
            dry_run=False,
        )
        conn.commit()
        final = client_issues.get_issue(conn, issue_id=issue.issue_id)

    assert out["action"] == "commented,closed"
    assert final is not None
    assert final.metadata["github_issue"]["state"] == "closed"
    assert any("/issues/777/comments" in arg for call in calls for arg in call)
    assert any("state=closed" in arg for call in calls for arg in call)
