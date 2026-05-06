from __future__ import annotations

import json
import importlib.util
import sqlite3
import sys
from pathlib import Path

from chatgptrest.core.db import init_db
from chatgptrest.core.job_store import create_job


def _load_maint_daemon_module():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "ops" / "maint_daemon.py"
    spec = importlib.util.spec_from_file_location("chatgptrest_ops_maint_daemon", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _jsonl_event_count(path: Path, event_type: str) -> int:
    if not path.exists():
        return 0
    total = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s:
            continue
        obj = json.loads(s)
        if str(obj.get("type") or "") == str(event_type):
            total += 1
    return total


def test_maint_daemon_ensure_repair_check_job_is_idempotent(tmp_path: Path):
    md = _load_maint_daemon_module()

    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    init_db(db_path)

    incident = md.IncidentState(
        incident_id="20260105_000000Z_deadbeef0000",
        signature="error:DriveUploadNotReady:i/o timeout",
        sig_hash="deadbeef0000",
        created_ts=0.0,
        last_seen_ts=0.0,
        count=1,
        job_ids=["target-1"],
        repair_job_id=None,
    )

    conn = md._connect(db_path)  # noqa: SLF001
    try:
        conn.execute("BEGIN IMMEDIATE")
        job_id1 = md._ensure_repair_check_job(  # noqa: SLF001
            conn=conn,
            artifacts_dir=artifacts_dir,
            incident=incident,
            target_job_id="target-1",
            signature=incident.signature,
            conversation_url=None,
            timeout_seconds=30,
            mode="quick",
            probe_driver=True,
            recent_failures=3,
        )
        conn.commit()

        conn.execute("BEGIN IMMEDIATE")
        job_id2 = md._ensure_repair_check_job(  # noqa: SLF001
            conn=conn,
            artifacts_dir=artifacts_dir,
            incident=incident,
            target_job_id="target-1",
            signature=incident.signature,
            conversation_url=None,
            timeout_seconds=30,
            mode="quick",
            probe_driver=True,
            recent_failures=3,
        )
        conn.commit()
    finally:
        conn.close()

    assert job_id1 == job_id2

    conn2 = sqlite3.connect(str(db_path))
    conn2.row_factory = sqlite3.Row
    try:
        row = conn2.execute("SELECT kind, status FROM jobs WHERE job_id = ?", (job_id1,)).fetchone()
        assert row is not None
        assert str(row["kind"]) == "repair.check"
        assert str(row["status"]) == "queued"
        request_payload = json.loads(
            (artifacts_dir / "jobs" / job_id1 / "request.json").read_text(encoding="utf-8")
        )
        assert request_payload["input"]["job_id"] == "target-1"
        assert request_payload["input"]["symptom"] == incident.signature
        assert request_payload["params"]["mode"] == "quick"
        assert request_payload["params"]["probe_driver"] is True
        assert request_payload["params"]["recent_failures"] == 3
    finally:
        conn2.close()


def test_maint_daemon_attach_repair_artifacts(tmp_path: Path):
    md = _load_maint_daemon_module()

    artifacts_dir = tmp_path / "artifacts"
    inc_dir = tmp_path / "incident"
    log_path = tmp_path / "maint.jsonl"
    repair_job_id = "r1"

    src_dir = artifacts_dir / "jobs" / repair_job_id
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "repair_report.json").write_text(json.dumps({"repair_job_id": repair_job_id}), encoding="utf-8")
    (src_dir / "answer.md").write_text("# repair.check report\n", encoding="utf-8")
    (src_dir / "result.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    copied = md._attach_repair_artifacts(  # noqa: SLF001
        artifacts_dir=artifacts_dir,
        inc_dir=inc_dir,
        repair_job_id=repair_job_id,
        log_path=log_path,
        incident_id="inc-1",
    )
    assert copied is True

    assert (inc_dir / "snapshots" / "repair_check" / "repair_report.json").exists()
    assert _jsonl_event_count(log_path, "auto_repair_attached") == 1


def test_maint_daemon_attach_repair_artifacts_returns_false_when_sources_missing(tmp_path: Path):
    md = _load_maint_daemon_module()

    artifacts_dir = tmp_path / "artifacts"
    inc_dir = tmp_path / "incident"
    log_path = tmp_path / "maint.jsonl"

    copied = md._attach_repair_artifacts(  # noqa: SLF001
        artifacts_dir=artifacts_dir,
        inc_dir=inc_dir,
        repair_job_id="missing-job",
        log_path=log_path,
        incident_id="inc-missing",
    )
    assert copied is False
    assert _jsonl_event_count(log_path, "auto_repair_attached") == 0


