from __future__ import annotations

from chatgptrest.worker.worker import (
    _current_answer_matches_pre_match_assistant,
    _should_downgrade_when_export_missing_reply,
)


def test_export_missing_reply_downgrades_on_empty_answer() -> None:
    should, info = _should_downgrade_when_export_missing_reply(current_answer="", min_chars_required=0)
    assert should is True
    assert info.get("reason") == "empty_answer"


def test_export_missing_reply_downgrades_when_answer_below_threshold() -> None:
    should, info = _should_downgrade_when_export_missing_reply(current_answer="a" * 100, min_chars_required=0)
    assert should is True
    assert info.get("reason") == "answer_below_threshold"
    assert int(info.get("threshold") or 0) >= 200


def test_export_missing_reply_does_not_downgrade_for_substantial_answer() -> None:
    should, info = _should_downgrade_when_export_missing_reply(current_answer="a" * 250, min_chars_required=0)
    assert should is False
    assert info.get("reason") == "answer_sufficient"


def test_export_missing_reply_respects_min_chars_threshold() -> None:
    should, info = _should_downgrade_when_export_missing_reply(current_answer="a" * 500, min_chars_required=800)
    assert should is True
    assert info.get("threshold") == 800


def test_export_missing_reply_accepts_answer_above_min_chars_threshold() -> None:
    should, info = _should_downgrade_when_export_missing_reply(current_answer="a" * 1000, min_chars_required=800)
    assert should is False
    assert info.get("threshold") == 800


def test_export_missing_reply_downgrades_thinking_job_with_current_assistant_in_progress() -> None:
    current_answer = (
        "## 1. 总判断\n\n"
        "这套计划最大的问题不是缺少流程，而是缺少能约束执行优先级的证据闭环。\n\n"
        "## 2. 执行边界\n\n"
        "先固定 Labebe 交付路径，再把治理能力作为问题触发后的补充机制。"
        * 20
    )
    should, info = _should_downgrade_when_export_missing_reply(
        current_answer=current_answer,
        question_text="请给出完整顾问备忘录。",
        min_chars_required=800,
        thinking_preset_requested=True,
        export_guard_info={
            "answer_source": "matched_but_missing_assistant",
            "export_has_in_progress": True,
            "thread_contaminated_after_match": False,
            "next_role_after_match": "assistant",
            "subsequent_user_turn_count": 0,
        },
    )
    assert should is True
    assert info.get("reason") == "matched_assistant_still_in_progress"
    assert info.get("current_answer_quality") == "final"


def test_export_missing_reply_keeps_legacy_lag_policy_for_non_thinking_answer() -> None:
    should, info = _should_downgrade_when_export_missing_reply(
        current_answer="a" * 1000,
        min_chars_required=800,
        thinking_preset_requested=False,
        deep_research_requested=False,
        export_guard_info={
            "answer_source": "matched_but_missing_assistant",
            "export_has_in_progress": True,
            "thread_contaminated_after_match": False,
            "next_role_after_match": "assistant",
            "subsequent_user_turn_count": 0,
        },
    )
    assert should is False
    assert info.get("reason") == "answer_sufficient"


def test_export_missing_reply_fails_closed_when_thread_contaminated() -> None:
    should, info = _should_downgrade_when_export_missing_reply(
        current_answer="a" * 5000,
        min_chars_required=0,
        export_guard_info={
            "thread_contaminated_after_match": True,
            "next_role_after_match": "user",
            "subsequent_user_turn_count": 1,
        },
    )
    assert should is True
    assert info.get("reason") == "thread_contaminated_by_subsequent_user_turn"
    assert info.get("terminal_action") == "needs_followup"


def test_export_missing_reply_fails_closed_for_prompt_echo_during_in_progress_partial() -> None:
    question = (
        "## Implementation Objective\n"
        "做2026年Q1绩效总结，工作总结梳理。先读取并检查用户提供的材料。\n\n"
        "## Available Inputs\n"
        "- 文件A\n- 文件B\n\n"
        "## Output Contract\n"
        "{...}\n\n"
        "## Evidence Requirements\n"
        "{...}\n\n"
        "## Scenario Pack\n"
        "{...}\n"
        "\n## Review Rubric\n"
        "- 先按模块梳理，再指出缺口与下一步。\n"
        "- 不要直接生成考核表。\n"
    )
    should, info = _should_downgrade_when_export_missing_reply(
        current_answer=question,
        question_text=question,
        min_chars_required=0,
        export_guard_info={
            "answer_source": "matched_in_progress_partial",
            "thread_contaminated_after_match": False,
            "next_role_after_match": "assistant",
            "subsequent_user_turn_count": 0,
        },
    )
    assert should is True
    assert info.get("reason") == "matched_in_progress_partial_prompt_echo"
    assert info.get("prompt_echo_match") in {"exact", "compiled_prompt_scaffold", "long_common_prefix"}


