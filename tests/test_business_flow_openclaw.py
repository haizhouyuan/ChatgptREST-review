"""L5-3: OpenClaw → async answer business flow.

Verifies the cross-version contract at the data layer level:
advisor_runs can track runs coming from OpenClaw (trace_id, agent_id),
and the durable run lifecycle supports asynchronous answer retrieval.
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
# L5-3a: OpenClaw trace_id stored in run context
# ---------------------------------------------------------------------------

def test_openclaw_trace_id_stored(tmp_path: Path):
    """trace_id from OpenClaw should be stored in run context."""
    db_path = tmp_path / "oc.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="oc-001",
            request_id="req-oc-001",
            mode="balanced",
            status="NEW",
            route="quick_ask",
            raw_question="openclaw test question",
            normalized_question="openclaw test question",
            context={
                "trace_id": "oc-trace-001",
                "agent_id": "openclaw_plugin",
                "channel": "openclaw",
            },
            quality_threshold=None,
            crosscheck=False,
            max_retries=1,
        )
        conn.commit()

        run = get_run(conn, run_id="oc-001")
        assert run is not None
        ctx = run.get("context") or run.get("context_json")
        if isinstance(ctx, str):
            ctx = json.loads(ctx)
        assert ctx["trace_id"] == "oc-trace-001"
        assert ctx["agent_id"] == "openclaw_plugin"


# ---------------------------------------------------------------------------
# L5-3b: Async answer lifecycle — RUNNING → COMPLETED with event trail
# ---------------------------------------------------------------------------

def test_async_answer_lifecycle_with_events(tmp_path: Path):
    """Async answer: create run → event trail → complete with answer."""
    db_path = tmp_path / "oc.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="oc-async-001",
            request_id="req-oc-async",
            mode="balanced",
            status="NEW",
            route="quick_ask",
            raw_question="async answer test",
            normalized_question="async answer test",
            context=None,
            quality_threshold=None,
            crosscheck=False,
            max_retries=1,
        )
        conn.commit()

        # Simulate dispatching
        update_run(conn, run_id="oc-async-001", status="DISPATCHING")
        conn.commit()

        # Record an event
        append_event(
            conn,
            run_id="oc-async-001",
            type="llm_called",
            payload={"provider": "chatgpt", "preset": "pro"},
        )
        conn.commit()

        # Complete
        update_run(conn, run_id="oc-async-001", status="COMPLETED")
        conn.commit()

        # Verify
        run = get_run(conn, run_id="oc-async-001")
        assert run["status"] == "COMPLETED"

        events, count = list_events(conn, run_id="oc-async-001")
        assert len(events) >= 1
        assert events[0]["type"] == "llm_called"


# ---------------------------------------------------------------------------
# L5-3c: Multiple concurrent runs don't interfere
# ---------------------------------------------------------------------------

def test_concurrent_runs_isolated(tmp_path: Path):
    """Multiple runs should be independently trackable."""
    db_path = tmp_path / "oc.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        for i in range(3):
            create_run(
                conn,
                run_id=f"oc-conc-{i:03d}",
                request_id=f"req-conc-{i:03d}",
                mode="balanced",
                status="NEW",
                route="quick_ask",
                raw_question=f"concurrent test {i}",
                normalized_question=f"concurrent test {i}",
                context={"run_index": i},
                quality_threshold=None,
                crosscheck=False,
                max_retries=1,
            )
        conn.commit()

        # Complete only run 1
        update_run(conn, run_id="oc-conc-001", status="COMPLETED")
        conn.commit()

        # Verify isolation
        r0 = get_run(conn, run_id="oc-conc-000")
        r1 = get_run(conn, run_id="oc-conc-001")
        r2 = get_run(conn, run_id="oc-conc-002")

        assert r0["status"] == "NEW"
        assert r1["status"] == "COMPLETED"
        assert r2["status"] == "NEW"


# ---------------------------------------------------------------------------
# L5-3d: Core modules importable
# ---------------------------------------------------------------------------

def test_core_modules_importable():
    """Core API modules should be importable for contract verification."""
    from chatgptrest.core import advisor_runs
    from chatgptrest.core import db

    assert callable(advisor_runs.create_run)
    assert callable(advisor_runs.get_run)
    assert callable(advisor_runs.update_run)
    assert callable(db.connect)
    assert callable(db.init_db)
