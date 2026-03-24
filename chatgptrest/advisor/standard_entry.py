"""Standard Entry Adapter — normalizes all task entry points.

Ensures that tasks submitted via Codex, MCP, or other non-Feishu channels
go through the same intent-recognition and validation pipeline as tasks
from the Feishu gateway.

The adapter wraps raw requests into the standard funnel format, performs
preset recommendation, and skill pre-check before passing to dispatch.

Part of the system-optimization-20260316 feature set.
"""

from __future__ import annotations

import logging
import uuid
import time
from dataclasses import dataclass, field
from typing import Any

from chatgptrest.advisor.scenario_packs import (
    apply_scenario_pack,
    resolve_scenario_pack,
    summarize_scenario_pack,
)
from chatgptrest.advisor.task_intake import TaskIntakeSpec, build_task_intake_spec, summarize_task_intake

logger = logging.getLogger(__name__)


@dataclass
class StandardRequest:
    """Normalized task request from any entry point."""

    question: str
    source: str  # "feishu", "codex", "mcp", "api", "direct"
    trace_id: str = ""
    target_agent: str = "main"
    preset: str = "auto"
    file_paths: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    task_intake: TaskIntakeSpec | None = None

    def __post_init__(self) -> None:
        if not self.trace_id:
            self.trace_id = str(uuid.uuid4())


