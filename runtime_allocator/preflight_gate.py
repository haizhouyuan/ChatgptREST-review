"""PreflightGate — fail-closed safety checks BEFORE agent execution.

Rules (evaluated in order, first block wins):
1. read_only + write request → blocked
2. model lane mismatch → blocked
3. code-modifying task without git diff check → blocked
4. high-risk memory write without review → human_review_required
5. unknown task_type → human_review_required
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional

from runtime_allocator.contracts import (
    BaseGateResult,
    GateStatus,
    PreflightResult,
    WriteScope,
)
from runtime_allocator.policy_store import get_policy


# Task-type → default write scope mapping
_TASK_WRITE_SCOPE: dict[str, WriteScope] = {
    # Finbot
    "finbot_trade_proposal": WriteScope.READ_ONLY,
    "finbot_fundamental": WriteScope.READ_ONLY,
    "finbot_technical": WriteScope.READ_ONLY,
    "finbot_debate": WriteScope.READ_ONLY,
    "finbot_risk_veto": WriteScope.READ_ONLY,
    "finbot_market_analysis": WriteScope.READ_ONLY,
    "finbot_news_summary": WriteScope.READ_ONLY,
    # Planning
    "strategy_brief": WriteScope.READ_ONLY,
    "strategic_plan": WriteScope.READ_ONLY,
    "planning_strategy": WriteScope.READ_ONLY,
    "hr_sensitive": WriteScope.READ_ONLY,
    "hr_sensitive_review": WriteScope.READ_ONLY,
    "meeting_summary": WriteScope.READ_ONLY,
    "meeting_extraction": WriteScope.READ_ONLY,
    "document_draft": WriteScope.MUTATE,
    "decision_memo": WriteScope.APPEND_ONLY,
    # Labebe
    "labebe_product_eval": WriteScope.READ_ONLY,
    "labebe_content_gen": WriteScope.MUTATE,
    "labebe_review_analysis": WriteScope.READ_ONLY,
    "labebe_commerce_decision": WriteScope.READ_ONLY,
    "labebe_evidence_bundle": WriteScope.APPEND_ONLY,
    "dtc_copy": WriteScope.MUTATE,
    "boss_gallery_card": WriteScope.MUTATE,
    # Memory
    "memory_indexing": WriteScope.MUTATE,
    "memory_benchmark": WriteScope.READ_ONLY,
    "memory_comparison": WriteScope.READ_ONLY,
    "memory_recommendation": WriteScope.READ_ONLY,
    "memory_system_eval": WriteScope.READ_ONLY,
    # LLM Research
    "llm_research_eval": WriteScope.READ_ONLY,
    "llm_research_benchmark": WriteScope.READ_ONLY,
    "model_download": WriteScope.MUTATE,
    "local_model_benchmark": WriteScope.READ_ONLY,
    # General
    "frontend": WriteScope.MUTATE,
    "code_reasoning": WriteScope.READ_ONLY,
    "benchmark": WriteScope.READ_ONLY,
}

# Tasks that mutate code and MUST have a git diff checkpoint
_CODE_MUTATING_TASKS = {
    "frontend",
    "dtc_copy",
    "boss_gallery_card",
    "document_draft",
}


def _has_git_diff(repo_path: Optional[str] = None) -> bool:
    """Check if there are uncommitted changes in the repo."""
    cwd = repo_path or os.getcwd()
    try:
        result = subprocess.run(
            ["git", "diff", "--quiet"],
            cwd=cwd,
            capture_output=True,
            timeout=10,
        )
        # Return True if there IS a diff (exit code 1 means diff exists)
        return result.returncode == 1
    except Exception:
        return False


def preflight(
    task_prompt: str,
    agent_slug: str,
    task_type: str,
    model_lane: str = "",
    declared_write_scope: Optional[WriteScope] = None,
    repo_path: Optional[str] = None,
    require_git_diff_for_code: bool = True,
) -> PreflightResult:
    """Run fail-closed preflight checks.

    Args:
        task_prompt: The raw task prompt text.
        agent_slug: Identifier for the agent/orchestrator.
        task_type: Task class key (e.g. "dtc_copy").
        model_lane: Expected model lane (e.g. "critical", "high", "standard").
        declared_write_scope: Scope declared by caller. If None, inferred from task_type.
        repo_path: Path to git repo for diff check.
        require_git_diff_for_code: If True, code-mutating tasks need git diff present.
    """
    reason_codes: list[str] = []

    # 1. Resolve write scope
    inferred_scope = _TASK_WRITE_SCOPE.get(task_type, WriteScope.READ_ONLY)
    effective_scope = declared_write_scope or inferred_scope

    # 2. Rule: read_only task requesting write → blocked
    if inferred_scope == WriteScope.READ_ONLY and declared_write_scope in (
        WriteScope.MUTATE,
        WriteScope.APPEND_ONLY,
    ):
        return PreflightResult(
            status=GateStatus.BLOCKED,
            reason_codes=["read_only_violation", f"task={task_type}"],
            detail=f"Task {task_type} is read-only but caller declared {declared_write_scope.value}",
            agent_slug=agent_slug,
            task_type=task_type,
            model_lane=model_lane,
            write_scope=effective_scope,
        )

    # 3. Rule: model lane mismatch
    policy = get_policy(task_type)
    if policy and model_lane:
        # Map task_type to expected quality tier
        from runtime_allocator.allocator_mvp import _TASK_QUALITY, QualityTier

        task_quality = _TASK_QUALITY.get(task_type)
        if task_quality:
            expected_lane = task_quality.value
            if model_lane != expected_lane:
                return PreflightResult(
                    status=GateStatus.BLOCKED,
                    reason_codes=[
                        "model_lane_mismatch",
                        f"expected={expected_lane}",
                        f"got={model_lane}",
                    ],
                    detail=f"Task {task_type} requires lane {expected_lane}, got {model_lane}",
                    agent_slug=agent_slug,
                    task_type=task_type,
                    model_lane=model_lane,
                    write_scope=effective_scope,
                )

    # 4. Rule: code-modifying task without git diff
    git_diff_present = _has_git_diff(repo_path)
    if require_git_diff_for_code and task_type in _CODE_MUTATING_TASKS:
        if not git_diff_present:
            return PreflightResult(
                status=GateStatus.BLOCKED,
                reason_codes=[
                    "no_git_diff_checkpoint",
                    f"task={task_type}",
                ],
                detail=f"Code-mutating task {task_type} requires git diff checkpoint before execution",
                agent_slug=agent_slug,
                task_type=task_type,
                model_lane=model_lane,
                write_scope=effective_scope,
                requires_git_diff=True,
                git_diff_present=False,
            )

    # 5. Rule: high-risk memory write without review
    if task_type.startswith("memory_") and effective_scope in (
        WriteScope.MUTATE,
        WriteScope.APPEND_ONLY,
    ):
        return PreflightResult(
            status=GateStatus.HUMAN_REVIEW_REQUIRED,
            reason_codes=["high_risk_memory_write", f"task={task_type}"],
            detail=f"Memory-mutating task {task_type} requires human review before commit",
            agent_slug=agent_slug,
            task_type=task_type,
            model_lane=model_lane,
            write_scope=effective_scope,
        )

    # 6. Rule: unknown task_type
    if policy is None and task_type not in _TASK_WRITE_SCOPE:
        return PreflightResult(
            status=GateStatus.HUMAN_REVIEW_REQUIRED,
            reason_codes=["unknown_task_type", f"task={task_type}"],
            detail=f"Unknown task type {task_type}: no policy or write scope defined",
            agent_slug=agent_slug,
            task_type=task_type,
            model_lane=model_lane,
            write_scope=effective_scope,
        )

    # All checks passed
    return PreflightResult(
        status=GateStatus.ALLOWED,
        reason_codes=["preflight_passed"],
        detail="All preflight checks passed",
        agent_slug=agent_slug,
        task_type=task_type,
        model_lane=model_lane,
        write_scope=effective_scope,
        requires_git_diff=require_git_diff_for_code and task_type in _CODE_MUTATING_TASKS,
        git_diff_present=git_diff_present,
    )
