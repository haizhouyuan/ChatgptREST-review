"""L7-2: Canary routing — progressive traffic shifting.

Tests canary routing governance where a percentage of traffic is routed
to a new code path, with gradual rollout and automatic rollback on degradation.

Canary properties tested:
- Canary runs are flagged and tracked separately
- Canary percentage routing is deterministic for a given request_id hash
- Canary degradation triggers rollback metadata
- Canary graduation — promotion to primary
- Canary metrics aggregation for rollout decisions
"""
from __future__ import annotations

import hashlib
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


def _canary_eligible(request_id: str, canary_pct: int) -> bool:
    """Deterministic canary routing: hash request_id mod 100 < canary_pct."""
    h = int(hashlib.sha256(request_id.encode()).hexdigest()[:8], 16)
    return (h % 100) < canary_pct


# ---------------------------------------------------------------------------
# L7-2a: Canary run flagged in context
# ---------------------------------------------------------------------------

def test_canary_run_flagged(tmp_path: Path):
    """A canary run has canary=True in its context."""
    db_path = tmp_path / "canary.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="canary-001",
            request_id="req-canary-001",
            mode="balanced",
            status="NEW",
            route="quick_ask",
            raw_question="canary test",
            normalized_question="canary test",
            context={
                "canary": True,
                "canary_version": "v4.0-alpha",
                "canary_pct": 10,
            },
            quality_threshold=None,
            crosscheck=False,
            max_retries=1,
        )
        conn.commit()

        run = get_run(conn, run_id="canary-001")
        ctx = run.get("context") or run.get("context_json")
        if isinstance(ctx, str):
            ctx = json.loads(ctx)
        assert ctx["canary"] is True
        assert ctx["canary_version"] == "v4.0-alpha"


# ---------------------------------------------------------------------------
# L7-2b: Deterministic canary hash routing
# ---------------------------------------------------------------------------

def test_canary_routing_deterministic():
    """Same request_id always routes the same way for a given canary_pct."""
    req_id = "req-deterministic-001"

    results = []
    for _ in range(100):
        results.append(_canary_eligible(req_id, 20))

    # All iterations should produce the same result
    assert len(set(results)) == 1, "Canary routing must be deterministic"


def test_canary_routing_distribution():
    """Canary routing should roughly match target percentage over many requests."""
    canary_pct = 20
    total = 1000
    canary_count = sum(
        1 for i in range(total) if _canary_eligible(f"req-{i:05d}", canary_pct)
    )

    # Should be roughly 20% ± 5% (with 1000 samples)
    ratio = canary_count / total
    assert 0.10 <= ratio <= 0.30, (
        f"Canary ratio {ratio:.2%} too far from target {canary_pct}%"
    )


# ---------------------------------------------------------------------------
# L7-2c: Canary degradation triggers rollback events
# ---------------------------------------------------------------------------

def test_canary_degradation_rollback(tmp_path: Path):
    """When canary quality drops, a rollback event is recorded."""
    db_path = tmp_path / "canary.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="canary-deg-001",
            request_id="req-deg",
            mode="balanced",
            status="RUNNING",
            route="quick_ask",
            raw_question="canary degradation test",
            normalized_question="canary degradation test",
            context={"canary": True, "canary_version": "v4.0-alpha"},
            quality_threshold=80,
            crosscheck=False,
            max_retries=1,
        )
        conn.commit()

        # Record degradation
        append_event(
            conn,
            run_id="canary-deg-001",
            type="canary_degradation",
            payload={
                "quality_score": 45,
                "threshold": 80,
                "action": "rollback",
                "canary_version": "v4.0-alpha",
            },
        )
        conn.commit()

        update_run(conn, run_id="canary-deg-001", status="DEGRADED")
        conn.commit()

        run = get_run(conn, run_id="canary-deg-001")
        assert run["status"] == "DEGRADED"

        events, count = list_events(conn, run_id="canary-deg-001")
        assert any(e["type"] == "canary_degradation" for e in events)


# ---------------------------------------------------------------------------
# L7-2d: Canary graduation — promote to primary
# ---------------------------------------------------------------------------

def test_canary_graduation(tmp_path: Path):
    """A successful canary run records a graduation event."""
    db_path = tmp_path / "canary.sqlite3"
    init_db(db_path)

    with connect(db_path) as conn:
        create_run(
            conn,
            run_id="canary-grad-001",
            request_id="req-grad",
            mode="balanced",
            status="RUNNING",
            route="quick_ask",
            raw_question="canary graduation test",
            normalized_question="canary graduation test",
            context={"canary": True, "canary_version": "v4.0-alpha"},
            quality_threshold=80,
            crosscheck=False,
            max_retries=1,
        )
        conn.commit()

        # Canary succeeds with high quality
        append_event(
            conn,
            run_id="canary-grad-001",
            type="canary_graduation",
            payload={
                "quality_score": 95,
                "threshold": 80,
                "action": "promote",
                "canary_version": "v4.0-alpha",
                "promoted_to": "primary",
            },
        )
        conn.commit()

        update_run(conn, run_id="canary-grad-001", status="COMPLETED")
        conn.commit()

        events, count = list_events(conn, run_id="canary-grad-001")
        grad_events = [e for e in events if e["type"] == "canary_graduation"]
        assert len(grad_events) == 1

        payload = grad_events[0].get("payload") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["action"] == "promote"
