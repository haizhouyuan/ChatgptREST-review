from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest


def _load_guardian_module():
    path = Path(__file__).resolve().parents[1] / "ops" / "openclaw_guardian_run.py"
    spec = importlib.util.spec_from_file_location("openclaw_guardian_run", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def guardian():
    return _load_guardian_module()


def test_issue_autoclose_disabled_when_hours_zero(guardian) -> None:
    out = guardian._sweep_client_issue_autoclose(
        base_url="http://127.0.0.1:18711",
        stale_hours=0,
        max_updates=50,
        source="worker_auto",
        statuses=["open", "in_progress"],
        actor="openclaw_guardian",
        timeout_seconds=1.0,
    )
    assert out["enabled"] is False
    assert out["updated"] == 0
    assert out["eligible"] == 0


def test_build_parser_defaults_match_topology(guardian) -> None:
    parser = guardian.build_parser()
    args = parser.parse_args([])
    # Aligned with config/topology.yaml sidecars.guardian (Issue #126)
    assert args.agent_id == "main"
    assert args.session_id == "main-guardian"


def test_auth_headers_for_v1_surfaces(monkeypatch: pytest.MonkeyPatch, guardian) -> None:
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "api-token")
    monkeypatch.setenv("CHATGPTREST_OPS_TOKEN", "ops-token")

    assert guardian._auth_headers_for_url("http://127.0.0.1:18711/healthz") == {
        "Authorization": "Bearer api-token"
    }
    assert guardian._auth_headers_for_url("http://127.0.0.1:18711/v1/issues?status=open") == {
        "Authorization": "Bearer api-token"
    }
    assert guardian._auth_headers_for_url("http://127.0.0.1:18711/v1/ops/status") == {
        "Authorization": "Bearer ops-token"
    }


def test_auth_headers_fallback_when_only_ops_token_present(monkeypatch: pytest.MonkeyPatch, guardian) -> None:
    monkeypatch.delenv("CHATGPTREST_API_TOKEN", raising=False)
    monkeypatch.setenv("CHATGPTREST_OPS_TOKEN", "ops-token")

    assert guardian._auth_headers_for_url("http://127.0.0.1:18711/healthz") == {
        "Authorization": "Bearer ops-token"
    }


def test_chatgptrest_auth_headers_use_ops_token_only_for_ops_paths(monkeypatch: pytest.MonkeyPatch, guardian) -> None:
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "api-token")
    monkeypatch.setenv("CHATGPTREST_OPS_TOKEN", "ops-token")

    assert guardian._chatgptrest_auth_headers(url="http://127.0.0.1:18711/healthz") == {
        "Authorization": "Bearer api-token"
    }
    assert guardian._chatgptrest_auth_headers(url="http://127.0.0.1:18711/v1/issues") == {
        "Authorization": "Bearer api-token"
    }
    assert guardian._chatgptrest_auth_headers(url="http://127.0.0.1:18711/v1/ops/status") == {
        "Authorization": "Bearer ops-token"
    }


