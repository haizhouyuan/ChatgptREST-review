"""L5-5: Planning lane — advisor run lifecycle with steps and events.

Tests the durable planning pipeline at the data layer, including:
- Multi-step runs (step creation, ordering)
- Run event trail (route selection, LLM calls, quality checks)
- Run status transitions for planning mode
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from chatgptrest.core.advisor_runs import (
    create_run,
    get_run,
    update_run,
    upsert_step,
    list_steps,
    append_event,
    list_events,
)
from chatgptrest.core.db import connect, init_db


# ---------------------------------------------------------------------------
# L5-5a: Planning run with multiple steps
# ---------------------------------------------------------------------------

def test_planning_run_with_steps(tmp_path: Path):
    """A planning run can have multiple ordered steps."""
    db_path = tmp_path / "plan.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="plan-001",
            request_id="req-plan-001",
            mode="balanced",
            status="NEW",
            route="funnel",
            raw_question="设计投研计划",
            normalized_question="设计投研计划",
            context=None,
            quality_threshold=None,
            crosscheck=False,
            max_retries=1,
        )
        conn.commit()

        # Add steps
        upsert_step(conn, run_id="plan-001", step_id="step-1",
                     step_type="normalize", status="SUCCEEDED")
        upsert_step(conn, run_id="plan-001", step_id="step-2",
                     step_type="dispatch", status="EXECUTING")
        upsert_step(conn, run_id="plan-001", step_id="step-3",
                     step_type="review", status="PENDING")
        conn.commit()

        steps = list_steps(conn, run_id="plan-001")
        assert len(steps) == 3

        # Steps should have correct statuses
        status_map = {s["step_id"]: s["status"] for s in steps}
        assert status_map["step-1"] == "SUCCEEDED"
        assert status_map["step-2"] == "EXECUTING"
        assert status_map["step-3"] == "PENDING"


# ---------------------------------------------------------------------------
# L5-5b: Run event trail tracks planning decisions
# ---------------------------------------------------------------------------

def test_planning_event_trail(tmp_path: Path):
    """Planning decisions should be recorded as events."""
    db_path = tmp_path / "plan.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="plan-evt-001",
            request_id="req-plan-evt",
            mode="balanced",
            status="NEW",
            route="funnel",
            raw_question="event trail test",
            normalized_question="event trail test",
            context=None,
            quality_threshold=None,
            crosscheck=False,
            max_retries=0,
        )
        conn.commit()

        append_event(conn, run_id="plan-evt-001", type="route_selected",
                     payload={"route": "funnel", "confidence": 0.95})
        append_event(conn, run_id="plan-evt-001", type="llm_called",
                     payload={"provider": "chatgpt", "preset": "pro"})
        append_event(conn, run_id="plan-evt-001", type="quality_check",
                     payload={"score": 85, "threshold": 80, "passed": True})
        conn.commit()

        events, count = list_events(conn, run_id="plan-evt-001")
        assert len(events) == 3

        types = [e["type"] for e in events]
        assert "route_selected" in types
        assert "llm_called" in types
        assert "quality_check" in types


# ---------------------------------------------------------------------------
# L5-5c: Step update lifecycle
# ---------------------------------------------------------------------------

def test_step_update_lifecycle(tmp_path: Path):
    """Steps can be updated from NEW → RUNNING → COMPLETED."""
    db_path = tmp_path / "plan.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="plan-step-upd",
            request_id="req-step-upd",
            mode="balanced",
            status="RUNNING",
            route="funnel",
            raw_question="step update test",
            normalized_question="step update test",
            context=None,
            quality_threshold=None,
            crosscheck=False,
            max_retries=0,
        )
        conn.commit()

        # Create step as NEW
        upsert_step(conn, run_id="plan-step-upd", step_id="s-upd-1",
                     step_type="normalize", status="PENDING")
        conn.commit()

        steps = list_steps(conn, run_id="plan-step-upd")
        assert steps[0]["status"] == "PENDING"

        # Update to EXECUTING
        upsert_step(conn, run_id="plan-step-upd", step_id="s-upd-1",
                     step_type="normalize", status="EXECUTING")
        conn.commit()

        steps = list_steps(conn, run_id="plan-step-upd")
        assert steps[0]["status"] == "EXECUTING"

        # Update to SUCCEEDED
        upsert_step(conn, run_id="plan-step-upd", step_id="s-upd-1",
                     step_type="normalize", status="SUCCEEDED")
        conn.commit()

        steps = list_steps(conn, run_id="plan-step-upd")
        assert steps[0]["status"] == "SUCCEEDED"


# ---------------------------------------------------------------------------
# L5-5d: Degraded run status transitions
# ---------------------------------------------------------------------------

def test_degraded_status_transition(tmp_path: Path):
    """A run can transition to DEGRADED and then COMPLETED."""
    db_path = tmp_path / "plan.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="plan-deg-001",
            request_id="req-deg",
            mode="balanced",
            status="NEW",
            route="funnel",
            raw_question="degraded test",
            normalized_question="degraded test",
            context=None,
            quality_threshold=None,
            crosscheck=False,
            max_retries=0,
            degraded=True,
        )
        conn.commit()

        run = get_run(conn, run_id="plan-deg-001")
        assert run["degraded"] in (True, 1)

        update_run(conn, run_id="plan-deg-001", status="COMPLETED")
        conn.commit()

        run = get_run(conn, run_id="plan-deg-001")
        assert run["status"] == "COMPLETED"
        assert run["degraded"] in (True, 1)
