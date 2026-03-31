"""Skill registry compatibility layer backed by the canonical platform registry."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from chatgptrest.kernel.skill_manager import (
    ResolutionResult,
    get_bundle_resolver,
    get_canonical_registry,
)

logger = logging.getLogger(__name__)


def _registry():
    return get_canonical_registry()


class _RegistryBackedMapping(Mapping[str, Any]):
    """Compatibility mapping that always reflects the canonical registry."""

    def __init__(self, loader):
        self._loader = loader

    def _snapshot(self) -> dict[str, Any]:
        return dict(self._loader())

    def __getitem__(self, key: str) -> Any:
        return self._snapshot()[key]

    def __iter__(self):
        return iter(self._snapshot())

    def __len__(self) -> int:
        return len(self._snapshot())

    def get(self, key: str, default: Any = None) -> Any:
        return self._snapshot().get(key, default)


@dataclass
class AgentSkillProfile:
    """Compatibility profile for tests and legacy call sites.

    `skills` is intentionally kept as a set of capability IDs rather than
    skill package IDs, matching the legacy `check_skill_readiness()` contract.
    """

    agent_id: str
    skills: set[str] = field(default_factory=set)
    max_concurrent_tasks: int = 1
    preferred_model: str = "auto"

    def has_skill(self, skill_id: str) -> bool:
        return skill_id in self.skills

    def has_all_skills(self, required: list[str]) -> bool:
        return all(s in self.skills for s in required)

    def missing_skills(self, required: list[str]) -> list[str]:
        return [s for s in required if s not in self.skills]


def _build_default_agent_profiles() -> dict[str, AgentSkillProfile]:
    registry = _registry()
    profiles: dict[str, AgentSkillProfile] = {}
    for agent_id, profile in registry.agent_profiles.items():
        capabilities = set(
            registry.available_capabilities_for_bundles(profile.default_bundles, platform=profile.platform)
        )
        profiles[agent_id] = AgentSkillProfile(
            agent_id=agent_id,
            skills=capabilities,
            preferred_model=profile.preferred_model,
        )
    return profiles


SKILL_CATALOG: Mapping[str, str] = _RegistryBackedMapping(lambda: _registry().capability_catalog())
TASK_SKILL_REQUIREMENTS: Mapping[str, list[str]] = _RegistryBackedMapping(
    lambda: _registry().task_profile_requirements()
)
DEFAULT_AGENT_PROFILES: Mapping[str, AgentSkillProfile] = _RegistryBackedMapping(_build_default_agent_profiles)


@dataclass
class SkillCheckResult:
    """Result of a skill/bundle resolver check."""

    passed: bool
    status: str
    agent_id: str
    task_type: str
    required_skills: list[str]
    missing_skills: list[str]
    suggested_agent: str | None = None
    message: str = ""
    recommended_skills: list[str] = field(default_factory=list)
    recommended_bundles: list[str] = field(default_factory=list)
    unmet_capabilities: list[dict[str, Any]] = field(default_factory=list)
    decision_reasons: list[str] = field(default_factory=list)
    fallback_plan: list[dict[str, Any]] = field(default_factory=list)
    registry_authority: dict[str, Any] = field(default_factory=dict)
    platform: str = "openclaw"

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "status": self.status,
            "agent_id": self.agent_id,
            "task_type": self.task_type,
            "required_skills": self.required_skills,
            "missing_skills": self.missing_skills,
            "suggested_agent": self.suggested_agent,
            "message": self.message,
            "recommended_skills": list(self.recommended_skills),
            "recommended_bundles": list(self.recommended_bundles),
            "unmet_capabilities": list(self.unmet_capabilities),
            "decision_reasons": list(self.decision_reasons),
            "fallback_plan": list(self.fallback_plan),
            "registry_authority": dict(self.registry_authority),
            "platform": self.platform,
        }


def classify_task_type(project_card: dict[str, Any]) -> str:
    title = (project_card.get("title", "") or "").lower()
    desc = (project_card.get("description", "") or "").lower()
    plan = (project_card.get("execution_plan", "") or "").lower()
    combined = f"{title} {desc} {plan}"

    if any(kw in combined for kw in ["市场", "market", "调研", "品牌", "行业"]):
        return "market_research"
    if any(kw in combined for kw in ["投资", "股票", "invest", "stock", "valuation"]):
        return "investment_research"
    if any(kw in combined for kw in ["deep research", "深度研究", "deep_research"]):
        return "deep_research"
    if any(kw in combined for kw in ["review", "审查", "code review", "代码审查"]):
        return "code_review"
    if any(kw in combined for kw in ["develop", "implement", "开发", "实现", "refactor"]):
        return "code_development"
    if any(kw in combined for kw in ["分析", "analysis", "data", "数据"]):
        return "data_analysis"
    if any(kw in combined for kw in ["ops", "运维", "monitor", "deploy"]):
        return "ops_maintenance"
    return "general"


def find_best_agent(
    task_type: str,
    profiles: dict[str, AgentSkillProfile] | None = None,
    *,
    platform: str = "openclaw",
) -> str | None:
    if profiles is not None:
        required = TASK_SKILL_REQUIREMENTS.get(task_type, ["document_writing"])
        best_agent: str | None = None
        best_score = -1
        for agent_id, profile in profiles.items():
            if profile.has_all_skills(required):
                score = sum(1 for skill_id in required if skill_id in profile.skills)
                if score > best_score:
                    best_score = score
                    best_agent = agent_id
        return best_agent
    return _registry().find_best_agent_for_task(task_type, platform=platform)


def _message_for_resolution(decision: ResolutionResult) -> str:
    if decision.passed:
        return "Agent bundles satisfy all required capabilities"
    if decision.status == "unknown_agent":
        suffix = f" Suggested agent: {decision.suggested_agent}" if decision.suggested_agent else ""
        return f"Agent '{decision.agent_id}' is not registered for platform '{decision.platform}'.{suffix}"
    missing = [item.capability_id for item in decision.unmet_capabilities]
    suffix = f" Suggested agent: {decision.suggested_agent}" if decision.suggested_agent else ""
    return (
        f"Agent '{decision.agent_id}' lacks capabilities: {missing}. "
        f"Recommended bundles: {decision.recommended_bundles or ['<none>']}.{suffix}"
    )


def _result_from_resolution(decision: ResolutionResult) -> SkillCheckResult:
    missing = [item.capability_id for item in decision.unmet_capabilities]
    return SkillCheckResult(
        passed=decision.passed,
        status=decision.status,
        agent_id=decision.agent_id,
        task_type=decision.task_type,
        required_skills=list(decision.required_capabilities),
        missing_skills=missing,
        suggested_agent=decision.suggested_agent,
        message=_message_for_resolution(decision),
        recommended_skills=list(decision.recommended_skills),
        recommended_bundles=list(decision.recommended_bundles),
        unmet_capabilities=[item.to_dict() for item in decision.unmet_capabilities],
        decision_reasons=list(decision.decision_reasons),
        fallback_plan=list(decision.fallback_plan),
        registry_authority=dict(decision.registry_authority),
        platform=decision.platform,
    )


def check_skill_readiness(
    agent_id: str,
    project_card: dict[str, Any],
    profiles: dict[str, AgentSkillProfile] | None = None,
    *,
    platform: str = "openclaw",
    available_bundles: list[str] | None = None,
) -> SkillCheckResult:
    task_type = classify_task_type(project_card)
    required = TASK_SKILL_REQUIREMENTS.get(task_type, ["document_writing"])

    if profiles is not None:
        profile = profiles.get(agent_id)
        if profile is None:
            suggested = find_best_agent(task_type, profiles)
            logger.warning("Unknown agent '%s' — registered profile missing", agent_id)
            return SkillCheckResult(
                passed=False,
                status="unknown_agent",
                agent_id=agent_id,
                task_type=task_type,
                required_skills=required,
                missing_skills=list(required),
                suggested_agent=suggested,
                message=f"Agent '{agent_id}' is not registered; no skill profile found",
                recommended_skills=[],
                recommended_bundles=[],
                unmet_capabilities=[
                    {
                        "capability_id": capability_id,
                        "reason": "unknown_agent",
                        "required_by_task": task_type,
                        "candidate_bundles": [],
                        "candidate_skills": [],
                    }
                    for capability_id in required
                ],
                decision_reasons=[f"custom profile map has no entry for '{agent_id}'"],
                fallback_plan=(
                    [{"action": "switch_agent", "agent_id": suggested, "reason": "registered profile has required capabilities"}]
                    if suggested
                    else []
                ),
                registry_authority={"mode": "compat_profile_projection"},
                platform=platform,
            )
        missing = profile.missing_skills(required)
        if not missing:
            return SkillCheckResult(
                passed=True,
                status="ready",
                agent_id=agent_id,
                task_type=task_type,
                required_skills=required,
                missing_skills=[],
                message="Agent has all required capabilities",
                registry_authority={"mode": "compat_profile_projection"},
                platform=platform,
            )
        suggested = find_best_agent(task_type, profiles)
        msg = (
            f"Agent '{agent_id}' lacks capabilities: {missing}. "
            f"Suggested: '{suggested}'"
            if suggested
            else f"Agent '{agent_id}' lacks capabilities: {missing}. No suitable alternative found."
        )
        return SkillCheckResult(
            passed=False,
            status="unmet_capabilities",
            agent_id=agent_id,
            task_type=task_type,
            required_skills=required,
            missing_skills=missing,
            suggested_agent=suggested,
            message=msg,
            decision_reasons=[msg],
            fallback_plan=(
                [{"action": "switch_agent", "agent_id": suggested, "reason": "registered profile has required capabilities"}]
                if suggested
                else []
            ),
            registry_authority={"mode": "compat_profile_projection"},
            platform=platform,
        )

    decision = get_bundle_resolver().resolve_for_agent(
        agent_id=agent_id,
        task_type=task_type,
        platform=platform,
        available_bundles=available_bundles,
    )
    return _result_from_resolution(decision)