def test_collect_report_warns_when_tokens_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    guardian,
) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    conn = guardian.sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE jobs (
                job_id TEXT,
                kind TEXT,
                status TEXT,
                phase TEXT,
                created_at REAL,
                updated_at REAL,
                input_json TEXT,
                params_json TEXT,
                last_error_type TEXT,
                last_error TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.delenv("CHATGPTREST_API_TOKEN", raising=False)
    monkeypatch.delenv("CHATGPTREST_OPS_TOKEN", raising=False)
    monkeypatch.setattr(guardian, "_MISSING_TOKEN_WARNING_EMITTED", False)
    monkeypatch.setattr(guardian, "_http_json", lambda *args, **kwargs: (True, {"ok": True}))

    with caplog.at_level("WARNING"):
        report = guardian._collect_report(
            db_path=db_path,
            base_url="http://127.0.0.1:18711",
            lookback_minutes=5,
            max_rows=10,
            include_orch_report=False,
            orch_report_path=tmp_path / "missing.json",
        )

    assert report["health"]["ok"] is True
    assert "guardian is running without CHATGPTREST_API_TOKEN/CHATGPTREST_OPS_TOKEN" in caplog.text


def test_issue_autoclose_updates_only_stale_issues(monkeypatch: pytest.MonkeyPatch, guardian) -> None:
    now = 10_000.0
    calls: list[dict[str, Any]] = []

    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "api-token")
    monkeypatch.setattr(guardian.time, "time", lambda: now)
    monkeypatch.setattr(
        guardian,
        "_iter_client_issues",
        lambda **kwargs: [
            {
                "issue_id": "iss_stale",
                "last_seen_at": now - 73 * 3600,
                "updated_at": now - 73 * 3600,
                "latest_job_id": "job_stale",
            },
            {
                "issue_id": "iss_fresh",
                "last_seen_at": now - 2 * 3600,
                "updated_at": now - 2 * 3600,
                "latest_job_id": "job_fresh",
            },
        ],
    )

    def _fake_http_json_request(**kwargs):
        calls.append(dict(kwargs))
        return True, {"ok": True}, 200

    monkeypatch.setattr(guardian, "_http_json_request", _fake_http_json_request)

    out = guardian._sweep_client_issue_autoclose(
        base_url="http://127.0.0.1:18711",
        stale_hours=72,
        max_updates=10,
        source="worker_auto",
        statuses=["open", "in_progress"],
        actor="openclaw_guardian",
        timeout_seconds=2.0,
    )

    assert out["enabled"] is True
    assert out["listed"] == 2
    assert out["eligible"] == 1
    assert out["updated"] == 1
    assert out["updated_issue_ids"] == ["iss_stale"]
    assert len(calls) == 1
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"].endswith("/v1/issues/iss_stale/status")
    assert calls[0]["headers"]["Authorization"] == "Bearer api-token"
    assert calls[0]["body"]["status"] == "mitigated"
    assert calls[0]["body"]["linked_job_id"] == "job_stale"
    assert calls[0]["body"]["metadata"]["verification_type"] == "quiet_window"


