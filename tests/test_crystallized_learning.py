from __future__ import annotations

from chatgptrest.advisor.crystallized_learning import (
    CRYSTALLIZED_LEARNING_PROJECTION_MODE,
    INTERACTION_LEARNING_MIN_SUPPORT,
    build_interaction_learning_crystal,
    crystallized_learning_receipt,
)
from chatgptrest.advisor.interaction_learning import load_interaction_learning, record_interaction_learning
from chatgptrest.kernel.memory_manager import MemoryManager


def test_build_interaction_learning_crystal_returns_none_for_empty_payload() -> None:
    assert build_interaction_learning_crystal(None) is None


def test_build_interaction_learning_crystal_requires_support_threshold() -> None:
    crystal = build_interaction_learning_crystal(
        {
            "record_id": "rec-1",
            "key": "user_correction:acct-1:thread-1",
            "account_id": "acct-1",
            "thread_id": "thread-1",
            "preferred_executor_family": "codex",
            "_preference_meta": {
                "preferred_executor_family": {
                    "counts": {"codex": 1},
                    "last_source_message": "还要提高到codex",
                }
            },
        }
    )

    assert crystal is None


def test_build_interaction_learning_crystal_emits_shadow_governance_receipt() -> None:
    crystal = build_interaction_learning_crystal(
        {
            "record_id": "rec-1",
            "key": "user_correction:acct-1:thread-1",
            "account_id": "acct-1",
            "thread_id": "thread-1",
            "preferred_executor_family": "codex",
            "_preference_meta": {
                "preferred_executor_family": {
                    "counts": {"codex": 2, "claude": 1},
                    "last_source_message": "继续按codex标准",
                }
            },
        }
    )

    assert crystal is not None
    assert crystal["support_threshold"] == INTERACTION_LEARNING_MIN_SUPPORT
    assert crystal["governance"]["projection_mode"] == CRYSTALLIZED_LEARNING_PROJECTION_MODE
    assert "preferred_executor_family" in crystal["governance"]["allowlist"]
    receipt = crystallized_learning_receipt(crystal)
    assert receipt["applied"] is True
    assert receipt["projection_mode"] == CRYSTALLIZED_LEARNING_PROJECTION_MODE
    assert receipt["shadow_required"] is True
    assert receipt["stable_preference_keys"] == ["preferred_executor_family"]


def test_build_interaction_learning_crystal_supports_invalidation_via_newer_winner(tmp_path) -> None:
    memory = MemoryManager(str(tmp_path / "memory.db"))

    record_interaction_learning(
        memory,
        account_id="acct-1",
        thread_id="thread-1",
        session_id="sess-1",
        agent_id="advisor",
        role_id="planning",
        project_id="prj-beta",
        learning_payload={"preferred_executor_family": "codex", "source_message": "提高到codex"},
    )
    record_interaction_learning(
        memory,
        account_id="acct-1",
        thread_id="thread-1",
        session_id="sess-2",
        agent_id="advisor",
        role_id="planning",
        project_id="prj-beta",
        learning_payload={"preferred_executor_family": "codex", "source_message": "继续按codex标准"},
    )
    first = load_interaction_learning(memory, account_id="acct-1", thread_id="thread-1")
    first_crystal = build_interaction_learning_crystal(first)

    record_interaction_learning(
        memory,
        account_id="acct-1",
        thread_id="thread-1",
        session_id="sess-3",
        agent_id="advisor",
        role_id="planning",
        project_id="prj-beta",
        learning_payload={"preferred_executor_family": "claude", "source_message": "这次改成claude"},
    )
    record_interaction_learning(
        memory,
        account_id="acct-1",
        thread_id="thread-1",
        session_id="sess-4",
        agent_id="advisor",
        role_id="planning",
        project_id="prj-beta",
        learning_payload={"preferred_executor_family": "claude", "source_message": "继续按claude来"},
    )
    record_interaction_learning(
        memory,
        account_id="acct-1",
        thread_id="thread-1",
        session_id="sess-5",
        agent_id="advisor",
        role_id="planning",
        project_id="prj-beta",
        learning_payload={"preferred_executor_family": "claude", "source_message": "claude优先"},
    )
    second = load_interaction_learning(memory, account_id="acct-1", thread_id="thread-1")
    second_crystal = build_interaction_learning_crystal(second)

    assert first_crystal is not None
    assert first_crystal["stable_preferences"]["preferred_executor_family"] == "codex"
    assert second_crystal is not None
    assert second_crystal["stable_preferences"]["preferred_executor_family"] == "claude"
    assert first_crystal["crystal_id"] != second_crystal["crystal_id"]
    assert second_crystal["invalidation"]["key"] == first_crystal["invalidation"]["key"]
    assert second_crystal["supersession"]["superseded_count"] == 1
    assert second_crystal["supersession"]["superseded_preferences"][0]["value"] == "codex"
