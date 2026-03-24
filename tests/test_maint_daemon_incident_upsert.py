from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from chatgptrest.core.db import init_db


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


def _incident(md, *, incident_id: str, sig_hash: str):
    return md.IncidentState(
        incident_id=incident_id,
        signature=f"sig:{sig_hash}",
        sig_hash=sig_hash,
        created_ts=1.0,
        last_seen_ts=1.0,
        count=1,
        job_ids=["job-1"],
    )


def test_upsert_incident_db_keeps_existing_severity_when_none_is_passed(tmp_path: Path):
    md = _load_maint_daemon_module()
    db_path = tmp_path / "jobdb.sqlite3"
    init_db(db_path)
    conn = md._connect(db_path)  # noqa: SLF001
    try:
        inc = _incident(md, incident_id="inc-1", sig_hash="hash-1")

        conn.execute("BEGIN IMMEDIATE")
        md._upsert_incident_db(  # noqa: SLF001
            conn,
            incident=inc,
            category="job",
            severity="P1",
            status="open",
            evidence_dir=None,
        )
        conn.commit()

        conn.execute("BEGIN IMMEDIATE")
        md._upsert_incident_db(  # noqa: SLF001
            conn,
            incident=inc,
            category=None,
            severity=None,
            status="open",
            evidence_dir=None,
        )
        conn.commit()

        row = conn.execute(
            "SELECT category, severity, status FROM incidents WHERE incident_id = ?",
            ("inc-1",),
        ).fetchone()
        assert row is not None
        assert str(row["category"]) == "job"
        assert str(row["severity"]) == "P1"
        assert str(row["status"]) == "open"
    finally:
        conn.close()


def test_upsert_incident_db_inserts_defaults_when_severity_or_status_missing(tmp_path: Path):
    md = _load_maint_daemon_module()
    db_path = tmp_path / "jobdb.sqlite3"
    init_db(db_path)
    conn = md._connect(db_path)  # noqa: SLF001
    try:
        inc = _incident(md, incident_id="inc-2", sig_hash="hash-2")

        conn.execute("BEGIN IMMEDIATE")
        md._upsert_incident_db(  # noqa: SLF001
            conn,
            incident=inc,
            category=None,
            severity=None,
            status=None,
            evidence_dir=None,
        )
        conn.commit()

        row = conn.execute(
            "SELECT severity, status FROM incidents WHERE incident_id = ?",
            ("inc-2",),
        ).fetchone()
        assert row is not None
        assert str(row["severity"]) == "P2"
        assert str(row["status"]) == "open"
    finally:
        conn.close()


def test_incident_rollover_requires_fresh_signal_and_dedupe_window() -> None:
    md = _load_maint_daemon_module()

    assert md._incident_signal_is_fresh(signal_ts=100.0, last_seen_ts=100.0) is False  # noqa: SLF001
    assert md._incident_signal_is_fresh(signal_ts=100.0000001, last_seen_ts=100.0) is False  # noqa: SLF001
    assert md._incident_signal_is_fresh(signal_ts=100.01, last_seen_ts=100.0) is True  # noqa: SLF001

    # stale signal never rolls over
    assert md._incident_should_rollover_for_signal(signal_ts=100.0, last_seen_ts=100.0, dedupe_seconds=600) is False  # noqa: SLF001
    # fresh but still within dedupe window should not roll over
    assert md._incident_should_rollover_for_signal(signal_ts=150.0, last_seen_ts=100.0, dedupe_seconds=600) is False  # noqa: SLF001
    # fresh and outside dedupe window rolls over
    assert md._incident_should_rollover_for_signal(signal_ts=701.0, last_seen_ts=100.0, dedupe_seconds=600) is True  # noqa: SLF001


def test_incident_rollover_applies_minimum_dedupe_window_of_60_seconds() -> None:
    md = _load_maint_daemon_module()

    assert md._incident_should_rollover_for_signal(signal_ts=159.0, last_seen_ts=100.0, dedupe_seconds=1) is False  # noqa: SLF001
    assert md._incident_should_rollover_for_signal(signal_ts=160.0, last_seen_ts=100.0, dedupe_seconds=1) is True  # noqa: SLF001


def test_incident_signal_is_fresh_supports_custom_epsilon() -> None:
    md = _load_maint_daemon_module()

    assert md._incident_signal_is_fresh(signal_ts=100.005, last_seen_ts=100.0, epsilon=0.01) is False  # noqa: SLF001
    assert md._incident_signal_is_fresh(signal_ts=100.02, last_seen_ts=100.0, epsilon=0.01) is True  # noqa: SLF001


def test_incident_freshness_gate_skips_stale_touch_when_no_followup_work() -> None:
    md = _load_maint_daemon_module()
    inc = _incident(md, incident_id="inc-gate-1", sig_hash="hash-gate-1")
    inc.last_seen_ts = 100.0
    inc.job_ids = ["job-1"]
    inc.repair_job_id = "repair-1"
    inc.codex_last_run_ts = 120.0

    out = md._incident_freshness_gate(  # noqa: SLF001
        incident=inc,
        signal_ts=100.0,
        is_new_incident=False,
        job_id="job-1",
    )
    assert out["has_fresh_signal"] is False
    assert out["needs_followup_work"] is False
    assert out["should_skip_touch"] is True


def test_incident_freshness_gate_keeps_processing_when_followup_work_pending() -> None:
    md = _load_maint_daemon_module()
    inc = _incident(md, incident_id="inc-gate-2", sig_hash="hash-gate-2")
    inc.last_seen_ts = 100.0
    inc.job_ids = ["job-1"]
    inc.repair_job_id = None
    inc.codex_last_run_ts = 120.0

    out = md._incident_freshness_gate(  # noqa: SLF001
        incident=inc,
        signal_ts=100.0,
        is_new_incident=False,
        job_id="job-1",
    )
    assert out["has_fresh_signal"] is False
    assert out["needs_followup_work"] is True
    assert out["should_skip_touch"] is False


def test_incident_freshness_gate_treats_new_job_or_new_signal_as_fresh() -> None:
    md = _load_maint_daemon_module()
    inc = _incident(md, incident_id="inc-gate-3", sig_hash="hash-gate-3")
    inc.last_seen_ts = 100.0
    inc.job_ids = ["job-1"]
    inc.repair_job_id = "repair-1"
    inc.codex_last_run_ts = 120.0

    out_new_job = md._incident_freshness_gate(  # noqa: SLF001
        incident=inc,
        signal_ts=100.0,
        is_new_incident=False,
        job_id="job-2",
    )
    assert out_new_job["has_fresh_signal"] is True
    assert out_new_job["should_skip_touch"] is False

    out_new_signal = md._incident_freshness_gate(  # noqa: SLF001
        incident=inc,
        signal_ts=101.0,
        is_new_incident=False,
        job_id="job-1",
    )
    assert out_new_signal["has_fresh_signal"] is True
    assert out_new_signal["should_skip_touch"] is False