def test_maint_daemon_attach_repair_artifacts_skips_unchanged_files(tmp_path: Path):
    md = _load_maint_daemon_module()

    artifacts_dir = tmp_path / "artifacts"
    inc_dir = tmp_path / "incident"
    log_path = tmp_path / "maint.jsonl"
    repair_job_id = "r1-noop"

    src_dir = artifacts_dir / "jobs" / repair_job_id
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "repair_report.json").write_text(json.dumps({"repair_job_id": repair_job_id}), encoding="utf-8")
    (src_dir / "answer.md").write_text("# repair.check report\n", encoding="utf-8")
    (src_dir / "result.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    copied_first = md._attach_repair_artifacts(  # noqa: SLF001
        artifacts_dir=artifacts_dir,
        inc_dir=inc_dir,
        repair_job_id=repair_job_id,
        log_path=log_path,
        incident_id="inc-1-noop",
    )
    copied_second = md._attach_repair_artifacts(  # noqa: SLF001
        artifacts_dir=artifacts_dir,
        inc_dir=inc_dir,
        repair_job_id=repair_job_id,
        log_path=log_path,
        incident_id="inc-1-noop",
    )

    assert copied_first is True
    assert copied_second is False
    assert _jsonl_event_count(log_path, "auto_repair_attached") == 1


def test_maint_daemon_attach_repair_artifacts_overwrites_same_size_changed_content(tmp_path: Path):
    md = _load_maint_daemon_module()

    artifacts_dir = tmp_path / "artifacts"
    inc_dir = tmp_path / "incident"
    log_path = tmp_path / "maint.jsonl"
    repair_job_id = "r1-same-size"

    src_dir = artifacts_dir / "jobs" / repair_job_id
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "repair_report.json").write_text("{\"k\":1}\n", encoding="utf-8")
    (src_dir / "answer.md").write_text("AAAA\n", encoding="utf-8")
    (src_dir / "result.json").write_text("{\"v\":1}\n", encoding="utf-8")

    copied_first = md._attach_repair_artifacts(  # noqa: SLF001
        artifacts_dir=artifacts_dir,
        inc_dir=inc_dir,
        repair_job_id=repair_job_id,
        log_path=log_path,
        incident_id="inc-1-same-size",
    )
    assert copied_first is True

    (src_dir / "answer.md").write_text("BBBB\n", encoding="utf-8")  # same size, different content
    copied_second = md._attach_repair_artifacts(  # noqa: SLF001
        artifacts_dir=artifacts_dir,
        inc_dir=inc_dir,
        repair_job_id=repair_job_id,
        log_path=log_path,
        incident_id="inc-1-same-size",
    )
    assert copied_second is True
    assert _jsonl_event_count(log_path, "auto_repair_attached") == 2
    assert (inc_dir / "snapshots" / "repair_check" / "answer.md").read_text(encoding="utf-8") == "BBBB\n"


