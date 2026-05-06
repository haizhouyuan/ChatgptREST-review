"""L5-4: Multi-turn conversation with memory continuity.

Tests that:
- Conversation turns are stored in working memory
- Subsequent prompts include previous context
- Working memory capacity enforcement works (WORKING_CAPACITY=50)
- Oldest turns are evicted when capacity is reached
- get_conversation_history returns turns in correct order
"""
from __future__ import annotations

from pathlib import Path

import pytest

from chatgptrest.kernel.memory_manager import MemoryManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_memory_manager(tmp_path: Path) -> MemoryManager:
    """Fresh MemoryManager with a temp DB."""
    return MemoryManager(db_path=str(tmp_path / "test_memory.db"))


# ---------------------------------------------------------------------------
# L5-4a: Basic multi-turn — 2 turns captured correctly
# ---------------------------------------------------------------------------

def test_two_turn_conversation_stored(tmp_path: Path):
    """Two conversation turns are stored and retrievable."""
    mm = _make_memory_manager(tmp_path)
    try:
        session = "session-001"

        mm.add_conversation_turn(session, "什么是 PE ratio", "PE 是市盈率的缩写…")
        mm.add_conversation_turn(session, "那 PB ratio 呢", "PB 是市净率…")

        history = mm.get_conversation_history(session, limit=10)
        assert len(history) >= 2

        # Both turns should be present
        all_text = " ".join(str(h) for h in history)
        assert "PE" in all_text
        assert "PB" in all_text
    finally:
        mm.close()


# ---------------------------------------------------------------------------
# L5-4b: Session isolation — different sessions don't leak
# ---------------------------------------------------------------------------

def test_session_isolation(tmp_path: Path):
    """Turns in session A are not visible in session B."""
    mm = _make_memory_manager(tmp_path)
    try:
        mm.add_conversation_turn("sess-A", "question A", "answer A")
        mm.add_conversation_turn("sess-B", "question B", "answer B")

        history_a = mm.get_conversation_history("sess-A", limit=10)
        history_b = mm.get_conversation_history("sess-B", limit=10)

        a_text = " ".join(str(h) for h in history_a)
        b_text = " ".join(str(h) for h in history_b)

        assert "question A" in a_text or "answer A" in a_text
        assert "question B" not in a_text
        assert "question B" in b_text or "answer B" in b_text
        assert "question A" not in b_text
    finally:
        mm.close()


# ---------------------------------------------------------------------------
# L5-4c: Working memory capacity enforcement
# ---------------------------------------------------------------------------

def test_working_memory_capacity_enforcement(tmp_path: Path):
    """Working-memory record count stays bounded and turn pairs stay intact."""
    mm = _make_memory_manager(tmp_path)
    try:
        session = "sess-capacity"
        capacity = mm.WORKING_CAPACITY

        # Fill to capacity + 10
        for i in range(capacity + 10):
            mm.add_conversation_turn(
                session,
                f"question-{i:04d}",
                f"answer-{i:04d}",
            )

        history = mm.get_conversation_history(session, limit=capacity + 20)

        # Working memory should not grow unbounded
        # It should be at or around WORKING_CAPACITY
        # (each turn writes ~2 records: user + assistant)
        conn = mm._conn()
        count = conn.execute(
            """SELECT count(*) FROM memory_records
               WHERE tier = 'working'
               AND json_extract(source, '$.session_id') = ?""",
            (session,),
        ).fetchone()[0]
        turn_counts = conn.execute(
            """SELECT json_extract(value, '$.turn_id') AS turn_id, count(*) AS n
               FROM memory_records
               WHERE tier = 'working'
               AND json_extract(source, '$.session_id') = ?
               GROUP BY turn_id
               ORDER BY turn_id""",
            (session,),
        ).fetchall()

        # Working memory should stay within the configured record budget.
        assert count <= capacity, (
            f"Working memory grew to {count}, expected ≤ {capacity}"
        )
        # Every surviving turn should still be represented by a full pair.
        assert turn_counts, "Expected at least one surviving turn pair"
        assert all(row["n"] == 2 for row in turn_counts), turn_counts
        assert len(turn_counts) <= capacity // 2
    finally:
        mm.close()


# ---------------------------------------------------------------------------
# L5-4d: Eviction preserves recent turns
# ---------------------------------------------------------------------------

def test_eviction_preserves_recent_turns(tmp_path: Path):
    """After eviction, oldest turns should be gone, recent turns should exist."""
    mm = _make_memory_manager(tmp_path)
    try:
        session = "sess-evict"
        capacity = mm.WORKING_CAPACITY
        inserted_turns = capacity + 5

        # Write capacity + 5 turns
        for i in range(inserted_turns):
            mm.add_conversation_turn(
                session,
                f"q-{i:04d}",
                f"a-{i:04d}",
            )

        # Get full history
        history = mm.get_conversation_history(session, limit=capacity * 3)
        all_text = " ".join(str(h) for h in history)
        retained_turns = capacity // 2
        oldest_retained = inserted_turns - retained_turns

        # Some turns should still be present (working memory not empty).
        assert len(history) > 0, "Working memory should not be empty after eviction"
        # Everything older than the retained window should be gone.
        assert f"q-{oldest_retained - 1:04d}" not in all_text
        assert f"a-{oldest_retained - 1:04d}" not in all_text
        # The boundary turn and the newest turn should remain.
        assert f"q-{oldest_retained:04d}" in all_text
        assert f"a-{inserted_turns - 1:04d}" in all_text
    finally:
        mm.close()


# ---------------------------------------------------------------------------
# L5-4e: Conversation history returns ordered entries
# ---------------------------------------------------------------------------

def test_conversation_history_is_ordered(tmp_path: Path):
    """get_conversation_history returns entries in temporal order."""
    mm = _make_memory_manager(tmp_path)
    try:
        session = "sess-order"

        mm.add_conversation_turn(session, "first", "first-reply")
        mm.add_conversation_turn(session, "second", "second-reply")
        mm.add_conversation_turn(session, "third", "third-reply")

        history = mm.get_conversation_history(session, limit=10)

        messages = [entry.get("message", "") for entry in history if isinstance(entry, dict)]
        assert messages[:6] == [
            "first",
            "first-reply",
            "second",
            "second-reply",
            "third",
            "third-reply",
        ]
    finally:
        mm.close()
