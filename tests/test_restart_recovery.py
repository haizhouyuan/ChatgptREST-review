"""L6-1: Process restart recovery — advisor_runs survive restart.

Tests that the durable spine (advisor_runs SQLite table) survives
connection close and re-open, verifying:
- Runs created before "restart" are still retrievable
- Run status updates persist across reconnects
- In-progress runs can be resumed after restart
- Context JSON survives
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from chatgptrest.core.advisor_runs import (
    create_run,
    get_run,
    update_run,
)
from chatgptrest.core.db import connect, init_db


# ---------------------------------------------------------------------------
# L6-1a: Run survives connection close and re-open
# ---------------------------------------------------------------------------

def test_run_survives_reconnect(tmp_path: Path):
    """A run created in session-1 should be retrievable in session-2."""
    db_path = tmp_path / "advisor.sqlite3"
    init_db(db_path)

    # Session 1: create run
    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="run-survive-001",
            request_id="req-001",
            mode="balanced",
            status="NEW",
            route="quick_ask",
            raw_question="restart test",
            normalized_question="restart test",
            context={"test": True},
            quality_threshold=None,
            crosscheck=False,
            max_retries=1,
        )
        conn.commit()

    # Session 2: retrieve
    with connect(db_path) as conn:
        recovered = get_run(conn, run_id="run-survive-001")

    assert recovered is not None
    assert recovered["run_id"] == "run-survive-001"
    assert recovered["raw_question"] == "restart test"
    assert recovered["status"] == "NEW"


# ---------------------------------------------------------------------------
# L6-1b: Status update persists across reconnect
# ---------------------------------------------------------------------------

def test_status_update_persists(tmp_path: Path):
    """Update status in session-1, verify in session-2."""
    db_path = tmp_path / "advisor.sqlite3"
    init_db(db_path)

    # Session 1: create + update
    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="run-status-001",
            request_id="req-002",
            mode="balanced",
            status="NEW",
            route="deep_research",
            raw_question="status test",
            normalized_question="status test",
            context=None,
            quality_threshold=80,
            crosscheck=True,
            max_retries=2,
        )
        conn.commit()
        update_run(conn, run_id="run-status-001", status="COMPLETED")
        conn.commit()

    # Session 2: verify
    with connect(db_path) as conn:
        run = get_run(conn, run_id="run-status-001")

    assert run is not None
    assert run["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# L6-1c: Multiple runs survive restart
# ---------------------------------------------------------------------------

def test_multiple_runs_survive(tmp_path: Path):
    """Multiple runs created in one session should all be recoverable."""
    db_path = tmp_path / "advisor.sqlite3"
    init_db(db_path)

    # Session 1: create 5 runs
    with connect(db_path) as conn:
        for i in range(5):
            create_run(
                conn,
                run_id=f"run-multi-{i:03d}",
                request_id=f"req-multi-{i:03d}",
                mode="balanced",
                status="pending" if i < 3 else "completed",
                route="quick_ask",
                raw_question=f"question {i}",
                normalized_question=f"question {i}",
                context=None,
                quality_threshold=None,
                crosscheck=False,
                max_retries=1,
            )
        conn.commit()

    # Session 2: verify all 5
    with connect(db_path) as conn:
        for i in range(5):
            run = get_run(conn, run_id=f"run-multi-{i:03d}")
            assert run is not None, f"Run run-multi-{i:03d} not found after restart"


# ---------------------------------------------------------------------------
# L6-1d: In-progress run can be resumed
# ---------------------------------------------------------------------------

def test_in_progress_run_resumable(tmp_path: Path):
    """A run left in 'in_progress' can be updated after restart."""
    db_path = tmp_path / "advisor.sqlite3"
    init_db(db_path)

    # Session 1: create in_progress run
    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="run-resume-001",
            request_id="req-resume",
            mode="balanced",
            status="RUNNING",
            route="deep_research",
            raw_question="resumable test",
            normalized_question="resumable test",
            context={"resumable": True},
            quality_threshold=None,
            crosscheck=False,
            max_retries=1,
        )
        conn.commit()

    # Session 2: resume and complete
    with connect(db_path) as conn:
        run = get_run(conn, run_id="run-resume-001")
        assert run is not None
        assert run["status"] == "RUNNING"

        update_run(conn, run_id="run-resume-001", status="COMPLETED")
        conn.commit()

        completed = get_run(conn, run_id="run-resume-001")
        assert completed["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# L6-1e: Context JSON survives restart
# ---------------------------------------------------------------------------

def test_context_json_survives(tmp_path: Path):
    """Complex context JSON should survive close/reopen."""
    db_path = tmp_path / "advisor.sqlite3"
    init_db(db_path)
    context = {
        "channel": "feishu_ws",
        "chat_id": "c-001",
        "nested": {"deep": [1, 2, 3]},
    }

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="run-ctx-001",
            request_id="req-ctx",
            mode="balanced",
            status="pending",
            route="quick_ask",
            raw_question="context test",
            normalized_question="context test",
            context=context,
            quality_threshold=None,
            crosscheck=False,
            max_retries=0,
        )
        conn.commit()

    with connect(db_path) as conn:
        run = get_run(conn, run_id="run-ctx-001")

    assert run is not None
    ctx = run.get("context") or run.get("context_json")
    if isinstance(ctx, str):
        ctx = json.loads(ctx)
    assert ctx["channel"] == "feishu_ws"
    assert ctx["nested"]["deep"] == [1, 2, 3]