def test_maint_daemon_ensure_repair_autofix_job_is_idempotent(tmp_path: Path):
    md = _load_maint_daemon_module()

    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    init_db(db_path)

    incident = md.IncidentState(
        incident_id="20260105_000000Z_autofix000001",
        signature="error:CodexSreFailed:driver unstable",
        sig_hash="autofix000001",
        created_ts=0.0,
        last_seen_ts=0.0,
        count=1,
        job_ids=["target-1"],
        repair_job_id=None,
    )

    conn = md._connect(db_path)  # noqa: SLF001
    try:
        conn.execute("BEGIN IMMEDIATE")
        job_id1 = md._ensure_repair_autofix_job(  # noqa: SLF001
            conn=conn,
            artifacts_dir=artifacts_dir,
            incident=incident,
            target_job_id="target-1",
            signature=incident.signature,
            conversation_url="https://chatgpt.com/c/00000000-0000-0000-0000-000000000001",
            timeout_seconds=180,
            allow_actions="restart_driver,capture_ui",
            max_risk="medium",
        )
        conn.commit()

        conn.execute("BEGIN IMMEDIATE")
        job_id2 = md._ensure_repair_autofix_job(  # noqa: SLF001
            conn=conn,
            artifacts_dir=artifacts_dir,
            incident=incident,
            target_job_id="target-1",
            signature=incident.signature,
            conversation_url="https://chatgpt.com/c/00000000-0000-0000-0000-000000000001",
            timeout_seconds=180,
            allow_actions="restart_driver,capture_ui",
            max_risk="medium",
        )
        conn.commit()
    finally:
        conn.close()

    assert job_id1 == job_id2

    conn2 = sqlite3.connect(str(db_path))
    conn2.row_factory = sqlite3.Row
    try:
        row = conn2.execute("SELECT kind, status FROM jobs WHERE job_id = ?", (job_id1,)).fetchone()
        assert row is not None
        assert str(row["kind"]) == "repair.autofix"
        assert str(row["status"]) == "queued"
        request_payload = json.loads(
            (artifacts_dir / "jobs" / job_id1 / "request.json").read_text(encoding="utf-8")
        )
        assert request_payload["input"]["job_id"] == "target-1"
        assert request_payload["input"]["conversation_url"].startswith("https://chatgpt.com/c/")
        assert request_payload["params"]["allow_actions"] == "restart_driver,capture_ui"
        assert request_payload["params"]["model"] == "gpt-5.3-codex-spark"
        assert request_payload["params"]["max_risk"] == "medium"
        assert request_payload["params"]["apply_actions"] is True
    finally:
        conn2.close()


def test_maint_daemon_skips_repair_jobs_for_synthetic_source(tmp_path: Path):
    md = _load_maint_daemon_module()

    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    init_db(db_path)

    conn = md._connect(db_path)  # noqa: SLF001
    try:
        source = create_job(
            conn,
            artifacts_dir=artifacts_dir,
            idempotency_key="maint-synthetic-source-1",
            kind="chatgpt_web.ask",
            input={"question": "test needs_followup state\n\n--- 附加上下文 ---\n- depth: standard"},
            params={"preset": "auto", "allow_live_chatgpt_smoke": True},
            client={"name": "advisor_ask"},
            requested_by={"transport": "test"},
            max_attempts=1,
        )
        conn.commit()

        incident = md.IncidentState(
            incident_id="20260105_000000Z_skiprepair0001",
            signature="error:WaitNoProgressTimeout:synthetic",
            sig_hash="skiprepair0001",
            created_ts=0.0,
            last_seen_ts=0.0,
            count=1,
            job_ids=[source.job_id],
            repair_job_id=None,
        )

        conn.execute("BEGIN IMMEDIATE")
        repair_check_job_id = md._ensure_repair_check_job(  # noqa: SLF001
            conn=conn,
            artifacts_dir=artifacts_dir,
            incident=incident,
            target_job_id=source.job_id,
            signature=incident.signature,
            conversation_url="https://chatgpt.com/c/00000000-0000-0000-0000-000000000321",
            timeout_seconds=30,
            mode="quick",
            probe_driver=True,
            recent_failures=3,
        )
        conn.commit()

        conn.execute("BEGIN IMMEDIATE")
        repair_autofix_job_id = md._ensure_repair_autofix_job(  # noqa: SLF001
            conn=conn,
            artifacts_dir=artifacts_dir,
            incident=incident,
            target_job_id=source.job_id,
            signature=incident.signature,
            conversation_url="https://chatgpt.com/c/00000000-0000-0000-0000-000000000321",
            timeout_seconds=180,
            allow_actions="restart_driver,capture_ui",
            max_risk="medium",
        )
        conn.commit()
    finally:
        conn.close()

    assert repair_check_job_id == ""
    assert repair_autofix_job_id == ""

    conn2 = sqlite3.connect(str(db_path))
    conn2.row_factory = sqlite3.Row
    try:
        rows = conn2.execute(
            "SELECT kind FROM jobs WHERE kind IN ('repair.check', 'repair.autofix')"
        ).fetchall()
        assert not rows
    finally:
        conn2.close()


