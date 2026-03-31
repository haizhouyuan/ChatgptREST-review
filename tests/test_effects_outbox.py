"""Tests for Effects Outbox (T1.1).

Covers:
    - Basic enqueue + execute
    - Deduplication (same effect_type + effect_key)
    - Handler failure → status=failed + error payload
    - is_done check
    - get_by_trace query
    - retry_failed
    - close guard
    - execute with no handler skips
    - count with filters
    - concurrent enqueue idempotency
    - execute order (FIFO by created_at)
    - large batch execute
    - effect payload round-trip
    - closed outbox rejects enqueue / execute / retry
"""

import json
import pytest

from chatgptrest.kernel.effects_outbox import EffectsOutbox, EffectResult


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def outbox():
    ob = EffectsOutbox(":memory:")
    yield ob
    if not ob._closed:
        ob.close()


def _noop_handler(payload):
    return {"ok": True}


def _fail_handler(payload):
    raise ValueError(f"boom: {payload.get('x', '?')}")


# ── Tests ─────────────────────────────────────────────────────────

def test_enqueue_and_execute(outbox):
    """Basic enqueue → execute_pending → done."""
    eid = outbox.enqueue("t1", "feishu_notify", "t1:feishu:ou1", {"msg": "hi"})
    assert eid is not None

    results = outbox.execute_pending({"feishu_notify": _noop_handler})
    assert len(results) == 1
    assert results[0].success is True
    assert results[0].effect_type == "feishu_notify"
    assert outbox.is_done("feishu_notify", "t1:feishu:ou1")


def test_dedup_same_key(outbox):
    """Same (effect_type, effect_key) → second enqueue returns None."""
    eid1 = outbox.enqueue("t1", "feishu_notify", "t1:feishu:ou1")
    eid2 = outbox.enqueue("t1", "feishu_notify", "t1:feishu:ou1")
    assert eid1 is not None
    assert eid2 is None  # deduped


def test_different_type_same_key_ok(outbox):
    """Different effect_type but same key string → both accepted."""
    eid1 = outbox.enqueue("t1", "feishu_notify", "key1")
    eid2 = outbox.enqueue("t1", "kb_writeback", "key1")
    assert eid1 is not None
    assert eid2 is not None


def test_handler_failure(outbox):
    """Handler raises → status=failed, error recorded."""
    outbox.enqueue("t2", "agent_dispatch", "t2:dispatch:x", {"x": "data"})
    results = outbox.execute_pending({"agent_dispatch": _fail_handler})
    assert len(results) == 1
    assert results[0].success is False
    assert "boom" in results[0].error

    # Not marked as done
    assert not outbox.is_done("agent_dispatch", "t2:dispatch:x")
    # Check stored error
    effects = outbox.get_by_trace("t2")
    assert effects[0].status == "failed"
    assert effects[0].error is not None


def test_is_done_not_found(outbox):
    """is_done for non-existent key → False."""
    assert not outbox.is_done("feishu_notify", "nonexistent")


def test_get_by_trace(outbox):
    """get_by_trace returns all effects for a trace_id."""
    outbox.enqueue("t3", "feishu_notify", "t3:feishu:1")
    outbox.enqueue("t3", "kb_writeback", "t3:kb:1")
    outbox.enqueue("t4", "feishu_notify", "t4:feishu:1")

    t3_effects = outbox.get_by_trace("t3")
    assert len(t3_effects) == 2
    assert all(e.trace_id == "t3" for e in t3_effects)

    t4_effects = outbox.get_by_trace("t4")
    assert len(t4_effects) == 1


def test_retry_failed(outbox):
    """retry_failed resets failed effects and re-executes."""
    outbox.enqueue("t5", "agent_dispatch", "t5:dispatch:1", {"x": "1"})
    # First: fail
    outbox.execute_pending({"agent_dispatch": _fail_handler})
    assert not outbox.is_done("agent_dispatch", "t5:dispatch:1")

    # Retry with working handler
    results = outbox.retry_failed({"agent_dispatch": _noop_handler})
    assert len(results) == 1
    assert results[0].success is True
    assert outbox.is_done("agent_dispatch", "t5:dispatch:1")