def test_export_missing_reply_allows_real_answer_when_export_lagging() -> None:
    question = "请基于材料输出Q1工作总结模块、事项、缺口和下一步。"
    current_answer = (
        "## 建议模块\n"
        "1. 主营业务推进\n"
        "2. 增量业务与客户拓展\n"
        "3. 组织协同与汇报\n\n"
        "## 初步事项\n"
        "- 已从周报提取 3 月与 4 月初的关键事项。\n"
        "- 两份往年绩效表可作为结构参考，但不应直接套用。\n\n"
        "## 缺口\n"
        "- 1-2 月材料仍偏少，需要补会议纪要或相关输出物。\n"
        "\n## 下一步\n"
        "- 先补齐 1-2 月材料，再映射到绩效表字段。\n"
        "- 第二轮再把 planning 库内相关材料并入，以形成正式绩效稿。\n"
    )
    should, info = _should_downgrade_when_export_missing_reply(
        current_answer=current_answer,
        question_text=question,
        min_chars_required=0,
        export_guard_info={
            "answer_source": "matched_in_progress_partial",
            "thread_contaminated_after_match": False,
            "next_role_after_match": "assistant",
            "subsequent_user_turn_count": 0,
        },
    )
    assert should is False
    assert info.get("reason") == "answer_sufficient"


def test_detects_current_answer_from_pre_match_assistant_turn() -> None:
    previous_answer = (
        "## Executive Judgment\n\n"
        "The earlier review concluded that the control plane needs a manifest, policy checker, "
        "and audit ledger before any autonomous worker advancement. The point was not to add "
        "more prose review, but to compile the sidecar rules into machine-checkable gates.\n\n"
        "## Required Changes\n\n"
        "- Freeze runtime capability metadata.\n"
        "- Fail closed when the board state cannot be reconciled.\n"
        "- Record degraded reviewer independence instead of silently passing.\n"
    )
    export_obj = {
        "messages": [
            {"role": "user", "text": "Old question"},
            {"role": "assistant", "text": previous_answer},
            {"role": "user", "text": "Current follow-up question"},
            {"role": "assistant", "text": "I am checking the packet now."},
        ]
    }

    matched, info = _current_answer_matches_pre_match_assistant(
        current_answer=previous_answer,
        export_obj=export_obj,
        matched_user_index=2,
        question_text="Current follow-up question",
    )

    assert matched is True
    assert info.get("current_answer_matches_pre_match_assistant") is True
    assert info.get("pre_match_assistant_match_kind") == "exact"
    assert info.get("pre_match_assistant_index") == 1


def test_export_missing_reply_fails_closed_when_dom_answer_is_previous_assistant() -> None:
    current_answer = (
        "## Findings\n\n"
        "The previous round already found that issue creation is not autonomy. A robust "
        "control plane needs explicit readiness gates, no-op success semantics, and a "
        "separate transition checker before any worker is launched.\n\n"
        "## Recommendation\n\n"
        "Keep write actuators blocked until the manifest and policy checks are green.\n"
    )
    should, info = _should_downgrade_when_export_missing_reply(
        current_answer=current_answer,
        question_text="Please analyze the new follow-up packet.",
        min_chars_required=0,
        export_guard_info={
            "answer_source": "matched_in_progress_partial",
            "thread_contaminated_after_match": False,
            "next_role_after_match": "assistant",
            "subsequent_user_turn_count": 0,
            "current_answer_matches_pre_match_assistant": True,
            "pre_match_assistant_match_kind": "exact",
            "pre_match_assistant_index": 3,
        },
    )

    assert should is True
    assert info.get("reason") == "matched_in_progress_partial_current_answer_is_previous_assistant"
    assert info.get("pre_match_assistant_match_kind") == "exact"
