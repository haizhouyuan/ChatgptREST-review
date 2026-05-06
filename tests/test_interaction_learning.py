from __future__ import annotations

from chatgptrest.advisor.interaction_learning import (
    extract_user_correction_signals,
    load_interaction_learning,
    record_interaction_learning,
)
from chatgptrest.kernel.memory_manager import MemoryManager


def test_extract_user_correction_signals_detects_codex_grade_task_closure() -> None:
    payload = extract_user_correction_signals(
        "我的意思不是让你帮我整理输入，我会直接发原话。要高质量，还要提高到Codex的高度，最终落实成任务闭环。"
    )

    assert payload is not None
    assert payload["raw_ingress_mode"] == "preserve_user_wording"
    assert payload["quality_bar"] == "codex_grade"
    assert payload["preferred_executor_family"] == "codex"
    assert payload["closure_style"] == "task_closure"


def test_record_interaction_learning_persists_thread_scoped_preferences(tmp_path) -> None:
    memory = MemoryManager(str(tmp_path / "memory.db"))

    recorded = record_interaction_learning(
        memory,
        account_id="acct-1",
        thread_id="thread-1",
        session_id="sess-1",
        agent_id="openclawbot",
        role_id="planning",
        project_id="",
        learning_payload={
            "raw_ingress_mode": "preserve_user_wording",
            "closure_style": "task_closure",
            "preferred_executor_family": "codex",
        },
    )
    loaded = load_interaction_learning(memory, account_id="acct-1", thread_id="thread-1")

    assert recorded is not None
    assert loaded is not None
    assert loaded["raw_ingress_mode"] == "preserve_user_wording"
    assert loaded["closure_style"] == "task_closure"
    assert loaded["preferred_executor_family"] == "codex"


def test_extract_user_correction_signals_detects_brevity_focus_and_reply_first() -> None:
    payload = extract_user_correction_signals("太长了，重点不对，先告诉我怎么回对方。")

    assert payload is not None
    assert payload["brevity_preference"] == "short"
    assert payload["focus_preference"] == "tighten_focus"
    assert payload["reply_first_preference"] == "reply_first"


def test_extract_user_correction_signals_does_not_trigger_for_normal_statement() -> None:
    payload = extract_user_correction_signals("明天我会去开会，顺便看一下产线情况。")

    assert payload is None


def test_record_interaction_learning_uses_counts_to_resolve_conflicts(tmp_path) -> None:
    memory = MemoryManager(str(tmp_path / "memory.db"))

    record_interaction_learning(
        memory,
        account_id="acct-1",
        thread_id="thread-1",
        session_id="sess-1",
        agent_id="openclawbot",
        role_id="planning",
        project_id="",
        learning_payload={"brevity_preference": "short", "source_message": "太长了"},
    )
    record_interaction_learning(
        memory,
        account_id="acct-1",
        thread_id="thread-1",
        session_id="sess-2",
        agent_id="openclawbot",
        role_id="planning",
        project_id="",
        learning_payload={"brevity_preference": "short", "source_message": "还是太长了"},
    )
    loaded = record_interaction_learning(
        memory,
        account_id="acct-1",
        thread_id="thread-1",
        session_id="sess-3",
        agent_id="openclawbot",
        role_id="planning",
        project_id="",
        learning_payload={"brevity_preference": "detailed", "source_message": "这次展开一点"},
    )

    assert loaded is not None
    assert loaded["brevity_preference"] == "short"
