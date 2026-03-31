"""L7-1: Shadow mode — dual-write governance.

Tests shadow run behavior where a new code path runs in parallel
but results are only recorded, not served to the user.

Shadow mode properties tested:
- Shadow runs are tracked with shadow=True flag
- Shadow results can be compared against primary
- Shadow failures don't affect primary run lifecycle
- Shadow metrics are recorded for analysis
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from chatgptrest.core.advisor_runs import (
    create_run,
    get_run,
    update_run,
    append_event,
    list_events,
)
from chatgptrest.core.db import connect, init_db


# ---------------------------------------------------------------------------
# L7-1a: Shadow run tracked alongside primary
# ---------------------------------------------------------------------------

def test_shadow_run_tracked_alongside_primary(tmp_path: Path):
    """A shadow run is created alongside the primary, both trackable."""
    db_path = tmp_path / "shadow.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        # Primary run
        create_run(
            conn,
            run_id="primary-001",
            request_id="req-001",
            mode="balanced",
            status="NEW",
            route="quick_ask",
            raw_question="test question",
            normalized_question="test question",
            context={"shadow": False},
            quality_threshold=None,
            crosscheck=False,
            max_retries=1,
        )
        # Shadow run
        create_run(
            conn,
            run_id="shadow-001",
            request_id="req-001",
            mode="balanced",
            status="NEW",
            route="quick_ask",
            raw_question="test question",
            normalized_question="test question",
            context={"shadow": True, "primary_run_id": "primary-001"},
            quality_threshold=None,
            crosscheck=False,
            max_retries=1,
        )
        conn.commit()

        primary = get_run(conn, run_id="primary-001")
        shadow = get_run(conn, run_id="shadow-001")

        assert primary is not None
        assert shadow is not None
        assert primary["run_id"] != shadow["run_id"]
        assert primary["request_id"] == shadow["request_id"]


# ---------------------------------------------------------------------------
# L7-1b: Shadow failure doesn't affect primary
# ---------------------------------------------------------------------------

def test_shadow_failure_does_not_affect_primary(tmp_path: Path):
    """When a shadow run fails, the primary can still complete normally."""
    db_path = tmp_path / "shadow.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="primary-002",
            request_id="req-002",
            mode="balanced",
            status="RUNNING",
            route="quick_ask",
            raw_question="shadow test",
            normalized_question="shadow test",
            context={"shadow": False},
            quality_threshold=None,
            crosscheck=False,
            max_retries=1,
        )
        create_run(
            conn,
            run_id="shadow-002",
            request_id="req-002",
            mode="balanced",
            status="RUNNING",
            route="quick_ask",
            raw_question="shadow test",
            normalized_question="shadow test",
            context={"shadow": True, "primary_run_id": "primary-002"},
            quality_threshold=None,
            crosscheck=False,
            max_retries=1,
        )
        conn.commit()

        # Shadow fails
        update_run(conn, run_id="shadow-002", status="FAILED",
                   error="Shadow: timeout")
        conn.commit()

        # Primary succeeds
        update_run(conn, run_id="primary-002", status="COMPLETED")
        conn.commit()

        primary = get_run(conn, run_id="primary-002")
        shadow = get_run(conn, run_id="shadow-002")

        assert primary["status"] == "COMPLETED"
        assert shadow["status"] == "FAILED"


# ---------------------------------------------------------------------------
# L7-1c: Shadow comparison events recorded
# ---------------------------------------------------------------------------

def test_shadow_comparison_events_recorded(tmp_path: Path):
    """Comparison between primary and shadow is recorded as an event."""
    db_path = tmp_path / "shadow.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="primary-003",
            request_id="req-003",
            mode="balanced",
            status="NEW",
            route="quick_ask",
            raw_question="comparison test",
            normalized_question="comparison test",
            context=None,
            quality_threshold=None,
            crosscheck=False,
            max_retries=0,
        )
        conn.commit()

        # Record comparison event
        append_event(
            conn,
            run_id="primary-003",
            type="shadow_comparison",
            payload={
                "primary_answer_chars": 500,
                "shadow_answer_chars": 480,
                "latency_primary_ms": 3200,
                "latency_shadow_ms": 2800,
                "semantic_match": 0.92,
                "cost_primary": 0.05,
                "cost_shadow": 0.02,
            },
        )
        conn.commit()

        events, count = list_events(conn, run_id="primary-003")
        assert len(events) == 1
        evt = events[0]
        assert evt["type"] == "shadow_comparison"

        payload = evt.get("payload") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["semantic_match"] == 0.92


# ---------------------------------------------------------------------------
# L7-1d: Shadow mode module structure verification
# ---------------------------------------------------------------------------

def test_advisor_runtime_importable():
    """Advisor runtime module should be importable."""
    from chatgptrest.advisor import runtime
    assert hasattr(runtime, "__name__")


def test_dispatch_module_importable():
    """Advisor dispatch module should be importable."""
    from chatgptrest.advisor import dispatch
    assert hasattr(dispatch, "__name__")
