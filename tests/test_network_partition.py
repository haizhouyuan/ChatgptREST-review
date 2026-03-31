"""L6-3: Network partition simulation.

Tests how the system handles unreachable dependencies at the data layer:
- DB operations remain functional when external services are down
- Error recording works during partition
- Recovery after reconnection preserves state
"""
from __future__ import annotations

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
# L6-3a: DB writes work even when LLM connector would fail
# ---------------------------------------------------------------------------

def test_db_writes_independent_of_llm(tmp_path: Path):
    """DB operations should work regardless of external LLM availability."""
    db_path = tmp_path / "partition.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="part-001",
            request_id="req-part-001",
            mode="balanced",
            status="NEW",
            route="quick_ask",
            raw_question="partition test",
            normalized_question="partition test",
            context=None,
            quality_threshold=None,
            crosscheck=False,
            max_retries=1,
        )
        conn.commit()

        # Record the failure
        append_event(
            conn,
            run_id="part-001",
            type="llm_error",
            payload={"error": "Connection refused", "provider": "chatgpt"},
        )
        conn.commit()

        update_run(conn, run_id="part-001", status="FAILED",
                   error_type="NetworkPartition",
                   error="LLM unreachable: Connection refused")
        conn.commit()

        run = get_run(conn, run_id="part-001")
        assert run["status"] == "FAILED"

        events, count = list_events(conn, run_id="part-001")
        assert len(events) == 1
        assert events[0]["type"] == "llm_error"


# ---------------------------------------------------------------------------
# L6-3b: Multiple partitions recorded as events
# ---------------------------------------------------------------------------

def test_multiple_partition_events_recorded(tmp_path: Path):
    """Multiple network errors should be tracked as separate events."""
    db_path = tmp_path / "partition.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="part-multi-001",
            request_id="req-pm",
            mode="balanced",
            status="RUNNING",
            route="quick_ask",
            raw_question="multi-partition test",
            normalized_question="multi-partition test",
            context=None,
            quality_threshold=None,
            crosscheck=False,
            max_retries=3,
        )
        conn.commit()

        # Record 3 retry failures
        for i in range(3):
            append_event(
                conn,
                run_id="part-multi-001",
                type="retry_failed",
                payload={"attempt": i + 1, "error": f"timeout attempt {i+1}"},
            )
        conn.commit()

        events, count = list_events(conn, run_id="part-multi-001")
        assert len(events) == 3
        for evt in events:
            assert evt["type"] == "retry_failed"


# ---------------------------------------------------------------------------
# L6-3c: Recovery after partition — run can be resumed
# ---------------------------------------------------------------------------

def test_recovery_after_partition(tmp_path: Path):
    """After partition recovery, a failed run can be retried and completed."""
    db_path = tmp_path / "partition.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="part-recover-001",
            request_id="req-pr",
            mode="balanced",
            status="FAILED",
            route="quick_ask",
            raw_question="recovery test",
            normalized_question="recovery test",
            context=None,
            quality_threshold=None,
            crosscheck=False,
            max_retries=1,
            degraded=True,
        )
        conn.commit()

    # "Restart" — new connection (simulating service recovery)
    with connect(db_path) as conn:
        run = get_run(conn, run_id="part-recover-001")
        assert run["status"] == "FAILED"

        # Retry and succeed
        update_run(conn, run_id="part-recover-001", status="RUNNING")
        conn.commit()

        append_event(
            conn,
            run_id="part-recover-001",
            type="recovery_retry",
            payload={"trigger": "partition_resolved"},
        )
        conn.commit()

        update_run(conn, run_id="part-recover-001", status="COMPLETED")
        conn.commit()

        run = get_run(conn, run_id="part-recover-001")
        assert run["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# L6-3d: Feishu gateway module importable (doesn't require connection)
# ---------------------------------------------------------------------------

def test_feishu_gateway_importable():
    """Feishu gateway module should import without needing a live WS connection."""
    from chatgptrest.advisor.feishu_ws_gateway import FeishuWSGateway
    assert callable(FeishuWSGateway)


# ---------------------------------------------------------------------------
# L6-3e: Memory manager survives with no external deps
# ---------------------------------------------------------------------------

def test_memory_manager_independent(tmp_path: Path):
    """Memory manager should work purely on local SQLite, no network deps."""
    from chatgptrest.kernel.memory_manager import MemoryManager

    mm = MemoryManager(db_path=str(tmp_path / "mem.db"))
    try:
        mm.add_conversation_turn(
            "partition-session",
            "question during partition",
            "local-only answer",
        )

        history = mm.get_conversation_history("partition-session", limit=5)
        all_text = " ".join(str(h) for h in history)
        assert "partition" in all_text
    finally:
        mm.close()