def test_maint_daemon_attach_repair_autofix_artifacts(tmp_path: Path):
    md = _load_maint_daemon_module()

    artifacts_dir = tmp_path / "artifacts"
    inc_dir = tmp_path / "incident"
    log_path = tmp_path / "maint.jsonl"
    repair_job_id = "r2"

    src_dir = artifacts_dir / "jobs" / repair_job_id
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "repair_autofix_report.json").write_text(json.dumps({"repair_job_id": repair_job_id}), encoding="utf-8")
    (src_dir / "answer.md").write_text("# repair.autofix report\n", encoding="utf-8")
    (src_dir / "result.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    copied = md._attach_repair_autofix_artifacts(  # noqa: SLF001
        artifacts_dir=artifacts_dir,
        inc_dir=inc_dir,
        repair_job_id=repair_job_id,
        log_path=log_path,
        incident_id="inc-2",
    )
    assert copied is True
    assert (inc_dir / "snapshots" / "repair_autofix" / "repair_autofix_report.json").exists()
    assert _jsonl_event_count(log_path, "codex_maint_fallback_attached") == 1


def test_maint_daemon_attach_repair_autofix_artifacts_returns_false_when_sources_missing(tmp_path: Path):
    md = _load_maint_daemon_module()

    artifacts_dir = tmp_path / "artifacts"
    inc_dir = tmp_path / "incident"
    log_path = tmp_path / "maint.jsonl"

    copied = md._attach_repair_autofix_artifacts(  # noqa: SLF001
        artifacts_dir=artifacts_dir,
        inc_dir=inc_dir,
        repair_job_id="missing-job",
        log_path=log_path,
        incident_id="inc-missing-autofix",
    )
    assert copied is False
    assert _jsonl_event_count(log_path, "codex_maint_fallback_attached") == 0


def test_maint_daemon_attach_repair_autofix_artifacts_skips_unchanged_files(tmp_path: Path):
    md = _load_maint_daemon_module()

    artifacts_dir = tmp_path / "artifacts"
    inc_dir = tmp_path / "incident"
    log_path = tmp_path / "maint.jsonl"
    repair_job_id = "r2-noop"

    src_dir = artifacts_dir / "jobs" / repair_job_id
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "repair_autofix_report.json").write_text(json.dumps({"repair_job_id": repair_job_id}), encoding="utf-8")
    (src_dir / "answer.md").write_text("# repair.autofix report\n", encoding="utf-8")
    (src_dir / "result.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    copied_first = md._attach_repair_autofix_artifacts(  # noqa: SLF001
        artifacts_dir=artifacts_dir,
        inc_dir=inc_dir,
        repair_job_id=repair_job_id,
        log_path=log_path,
        incident_id="inc-2-noop",
    )
    copied_second = md._attach_repair_autofix_artifacts(  # noqa: SLF001
        artifacts_dir=artifacts_dir,
        inc_dir=inc_dir,
        repair_job_id=repair_job_id,
        log_path=log_path,
        incident_id="inc-2-noop",
    )

    assert copied_first is True
    assert copied_second is False
    assert _jsonl_event_count(log_path, "codex_maint_fallback_attached") == 1


def test_maint_daemon_attach_repair_autofix_artifacts_overwrites_same_size_changed_content(tmp_path: Path):
    md = _load_maint_daemon_module()

    artifacts_dir = tmp_path / "artifacts"
    inc_dir = tmp_path / "incident"
    log_path = tmp_path / "maint.jsonl"
    repair_job_id = "r2-same-size"

    src_dir = artifacts_dir / "jobs" / repair_job_id
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "repair_autofix_report.json").write_text("{\"k\":1}\n", encoding="utf-8")
    (src_dir / "answer.md").write_text("AAAA\n", encoding="utf-8")
    (src_dir / "result.json").write_text("{\"v\":1}\n", encoding="utf-8")

    copied_first = md._attach_repair_autofix_artifacts(  # noqa: SLF001
        artifacts_dir=artifacts_dir,
        inc_dir=inc_dir,
        repair_job_id=repair_job_id,
        log_path=log_path,
        incident_id="inc-2-same-size",
    )
    assert copied_first is True

    (src_dir / "answer.md").write_text("BBBB\n", encoding="utf-8")  # same size, different content
    copied_second = md._attach_repair_autofix_artifacts(  # noqa: SLF001
        artifacts_dir=artifacts_dir,
        inc_dir=inc_dir,
        repair_job_id=repair_job_id,
        log_path=log_path,
        incident_id="inc-2-same-size",
    )
    assert copied_second is True
    assert _jsonl_event_count(log_path, "codex_maint_fallback_attached") == 2
    assert (inc_dir / "snapshots" / "repair_autofix" / "answer.md").read_text(encoding="utf-8") == "BBBB\n"
