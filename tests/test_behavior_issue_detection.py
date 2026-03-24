from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from chatgptrest.core.db import connect, init_db, insert_event
from chatgptrest.core import job_store
from chatgptrest.core import client_issues
from chatgptrest.ops_shared.behavior_issues import (
    BehaviorIssueSubsystem,
    detect_behavior_issue_candidates,
)
from chatgptrest.ops_shared.subsystem import TickContext


def _load_maint_daemon_module():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "ops" / "maint_daemon.py"
    spec = importlib.util.spec_from_file_location("chatgptrest_ops_maint_daemon_behavior", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _create_web_job(
    conn: sqlite3.Connection,
    *,
    artifacts_dir: Path,
    idem: str,
    question: str,
    client_name: str,
    kind: str = "gemini_web.ask",
    params: dict | None = None,
    parent_job_id: str | None = None,
) -> str:
    input_payload = {"question": question}
    if parent_job_id:
        input_payload["parent_job_id"] = parent_job_id
    job = job_store.create_job(
        conn,
        artifacts_dir=artifacts_dir,
        idempotency_key=idem,
        kind=kind,
        input=input_payload,
        params=dict(params or {}),
        client={"name": client_name},
        max_attempts=3,
        parent_job_id=parent_job_id,
    )
    return str(job.job_id)


def _mark_job(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    status: str,
    created_at: float,
    updated_at: float,
    conversation_url: str | None = None,
    conversation_id: str | None = None,
    answer_chars: int | None = None,
) -> None:
    conn.execute(
        """
        UPDATE jobs
        SET status = ?,
            created_at = ?,
            updated_at = ?,
            conversation_url = ?,
            conversation_id = ?,
            answer_chars = ?
        WHERE job_id = ?
        """,
        (
            str(status),
            float(created_at),
            float(updated_at),
            (str(conversation_url).strip() if conversation_url else None),
            (str(conversation_id).strip() if conversation_id else None),
            (int(answer_chars) if answer_chars is not None else None),
            str(job_id),
        ),
    )


def _write_answer_artifact(artifacts_dir: Path, *, job_id: str, answer: str) -> None:
    job_dir = artifacts_dir / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "answer.md").write_text(answer, encoding="utf-8")


def _seed_short_resubmit_pairs(conn: sqlite3.Connection, *, artifacts_dir: Path) -> list[str]:
    prompt_a = "请帮我给五岁孩子设计一个乐高主题的周末活动计划。"
    prompt_b = "请帮我比较一下 Deep Research 和普通搜索的差别。"
    now = time.time()

    j1 = _create_web_job(
        conn,
        artifacts_dir=artifacts_dir,
        idem="behavior-short-1",
        question=prompt_a,
        client_name="human-alpha",
    )
    _mark_job(
        conn,
        job_id=j1,
        status="completed",
        created_at=now - 500,
        updated_at=now - 450,
        conversation_url="https://gemini.google.com/app/human-alpha-1",
        conversation_id="human-alpha-1",
        answer_chars=18,
    )
    insert_event(conn, job_id=j1, type="completion_guard_completed_under_min_chars", payload={"answer_chars": 18})
    _write_answer_artifact(artifacts_dir, job_id=j1, answer="好的，我来处理。")

    j2 = _create_web_job(
        conn,
        artifacts_dir=artifacts_dir,
        idem="behavior-short-2",
        question=prompt_a,
        client_name="human-alpha",
    )
    _mark_job(
        conn,
        job_id=j2,
        status="queued",
        created_at=now - 430,
        updated_at=now - 430,
        conversation_url="https://gemini.google.com/app/human-alpha-2",
        conversation_id="human-alpha-2",
    )

    j3 = _create_web_job(
        conn,
        artifacts_dir=artifacts_dir,
        idem="behavior-short-3",
        question=prompt_b,
        client_name="human-beta",
    )
    _mark_job(
        conn,
        job_id=j3,
        status="completed",
        created_at=now - 320,
        updated_at=now - 300,
        conversation_url="https://gemini.google.com/app/human-beta-1",
        conversation_id="human-beta-1",
        answer_chars=24,
    )
    insert_event(conn, job_id=j3, type="completion_guard_completed_under_min_chars", payload={"answer_chars": 24})
    _write_answer_artifact(artifacts_dir, job_id=j3, answer="我马上开始。")

    j4 = _create_web_job(
        conn,
        artifacts_dir=artifacts_dir,
        idem="behavior-short-4",
        question=prompt_b,
        client_name="human-beta",
    )
    _mark_job(
        conn,
        job_id=j4,
        status="in_progress",
        created_at=now - 260,
        updated_at=now - 250,
        conversation_url="https://gemini.google.com/app/human-beta-2",
        conversation_id="human-beta-2",
    )
    return [j1, j2, j3, j4]


