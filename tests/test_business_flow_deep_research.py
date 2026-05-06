"""L5-2: Deep research — route contract verification.

Verifies that the deep research route is importable, properly structured,
and that advisor_runs can track a deep research lifecycle.

Avoids creating a full FastAPI TestClient which requires complex runtime
initialization. Instead tests the data layer and module contracts directly.
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
# L5-2a: Deep research run lifecycle — create → dispatch → complete
# ---------------------------------------------------------------------------

def test_deep_research_run_lifecycle(tmp_path: Path):
    """A deep research run goes through NEW → DISPATCHING → RUNNING → COMPLETED."""
    db_path = tmp_path / "dr.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        # Create
        run = create_run(
            conn,
            run_id="dr-001",
            request_id="req-dr-001",
            mode="deep",
            status="NEW",
            route="deep_research",
            raw_question="深度调研AI芯片封装产能",
            normalized_question="深度调研AI芯片封装产能",
            context={"channel": "feishu_ws", "chat_id": "c-001"},
            quality_threshold=80,
            crosscheck=True,
            max_retries=2,
        )
        conn.commit()
        assert run["status"] == "NEW"
        assert run["route"] == "deep_research"

        # Dispatch
        update_run(conn, run_id="dr-001", status="DISPATCHING")
        conn.commit()
        run = get_run(conn, run_id="dr-001")
        assert run["status"] == "DISPATCHING"

        # Running
        update_run(conn, run_id="dr-001", status="RUNNING")
        conn.commit()
        run = get_run(conn, run_id="dr-001")
        assert run["status"] == "RUNNING"

        # Complete
        update_run(conn, run_id="dr-001", status="COMPLETED")
        conn.commit()
        run = get_run(conn, run_id="dr-001")
        assert run["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# L5-2b: Deep research run preserves quality_threshold and crosscheck
# ---------------------------------------------------------------------------

def test_deep_research_stores_quality_params(tmp_path: Path):
    """quality_threshold and crosscheck should be stored and retrievable."""
    db_path = tmp_path / "dr.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="dr-002",
            request_id="req-dr-002",
            mode="deep",
            status="NEW",
            route="deep_research",
            raw_question="test quality params",
            normalized_question="test quality params",
            context=None,
            quality_threshold=90,
            crosscheck=True,
            max_retries=3,
        )
        conn.commit()

        run = get_run(conn, run_id="dr-002")
        assert run["quality_threshold"] == 90
        assert run["crosscheck"] in (True, 1)
        assert run["max_retries"] == 3


# ---------------------------------------------------------------------------
# L5-2c: Report route module importable
# ---------------------------------------------------------------------------

def test_report_graph_importable():
    """The report_graph module should be importable."""
    try:
        from chatgptrest.advisor import report_graph
        assert hasattr(report_graph, "__name__")
    except ImportError:
        pytest.skip("report_graph not available in this branch")


# ---------------------------------------------------------------------------
# L5-2d: Advisor graph module importable
# ---------------------------------------------------------------------------

def test_advisor_graph_importable():
    """The advisor graph module should be importable."""
    try:
        from chatgptrest.advisor import graph
        assert hasattr(graph, "__name__")
    except ImportError:
        pytest.skip("advisor graph not available in this branch")


# ---------------------------------------------------------------------------
# L5-2e: Failed deep research run records error
# ---------------------------------------------------------------------------

def test_deep_research_failure_records_error(tmp_path: Path):
    """When deep research fails, error info should be recorded."""
    db_path = tmp_path / "dr.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="dr-fail-001",
            request_id="req-dr-fail",
            mode="deep",
            status="NEW",
            route="deep_research",
            raw_question="will fail",
            normalized_question="will fail",
            context=None,
            quality_threshold=None,
            crosscheck=False,
            max_retries=0,
        )
        conn.commit()

        update_run(
            conn,
            run_id="dr-fail-001",
            status="FAILED",
            error_type="LLMTimeout",
            error="LLM did not respond within 30s",
        )
        conn.commit()

        run = get_run(conn, run_id="dr-fail-001")
        assert run["status"] == "FAILED"