def test_issue_close_sweep_closes_mitigated_after_three_client_successes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, guardian) -> None:
    from chatgptrest.core import client_issues
    from chatgptrest.core.db import connect, init_db

    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "api-token")
    db_path = tmp_path / "jobdb.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        issue, _, _ = client_issues.report_issue(
            conn,
            project="chatgptrest-mcp",
            title="Gemini follow-up thread handoff broken",
            severity="P1",
            kind="gemini_web.ask",
            symptom="conversation_url_conflict",
            source="worker_auto",
            job_id="job_fail",
            now=1_000.0,
        )
        client_issues.update_issue_status(
            conn,
            issue_id=issue.issue_id,
            status=client_issues.CLIENT_ISSUE_STATUS_MITIGATED,
            note="live verified",
            actor="codex",
            now=1_100.0,
        )
        for idx, ts in enumerate((1_200.0, 1_300.0, 1_400.0), start=1):
            conn.execute(
                """
                INSERT INTO jobs(
                  job_id, kind, input_json, params_json, client_json, phase, status,
                  created_at, updated_at, not_before, attempts, max_attempts
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    f"job_ok_{idx}",
                    "gemini_web.ask",
                    "{\"question\":\"继续上一次研究，补充结果。\"}",
                    "{}",
                    "{\"name\":\"chatgptrest-mcp\"}",
                    "wait",
                    "completed",
                    ts,
                    ts,
                    0.0,
                    1,
                    3,
                ),
            )
        conn.commit()

    calls: list[dict[str, Any]] = []

    def _fake_http_json_request(**kwargs):
        calls.append(dict(kwargs))
        return True, {"ok": True}, 200

    monkeypatch.setattr(guardian, "_http_json_request", _fake_http_json_request)

    out = guardian._sweep_client_issue_autoclose_closed(
        db_path=db_path,
        base_url="http://127.0.0.1:18711",
        source="worker_auto",
        actor="openclaw_guardian",
        timeout_seconds=2.0,
        required_successes=3,
        max_updates=10,
    )

    assert out["enabled"] is True
    assert out["listed"] == 1
    assert out["eligible"] == 1
    assert out["updated"] == 1
    assert out["updated_issue_ids"] == [issue.issue_id]
    assert len(calls) == 1
    assert calls[0]["url"].endswith(f"/v1/issues/{issue.issue_id}/status")
    assert calls[0]["headers"]["Authorization"] == "Bearer api-token"
    assert calls[0]["body"]["status"] == "closed"
    assert calls[0]["body"]["metadata"]["qualifying_success_job_ids"] == [
        "job_ok_1",
        "job_ok_2",
        "job_ok_3",
    ]
    assert [row["job_id"] for row in calls[0]["body"]["metadata"]["qualifying_successes"]] == [
        "job_ok_1",
        "job_ok_2",
        "job_ok_3",
    ]


def test_run_guardian_agent_handles_missing_openclaw(monkeypatch: pytest.MonkeyPatch, guardian, tmp_path: Path) -> None:
    def _raise_missing(*args, **kwargs):
        raise FileNotFoundError("openclaw")

    monkeypatch.setattr(guardian.subprocess, "run", _raise_missing)
    out = guardian._run_guardian_agent(
        openclaw_cmd="openclaw",
        agent_id="chatgptrest-guardian",
        session_id="chatgptrest-guardian-main",
        report_path=tmp_path / "report.json",
        timeout_seconds=10,
    )
    assert out["ok"] is False
    assert out["resolved"] is False
    assert out["error_type"] == "FileNotFoundError"


def test_notify_feishu_channel_handles_missing_openclaw(monkeypatch: pytest.MonkeyPatch, guardian) -> None:
    def _raise_missing(*args, **kwargs):
        raise FileNotFoundError("openclaw")

    monkeypatch.setattr(guardian.subprocess, "run", _raise_missing)
    out = guardian._notify_feishu_channel(
        openclaw_cmd="openclaw",
        target="ops-group",
        text="hello",
        account=None,
    )
    assert out["ok"] is False
    assert out["error_type"] == "FileNotFoundError"


def test_run_guardian_agent_uses_resolved_openclaw_cmd(monkeypatch: pytest.MonkeyPatch, guardian, tmp_path: Path) -> None:
    class _Proc:
        returncode = 0
        stdout = '{"result":{"payloads":[{"text":"{\\"resolved\\": true}"}]}}'
        stderr = ""

    monkeypatch.setattr(guardian.shutil, "which", lambda cmd: "/tmp/openclaw-bin" if cmd == "openclaw" else None)
    monkeypatch.setattr(guardian.subprocess, "run", lambda *args, **kwargs: _Proc())
    out = guardian._run_guardian_agent(
        openclaw_cmd="openclaw",
        agent_id="chatgptrest-guardian",
        session_id="chatgptrest-guardian-main",
        report_path=tmp_path / "report.json",
        timeout_seconds=10,
    )
    assert out["ok"] is True
    assert out["resolved"] is True
    assert out["command"][0] == "/tmp/openclaw-bin"
    prompt = out["command"][out["command"].index("--message") + 1]
    assert "不要调用 ops/openclaw_orch_agent.py --reconcile" in prompt


def test_run_guardian_agent_falls_back_to_main_when_named_agent_missing(
    monkeypatch: pytest.MonkeyPatch,
    guardian,
    tmp_path: Path,
) -> None:
    class _Proc:
        returncode = 0
        stdout = '{"result":{"payloads":[{"text":"{\\"resolved\\": false}"}]}}'
        stderr = ""

    state_dir = tmp_path / ".openclaw"
    (state_dir / "agents" / "main").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(state_dir))
    monkeypatch.setattr(guardian.shutil, "which", lambda cmd: "/tmp/openclaw-bin" if cmd == "openclaw" else None)
    monkeypatch.setattr(guardian.subprocess, "run", lambda *args, **kwargs: _Proc())

    out = guardian._run_guardian_agent(
        openclaw_cmd="openclaw",
        agent_id="chatgptrest-guardian",
        session_id="chatgptrest-guardian-main",
        report_path=tmp_path / "report.json",
        timeout_seconds=10,
    )

    assert out["command"][out["command"].index("--agent") + 1] == "main"
    assert out["requested_agent_id"] == "chatgptrest-guardian"
    assert out["resolved_agent_id"] == "main"


def test_resolve_openclaw_cmd_supports_official_home_overlay(monkeypatch: pytest.MonkeyPatch, guardian, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(guardian.shutil, "which", lambda cmd: None)
    bin_path = tmp_path / ".home-codex-official" / ".local" / "bin" / "openclaw"
    bin_path.parent.mkdir(parents=True, exist_ok=True)
    bin_path.write_text("", encoding="utf-8")
    assert guardian._resolve_openclaw_cmd("openclaw") == str(bin_path)