def _seed_dr_progression_failure(conn: sqlite3.Connection, *, artifacts_dir: Path) -> tuple[str, str]:
    now = time.time()
    parent = _create_web_job(
        conn,
        artifacts_dir=artifacts_dir,
        idem="behavior-dr-parent",
        question="请深度研究一下儿童沉迷短视频的干预策略。",
        client_name="human-gamma",
        params={"deep_research": True},
    )
    _mark_job(
        conn,
        job_id=parent,
        status="needs_followup",
        created_at=now - 200,
        updated_at=now - 180,
        conversation_url="https://gemini.google.com/app/dr-parent",
        conversation_id="dr-parent",
    )
    child = _create_web_job(
        conn,
        artifacts_dir=artifacts_dir,
        idem="behavior-dr-child",
        question="继续，直接开始研究。",
        client_name="human-gamma",
        params={"allow_queue": True, "deep_research": False},
        parent_job_id=parent,
    )
    _mark_job(
        conn,
        job_id=child,
        status="queued",
        created_at=now - 170,
        updated_at=now - 170,
        conversation_url="https://gemini.google.com/app/dr-parent",
        conversation_id="dr-parent",
    )
    conn.execute(
        "UPDATE jobs SET params_json = ? WHERE job_id = ?",
        (json.dumps({"allow_queue": True, "deep_research": False}, ensure_ascii=False), child),
    )
    return parent, child


def _behavior_state(tmp_path: Path, *, artifacts_dir: Path, monitor_dir: Path, auto_mitigate_after_hours: float = 0.0) -> dict:
    return {
        "enable_behavior_issue_detection": True,
        "behavior_issue_lookback_seconds": 7200,
        "behavior_issue_jobs_limit": 200,
        "behavior_short_answer_chars_max": 120,
        "behavior_short_resubmit_window_seconds": 900,
        "behavior_short_resubmit_min_occurrences": 2,
        "behavior_needs_followup_min_chain": 3,
        "enable_behavior_auto_sre_fix": True,
        "behavior_issue_max_promotions_per_tick": 8,
        "behavior_issue_auto_mitigate_after_hours": auto_mitigate_after_hours,
        "behavior_issue_auto_mitigate_max_per_tick": 10,
        "artifacts_dir": artifacts_dir,
        "monitor_dir": monitor_dir,
        "dedupe_seconds": 1800,
        "log_path": tmp_path / "maint.jsonl",
    }