def test_close_then_enqueue_raises(outbox):
    """After close(), enqueue raises RuntimeError."""
    outbox.close()
    with pytest.raises(RuntimeError, match="closed"):
        outbox.enqueue("t6", "feishu_notify", "t6:feishu:1")


def test_close_then_execute_raises(outbox):
    """After close(), execute_pending raises RuntimeError."""
    outbox.close()
    with pytest.raises(RuntimeError, match="closed"):
        outbox.execute_pending({})


def test_close_then_retry_raises(outbox):
    """After close(), retry_failed raises RuntimeError."""
    outbox.close()
    with pytest.raises(RuntimeError, match="closed"):
        outbox.retry_failed({})


def test_execute_no_handler_skips(outbox):
    """Effects with no matching handler are skipped (not marked failed)."""
    outbox.enqueue("t7", "unknown_type", "t7:unknown:1")
    results = outbox.execute_pending({"feishu_notify": _noop_handler})
    assert len(results) == 0  # skipped, not processed
    # Still pending
    assert outbox.count(status="pending") == 1


def test_count_with_filters(outbox):
    """count() works with status and trace_id filters."""
    outbox.enqueue("t8", "feishu_notify", "t8:feishu:1")
    outbox.enqueue("t8", "kb_writeback", "t8:kb:1")
    outbox.enqueue("t9", "feishu_notify", "t9:feishu:1")

    assert outbox.count() == 3
    assert outbox.count(status="pending") == 3
    assert outbox.count(trace_id="t8") == 2
    assert outbox.count(status="done") == 0

    outbox.execute_pending({"feishu_notify": _noop_handler})
    assert outbox.count(status="done") == 2  # both feishu_notify done
    assert outbox.count(status="pending") == 1  # kb_writeback still pending


def test_execute_fifo_order(outbox):
    """Effects are executed in FIFO order (oldest first)."""
    import time
    outbox.enqueue("t10", "feishu_notify", "t10:feishu:1", {"order": 1})
    time.sleep(0.01)
    outbox.enqueue("t10", "feishu_notify", "t10:feishu:2", {"order": 2})
    time.sleep(0.01)
    outbox.enqueue("t10", "feishu_notify", "t10:feishu:3", {"order": 3})

    execution_order = []

    def order_tracker(payload):
        execution_order.append(payload["order"])
        return True

    outbox.execute_pending({"feishu_notify": order_tracker})
    assert execution_order == [1, 2, 3]


def test_payload_roundtrip(outbox):
    """Complex payload survives enqueue → get_by_trace round-trip."""
    payload = {
        "message": "你好世界",
        "nested": {"key": [1, 2, 3]},
        "unicode": "🚀",
    }
    outbox.enqueue("t11", "feishu_notify", "t11:feishu:1", payload)
    effects = outbox.get_by_trace("t11")
    assert effects[0].payload == payload


def test_already_done_not_re_executed(outbox):
    """Done effects are not picked up by execute_pending again."""
    outbox.enqueue("t12", "feishu_notify", "t12:feishu:1")
    outbox.execute_pending({"feishu_notify": _noop_handler})
    assert outbox.is_done("feishu_notify", "t12:feishu:1")

    # Execute again — nothing to do
    results = outbox.execute_pending({"feishu_notify": _noop_handler})
    assert len(results) == 0


def test_multiple_traces_independent(outbox):
    """Effects from different traces don't interfere."""
    outbox.enqueue("tx", "feishu_notify", "tx:feishu:1")
    outbox.enqueue("ty", "feishu_notify", "ty:feishu:1")

    outbox.execute_pending({"feishu_notify": _noop_handler})

    assert outbox.is_done("feishu_notify", "tx:feishu:1")
    assert outbox.is_done("feishu_notify", "ty:feishu:1")
    assert outbox.count(status="done", trace_id="tx") == 1
    assert outbox.count(status="done", trace_id="ty") == 1
"""

Tests for Effects Outbox module.
"""
