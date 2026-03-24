"""Test memory tenant isolation — session_id filtering in get_episodic/get_semantic.

Verifies that when session_id is provided, cross-session memory records
are excluded from retrieval results.
"""

from __future__ import annotations

import pytest

from chatgptrest.kernel.memory_manager import (
    MemoryManager,
    MemoryRecord,
    MemorySource,
    MemoryTier,
    SourceType,
)


@pytest.fixture
def mm():
    manager = MemoryManager(":memory:")
    yield manager
    manager.close()


def _stage_promote(mm: MemoryManager, tier: MemoryTier, *,
                   session_id: str, category: str = "task_result",
                   key: str = "", value: dict | None = None,
                   agent: str = "advisor",
                   role: str = "",
                   account_id: str = "",
                   thread_id: str = "") -> str:
    """Helper that stages a record and forces promotion.

    For SEMANTIC tier the StagingGate requires min_occurrences >= 2,
    so we stage twice with the same fingerprint to pass the gate.
    """
    rec = MemoryRecord(
        category=category,
        key=key or f"test:{session_id}:{category}",
        value=value or {"data": f"from {session_id}"},
        confidence=0.9,
        source=MemorySource(
            type=SourceType.LLM_INFERENCE.value,
            agent=agent,
            role=role,
            session_id=session_id,
            account_id=account_id,
            thread_id=thread_id,
        ).to_dict(),
    )
    record_id = mm.stage(rec)
    if tier == MemoryTier.SEMANTIC:
        # Stage a second record with same fingerprint but different category
        # to meet min_occurrences=2 without hitting same-category dedup
        rec2 = MemoryRecord(
            category=f"_dup_{category}",
            key=f"dup:{key or f'test:{session_id}:{category}'}",
            value=value or {"data": f"from {session_id}"},
            confidence=0.9,
            source=MemorySource(
                type=SourceType.LLM_INFERENCE.value,
                agent=agent,
                role=role,
                session_id=session_id,
                account_id=account_id,
                thread_id=thread_id,
            ).to_dict(),
        )
        mm.stage(rec2)
    mm.promote(record_id, tier, reason="test")
    return record_id


# ── Episodic isolation ────────────────────────────────────────────


def test_episodic_no_session_returns_all(mm: MemoryManager) -> None:
    _stage_promote(mm, MemoryTier.EPISODIC, session_id="sess_A", key="ep_a")
    _stage_promote(mm, MemoryTier.EPISODIC, session_id="sess_B", key="ep_b")
    results = mm.get_episodic()
    assert len(results) == 2


def test_episodic_session_filters(mm: MemoryManager) -> None:
    _stage_promote(mm, MemoryTier.EPISODIC, session_id="sess_A", key="ep_a")
    _stage_promote(mm, MemoryTier.EPISODIC, session_id="sess_B", key="ep_b")
    results = mm.get_episodic(session_id="sess_A")
    assert len(results) == 1
    assert results[0].key == "ep_a"


def test_episodic_session_returns_empty_for_unknown(mm: MemoryManager) -> None:
    _stage_promote(mm, MemoryTier.EPISODIC, session_id="sess_A", key="ep_a")
    results = mm.get_episodic(session_id="sess_UNKNOWN")
    assert len(results) == 0


# ── Semantic isolation ────────────────────────────────────────────


def test_semantic_no_session_returns_all(mm: MemoryManager) -> None:
    _stage_promote(mm, MemoryTier.SEMANTIC, session_id="sess_A",
                   category="user_profile", key="sem_a")
    _stage_promote(mm, MemoryTier.SEMANTIC, session_id="sess_B",
                   category="user_profile", key="sem_b")
    results = mm.get_semantic(domain="user_profile")
    assert len(results) == 2


def test_semantic_session_filters(mm: MemoryManager) -> None:
    _stage_promote(mm, MemoryTier.SEMANTIC, session_id="sess_A",
                   category="user_profile", key="sem_a")
    _stage_promote(mm, MemoryTier.SEMANTIC, session_id="sess_B",
                   category="user_profile", key="sem_b")
    results = mm.get_semantic(domain="user_profile", session_id="sess_A")
    assert len(results) == 1
    assert results[0].key == "sem_a"


def test_semantic_session_returns_empty_for_unknown(mm: MemoryManager) -> None:
    _stage_promote(mm, MemoryTier.SEMANTIC, session_id="sess_A",
                   category="user_profile", key="sem_a")
    results = mm.get_semantic(domain="user_profile", session_id="sess_UNKNOWN")
    assert len(results) == 0


def test_episodic_account_filters(mm: MemoryManager) -> None:
    _stage_promote(mm, MemoryTier.EPISODIC, session_id="sess_A", key="ep_a", account_id="acct_A")
    _stage_promote(mm, MemoryTier.EPISODIC, session_id="sess_B", key="ep_b", account_id="acct_B")
    results = mm.get_episodic(account_id="acct_A")
    assert len(results) == 1
    assert results[0].key == "ep_a"


def test_episodic_thread_filters(mm: MemoryManager) -> None:
    _stage_promote(mm, MemoryTier.EPISODIC, session_id="sess_A", key="ep_a", thread_id="thr_A")
    _stage_promote(mm, MemoryTier.EPISODIC, session_id="sess_B", key="ep_b", thread_id="thr_B")
    results = mm.get_episodic(thread_id="thr_B")
    assert len(results) == 1
    assert results[0].key == "ep_b"


def test_semantic_account_and_thread_filters(mm: MemoryManager) -> None:
    _stage_promote(
        mm,
        MemoryTier.SEMANTIC,
        session_id="sess_A",
        category="user_profile",
        key="sem_a",
        account_id="acct_A",
        thread_id="thr_A",
    )
    _stage_promote(
        mm,
        MemoryTier.SEMANTIC,
        session_id="sess_B",
        category="user_profile",
        key="sem_b",
        account_id="acct_B",
        thread_id="thr_B",
    )
    results = mm.get_semantic(domain="user_profile", account_id="acct_B", thread_id="thr_B")
    assert len(results) == 1
    assert results[0].key == "sem_b"


def test_dedup_isolated_by_identity_scope(mm: MemoryManager) -> None:
    shared = {"data": "same_text"}
    rid_a = _stage_promote(
        mm,
        MemoryTier.EPISODIC,
        session_id="sess_A",
        category="captured_memory",
        key="cap_a",
        value=shared,
        account_id="acct_A",
        thread_id="thr_A",
        role="devops",
    )
    rid_b = _stage_promote(
        mm,
        MemoryTier.EPISODIC,
        session_id="sess_B",
        category="captured_memory",
        key="cap_b",
        value=shared,
        account_id="acct_B",
        thread_id="thr_B",
        role="research",
    )

    assert rid_a != rid_b
    acct_a = mm.get_episodic(category="captured_memory", account_id="acct_A", thread_id="thr_A")
    acct_b = mm.get_episodic(category="captured_memory", account_id="acct_B", thread_id="thr_B")
    assert len(acct_a) == 1
    assert len(acct_b) == 1
    assert acct_a[0].source["role"] == "devops"
    assert acct_b[0].source["role"] == "research"