def test_detect_behavior_issue_candidates_from_human_language_questions(tmp_path: Path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    init_db(db_path)

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        _seed_short_resubmit_pairs(conn, artifacts_dir=artifacts_dir)
        _seed_dr_progression_failure(conn, artifacts_dir=artifacts_dir)
        conn.commit()

    with connect(db_path) as conn:
        candidates = detect_behavior_issue_candidates(
            conn,
            now=time.time(),
            lookback_seconds=3600,
            jobs_limit=200,
            short_answer_chars_max=120,
            short_resubmit_window_seconds=900,
            short_resubmit_min_occurrences=2,
            needs_followup_min_chain=3,
        )

    detector_ids = {candidate.detector_id for candidate in candidates}
    assert "completed_short_resubmit" in detector_ids
    assert "dr_followup_progression_failure" in detector_ids
    short_resubmit = next(candidate for candidate in candidates if candidate.detector_id == "completed_short_resubmit")
    assert short_resubmit.metadata["occurrences"] == 2
    assert any("乐高主题" in prompt for prompt in short_resubmit.sample_prompts)


def test_behavior_issue_subsystem_promotes_issue_and_auto_mitigates(tmp_path: Path) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monitor_dir = artifacts_dir / "monitor" / "maint_daemon"
    init_db(db_path)

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        _seed_short_resubmit_pairs(conn, artifacts_dir=artifacts_dir)
        conn.commit()

    subsystem = BehaviorIssueSubsystem(interval_seconds=1)
    now = time.time()
    with connect(db_path) as conn:
        ctx = TickContext(
            now=now,
            args=SimpleNamespace(),
            conn=conn,
            state=_behavior_state(tmp_path, artifacts_dir=artifacts_dir, monitor_dir=monitor_dir, auto_mitigate_after_hours=0.0),
        )
        observations = subsystem.tick(ctx)
        promoted = [obs for obs in observations if obs.data.get("type") == "behavior_issue_promoted"]
        submitted = [obs for obs in observations if obs.data.get("type") == "behavior_sre_fix_submitted"]
        assert promoted
        assert submitted

        issues = conn.execute(
            "SELECT issue_id, status, source, title, latest_artifacts_path FROM client_issues WHERE source = 'behavior_auto'"
        ).fetchall()
        assert len(issues) == 1
        issue_id = str(issues[0]["issue_id"])
        assert str(issues[0]["status"]) == "in_progress"
        assert "short completions" in str(issues[0]["title"]).lower()
        summary_path = artifacts_dir / str(issues[0]["latest_artifacts_path"])
        assert summary_path.exists()
        assert "乐高主题" in summary_path.read_text(encoding="utf-8")

        repair_jobs = conn.execute("SELECT job_id, kind, status FROM jobs WHERE kind = 'sre.fix_request'").fetchall()
        assert len(repair_jobs) == 1
        assert str(repair_jobs[0]["status"]) == "queued"

        observations_second = subsystem.tick(ctx)
        assert all(obs.data.get("type") != "behavior_sre_fix_submitted" for obs in observations_second)
        issue_row = conn.execute("SELECT count FROM client_issues WHERE issue_id = ?", (issue_id,)).fetchone()
        assert issue_row is not None
        assert int(issue_row["count"]) == 1

        quiet_now = now + 7200.0
        conn.execute(
            "UPDATE client_issues SET updated_at = ?, last_seen_at = ? WHERE issue_id = ?",
            (quiet_now - 7200.0, quiet_now - 7200.0, issue_id),
        )
        conn.commit()
        ctx_quiet = TickContext(
            now=quiet_now,
            args=SimpleNamespace(),
            conn=conn,
            state=_behavior_state(tmp_path, artifacts_dir=artifacts_dir, monitor_dir=monitor_dir, auto_mitigate_after_hours=1.0),
        )
        mitigated = subsystem.tick(ctx_quiet)
        assert any(obs.data.get("type") == "behavior_issue_auto_mitigated" for obs in mitigated)
        issue = client_issues.get_issue(conn, issue_id=issue_id)
        assert issue is not None
        assert issue.status == "mitigated"


def test_maint_daemon_main_promotes_behavior_issue_from_human_questions(tmp_path: Path) -> None:
    md = _load_maint_daemon_module()
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    state_file = tmp_path / "state.json"
    init_db(db_path)

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        _seed_short_resubmit_pairs(conn, artifacts_dir=artifacts_dir)
        conn.commit()

    rc = md.main(
        [
            "--db",
            str(db_path),
            "--artifacts-dir",
            str(artifacts_dir),
            "--state-file",
            str(state_file),
            "--disable-ui-canary",
            "--run-seconds",
            "1",
            "--poll-seconds",
            "0.2",
            "--summary-every-seconds",
            "3600",
            "--scan-every-seconds",
            "3600",
            "--blocked-state-every-seconds",
            "3600",
            "--incident-auto-resolve-every-seconds",
            "3600",
            "--behavior-issue-every-seconds",
            "1",
            "--behavior-issue-auto-mitigate-after-hours",
            "0",
        ]
    )
    assert rc == 0

    with connect(db_path) as conn:
        issue_row = conn.execute(
            "SELECT issue_id, status, source FROM client_issues WHERE source = 'behavior_auto' ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        assert issue_row is not None
        assert str(issue_row["status"]) == "in_progress"

        repair_row = conn.execute(
            "SELECT kind, status FROM jobs WHERE kind = 'sre.fix_request' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert repair_row is not None
        assert str(repair_row["status"]) == "queued"

        incident_row = conn.execute(
            "SELECT category, severity FROM incidents WHERE category = 'behavior' ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        assert incident_row is not None
        assert str(incident_row["severity"]) == "P1"


def test_maint_daemon_main_job_scan_creates_incident_without_sig_hash_shadowing(tmp_path: Path) -> None:
    md = _load_maint_daemon_module()
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    state_file = tmp_path / "state.json"
    init_db(db_path)

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job_id = _create_web_job(
            conn,
            artifacts_dir=artifacts_dir,
            idem="job-scan-needs-followup-1",
            question="请继续上一次的研究，不要再重复计划说明。",
            client_name="human-delta",
            kind="gemini_web.ask",
        )
        _mark_job(
            conn,
            job_id=job_id,
            status="needs_followup",
            created_at=time.time() - 120,
            updated_at=time.time() - 60,
            conversation_url="https://gemini.google.com/app/job-scan-needs-followup",
            conversation_id="job-scan-needs-followup",
        )
        conn.execute(
            "UPDATE jobs SET last_error_type = ?, last_error = ? WHERE job_id = ?",
            ("RuntimeError", "Gemini still waiting for follow-up action", job_id),
        )
        conn.commit()

    rc = md.main(
        [
            "--db",
            str(db_path),
            "--artifacts-dir",
            str(artifacts_dir),
            "--state-file",
            str(state_file),
            "--disable-ui-canary",
            "--run-seconds",
            "6",
            "--poll-seconds",
            "0.2",
            "--summary-every-seconds",
            "3600",
            "--scan-every-seconds",
            "1",
            "--blocked-state-every-seconds",
            "3600",
            "--incident-auto-resolve-every-seconds",
            "3600",
            "--behavior-issue-every-seconds",
            "3600",
        ]
    )
    assert rc == 0

    log_path = artifacts_dir / "monitor" / "maint_daemon" / "maint.jsonl"
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        assert '"subsystem": "job_scan"' not in log_text
        assert "UnboundLocalError" not in log_text

    with connect(db_path) as conn:
        incident_row = conn.execute(
            "SELECT signature, severity, status FROM incidents WHERE signature LIKE 'needs_followup:%' ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        assert incident_row is not None
        assert str(incident_row["signature"]) == "needs_followup:gemini:gemini_web.ask:RuntimeError"
        assert str(incident_row["status"]) == "open"