def normalize_request(
    question: str,
    *,
    source: str = "unknown",
    target_agent: str = "main",
    preset: str = "auto",
    file_paths: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> StandardRequest:
    """Create a normalized StandardRequest from raw input."""
    request_metadata = dict(metadata or {})
    request_trace_id = str(request_metadata.get("trace_id") or "").strip() or str(uuid.uuid4())
    raw_task_intake = request_metadata.pop("task_intake", None)
    request = StandardRequest(
        question=question,
        source=source,
        trace_id=request_trace_id,
        target_agent=target_agent,
        preset=preset,
        file_paths=file_paths or [],
        metadata=request_metadata,
    )
    request.task_intake = build_task_intake_spec(
        ingress_lane="other",
        default_source=_default_source_for_standard_entry(source),
        raw_source=source,
        raw_task_intake=raw_task_intake if isinstance(raw_task_intake, dict) else None,
        question=question,
        goal_hint=str(request_metadata.get("goal_hint") or "").strip(),
        intent_hint=str(request_metadata.get("intent_hint") or "").strip(),
        trace_id=request.trace_id,
        session_id=str(request_metadata.get("session_id") or "").strip(),
        user_id=str(request_metadata.get("user_id") or "").strip(),
        account_id=str(request_metadata.get("account_id") or "").strip(),
        thread_id=str(request_metadata.get("thread_id") or "").strip(),
        agent_id=str(request_metadata.get("agent_id") or "").strip(),
        role_id=str(request_metadata.get("role_id") or "").strip(),
        context=request_metadata,
        attachments=request.file_paths,
        client_name=str(request_metadata.get("client_name") or "").strip(),
    )
    return request


def standard_entry_pipeline(
    request: StandardRequest,
) -> dict[str, Any]:
    """Run a task request through the standard pipeline.

    This ensures ANY entry point (Feishu, Codex, MCP, direct API)
    goes through the same flow:

    1. Preset Recommendation — suggest optimal model/preset
    2. Skill Pre-check — verify agent has required skills
    3. Quality Gate — validate request quality
    4. Return dispatch-ready package

    Returns a dict with pipeline results and recommendations.
    """
    result: dict[str, Any] = {
        "trace_id": request.trace_id,
        "source": request.source,
        "timestamp": time.time(),
        "steps": {},
        "ready_to_dispatch": False,
    }
    if request.task_intake is not None:
        scenario_pack = resolve_scenario_pack(
            request.task_intake,
            goal_hint=str(request.task_intake.goal_hint or ""),
            context=request.task_intake.context,
        )
        if scenario_pack is not None:
            request.task_intake = apply_scenario_pack(request.task_intake, scenario_pack)
            result["scenario_pack"] = summarize_scenario_pack(scenario_pack)
        result["task_intake"] = request.task_intake.to_dict()
        result["task_intake_summary"] = summarize_task_intake(request.task_intake)

    # --- Step 1: Preset Recommendation ---
    try:
        from chatgptrest.advisor.preset_recommender import (
            recommend_preset,
            validate_preset_choice,
        )

        recommendation = recommend_preset(
            request.question,
            has_files=bool(request.file_paths),
            task_intake=request.task_intake.to_dict() if request.task_intake else None,
            scenario_pack=result.get("scenario_pack"),
        )
        result["steps"]["preset_recommendation"] = recommendation.to_dict()

        # If user chose a specific preset, validate it.
        if request.preset != "auto":
            validation = validate_preset_choice(
                request.question,
                request.preset,
                task_intake=request.task_intake.to_dict() if request.task_intake else None,
                scenario_pack=result.get("scenario_pack"),
            )
            result["steps"]["preset_validation"] = validation
            if not validation["ok"]:
                result["steps"]["preset_warnings"] = validation["warnings"]
                # BUG FIX (Gemini code review 2026-03-17):
                # Previously only warned but didn't enforce — expensive presets
                # still flowed to the Web queue. Now force-downgrade.
                recommended_preset = validation.get("recommended", {}).get("preset")
                if recommended_preset:
                    logger.info(
                        "Preset guard: %s → %s (forced downgrade)",
                        request.preset,
                        recommended_preset,
                    )
                    request.preset = recommended_preset
                    result["applied_preset"] = recommended_preset
        else:
            # Auto mode: use the recommended preset
            request.preset = recommendation.preset
            result["applied_preset"] = recommendation.preset
            result["applied_provider"] = recommendation.provider
    except Exception as e:
        logger.warning("Preset recommender failed: %s", e)
        result["steps"]["preset_recommendation"] = {"error": str(e)}

    # --- Step 2: Skill Pre-check ---
    try:
        from chatgptrest.advisor.skill_registry import (
            check_skill_readiness,
            classify_task_type,
        )

        # Build a minimal project card from the question.
        project_card = {
            "title": request.question[:100],
            "description": request.question,
        }
        task_type = classify_task_type(project_card)
        skill_check = check_skill_readiness(
            agent_id=request.target_agent,
            project_card=project_card,
        )

        result["steps"]["skill_check"] = skill_check.to_dict()
        result["steps"]["task_type"] = task_type

        if not skill_check.passed:
            result["skill_gap"] = True
            result["suggested_agent"] = skill_check.suggested_agent
            if skill_check.suggested_agent:
                logger.info(
                    "Route change: %s → %s (skill gap)",
                    request.target_agent,
                    skill_check.suggested_agent,
                )
                request.target_agent = skill_check.suggested_agent
                result["applied_agent"] = skill_check.suggested_agent
    except Exception as e:
        logger.warning("Skill check failed: %s", e)
        result["steps"]["skill_check"] = {"error": str(e)}

    # --- Step 3: Quality Gate ---
    quality_issues: list[str] = []

    if len(request.question.strip()) < 10:
        quality_issues.append("Question too short (<10 chars)")

    if len(request.question) > 50000:
        quality_issues.append("Question extremely long (>50K chars) — consider splitting")

    if quality_issues:
        result["steps"]["quality_gate"] = {
            "passed": False,
            "issues": quality_issues,
        }
    else:
        result["steps"]["quality_gate"] = {"passed": True}

    # --- Final: Mark as ready ---
    result["ready_to_dispatch"] = (
        not quality_issues
        and result["steps"].get("skill_check", {}).get("passed", True)
    )

    result["dispatch_params"] = {
        "question": request.question,
        "preset": request.preset,
        "target_agent": request.target_agent,
        "file_paths": request.file_paths,
        "source": request.source,
        "trace_id": request.trace_id,
    }
    if request.task_intake is not None:
        result["dispatch_params"]["task_intake"] = request.task_intake.to_dict()
    if "scenario_pack" in result:
        result["dispatch_params"]["scenario_pack"] = result["scenario_pack"]

    return result


def process_codex_request(
    question: str,
    *,
    target_agent: str = "main",
    preset: str = "auto",
    file_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Convenience wrapper for Codex-originated requests.

    Ensures Codex requests go through the same pipeline as Feishu tasks.

    Example::

        result = process_codex_request(
            "研究中国两轮电动车市场",
            target_agent="research",
        )
        if result["ready_to_dispatch"]:
            # Proceed with dispatch
            ...
    """
    req = normalize_request(
        question,
        source="codex",
        target_agent=target_agent,
        preset=preset,
        file_paths=file_paths,
    )
    return standard_entry_pipeline(req)


def process_mcp_request(
    question: str,
    *,
    target_agent: str = "main",
    preset: str = "auto",
    file_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Convenience wrapper for MCP-originated requests."""
    req = normalize_request(
        question,
        source="mcp",
        target_agent=target_agent,
        preset=preset,
        file_paths=file_paths,
    )
    return standard_entry_pipeline(req)


def _default_source_for_standard_entry(source: str) -> str:
    legacy = str(source or "").strip().lower()
    if legacy == "codex":
        return "cli"
    if legacy == "api":
        return "rest"
    if legacy == "direct":
        return "unknown"
    return legacy or "unknown"
