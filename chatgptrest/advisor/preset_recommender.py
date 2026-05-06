"""Preset Recommender — pick the right model preset before wasting hours.

Analyzes a question's characteristics (length, complexity, type) and
recommends the optimal preset + provider combination. This prevents
the common failure mode where a simple question uses ChatGPT Pro
(wastes 30+ minutes) or a complex research task uses a fast preset
(produces low-quality output).

Part of the system-optimization-20260316 feature set.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------

PRESET_PROFILES: dict[str, dict[str, Any]] = {
    "auto": {
        "provider": "chatgpt",
        "avg_turnaround_s": 120,
        "quality": "good",
        "cost": "low",
        "best_for": ["simple questions", "follow-ups", "formatting"],
    },
    "pro_extended": {
        "provider": "chatgpt",
        "avg_turnaround_s": 1800,
        "quality": "excellent",
        "cost": "high",
        "best_for": [
            "complex analysis",
            "architecture review",
            "strategy planning",
            "multi-step reasoning",
        ],
    },
    "thinking_heavy": {
        "provider": "chatgpt",
        "avg_turnaround_s": 600,
        "quality": "very_good",
        "cost": "medium",
        "best_for": [
            "code review",
            "debugging",
            "technical explanation",
            "moderate analysis",
        ],
    },
    "deep_think": {
        "provider": "gemini",
        "avg_turnaround_s": 2400,
        "quality": "excellent",
        "cost": "high",
        "best_for": [
            "deep analysis",
            "comprehensive research",
            "multi-perspective evaluation",
        ],
    },
    "pro": {
        "provider": "gemini",
        "avg_turnaround_s": 300,
        "quality": "good",
        "cost": "low",
        "best_for": ["general questions", "summaries", "quick tasks"],
    },
    "deep_research_chatgpt": {
        "provider": "chatgpt",
        "avg_turnaround_s": 7200,
        "quality": "research_grade",
        "cost": "very_high",
        "best_for": [
            "broad market research",
            "competitive analysis",
            "literature review",
        ],
    },
    "deep_research_gemini": {
        "provider": "gemini",
        "avg_turnaround_s": 3600,
        "quality": "research_grade",
        "cost": "high",
        "best_for": [
            "targeted research",
            "fact-checking",
            "web-based research",
        ],
    },
    "local_llm": {
        "provider": "local",
        "avg_turnaround_s": 30,
        "quality": "moderate",
        "cost": "free",
        "best_for": [
            "quick drafts",
            "summarization",
            "formatting",
            "smoke tests",
            "keyword extraction",
            "classification",
        ],
    },
}

# ---------------------------------------------------------------------------
# Complexity signals
# ---------------------------------------------------------------------------

COMPLEX_KEYWORDS = {
    "zh": [
        "分析", "评审", "架构", "策略", "优化", "深度", "全面", "系统",
        "对比", "权衡", "风险", "设计", "规划", "蓝图", "方案",
    ],
    "en": [
        "analyze", "review", "architecture", "strategy", "optimize",
        "comprehensive", "evaluate", "compare", "trade-off", "design",
        "blueprint", "proposal", "assessment",
    ],
}

RESEARCH_KEYWORDS = {
    "zh": ["调研", "市场", "竞品", "行业", "趋势", "投资", "股票"],
    "en": ["research", "market", "industry", "trend", "competitor", "invest"],
}

SIMPLE_KEYWORDS = {
    "zh": ["翻译", "格式", "总结", "解释", "什么是", "帮我"],
    "en": ["translate", "format", "summarize", "explain", "what is", "help me"],
}


@dataclass
class PresetRecommendation:
    """Recommendation for which preset/provider to use."""

    preset: str
    provider: str
    confidence: float  # 0-1
    estimated_turnaround_s: int
    reason: str
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "provider": self.provider,
            "confidence": self.confidence,
            "estimated_turnaround_s": self.estimated_turnaround_s,
            "estimated_turnaround_human": _human_duration(self.estimated_turnaround_s),
            "reason": self.reason,
            "alternatives": self.alternatives,
            "warnings": self.warnings,
        }


def _human_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h{(seconds % 3600) // 60}m"


def _count_keywords(text: str, keywords: dict[str, list[str]]) -> int:
    text_lower = text.lower()
    count = 0
    for lang_kws in keywords.values():
        for kw in lang_kws:
            count += len(re.findall(re.escape(kw), text_lower))
    return count


def _estimate_complexity(question: str) -> str:
    """Classify question complexity as simple/moderate/complex/research."""
    complex_count = _count_keywords(question, COMPLEX_KEYWORDS)
    research_count = _count_keywords(question, RESEARCH_KEYWORDS)
    simple_count = _count_keywords(question, SIMPLE_KEYWORDS)
    length = len(question)

    # Research tasks.
    if research_count >= 2 or (research_count >= 1 and length > 500):
        return "research"

    # Complex analysis.
    if complex_count >= 3 or (complex_count >= 2 and length > 800):
        return "complex"

    # Simple tasks.
    if simple_count >= 1 and length < 200 and complex_count == 0:
        return "simple"

    # Moderate by default.
    if length > 500 or complex_count >= 1:
        return "moderate"

    return "simple"


def recommend_preset(
    question: str,
    *,
    has_files: bool = False,
    force_provider: str | None = None,
    prefer_local: bool = True,
    task_intake: Mapping[str, Any] | None = None,
    scenario_pack: Mapping[str, Any] | None = None,
) -> PresetRecommendation:
    """Recommend the optimal preset for a given question.

    Args:
        question: The question text.
        has_files: Whether the question includes file attachments.
        force_provider: Force a specific provider (chatgpt/gemini/local).
        prefer_local: If True, prefer local model for simple tasks.

    Returns:
        PresetRecommendation with the suggested preset and alternatives.
    """
    scenario_pack = dict(scenario_pack or {})
    task_intake = dict(task_intake or {})
    scenario = str(task_intake.get("scenario") or "").strip().lower()
    research_profile = str(scenario_pack.get("profile") or "").strip().lower()

    if research_profile in {"topic_research", "comparative_research"} or (
        scenario == "research" and str(scenario_pack.get("route_hint") or "").strip() != "report"
    ):
        return PresetRecommendation(
            preset="deep_research_chatgpt",
            provider=force_provider or "chatgpt",
            confidence=0.82,
            estimated_turnaround_s=7200,
            reason="Research scenario pack selected — use deep research grade preset for evidence-heavy analysis",
            alternatives=[
                {"preset": "deep_research_gemini", "provider": "gemini", "turnaround": "1h"},
                {"preset": "pro_extended", "provider": "chatgpt", "turnaround": "30m"},
            ],
            warnings=[
                "Research scenario asks are evidence-heavy; expect a longer turnaround.",
            ],
        )
    if research_profile == "research_report":
        return PresetRecommendation(
            preset="pro_extended",
            provider=force_provider or "chatgpt",
            confidence=0.8,
            estimated_turnaround_s=1800,
            reason="Research-report scenario pack selected — bias toward premium report writing and analysis quality",
            alternatives=[
                {"preset": "deep_research_chatgpt", "provider": "chatgpt", "turnaround": "2h"},
                {"preset": "deep_think", "provider": "gemini", "turnaround": "40m"},
            ],
            warnings=[
                "If the report still needs heavy web evidence collection, consider a deep-research lane first.",
            ],
        )

    complexity = _estimate_complexity(question)
    warnings: list[str] = []

    # --- Simple tasks ---
    if complexity == "simple":
        if prefer_local and force_provider is None:
            return PresetRecommendation(
                preset="local_llm",
                provider="local",
                confidence=0.8,
                estimated_turnaround_s=30,
                reason="Simple task — use local model for instant response",
                alternatives=[
                    {"preset": "auto", "provider": "chatgpt", "turnaround": "2m"},
                    {"preset": "pro", "provider": "gemini", "turnaround": "5m"},
                ],
            )
        return PresetRecommendation(
            preset="auto",
            provider=force_provider or "chatgpt",
            confidence=0.85,
            estimated_turnaround_s=120,
            reason="Simple task — standard preset sufficient",
            alternatives=[
                {"preset": "pro", "provider": "gemini", "turnaround": "5m"},
            ],
        )

    # --- Moderate tasks ---
    if complexity == "moderate":
        if has_files:
            return PresetRecommendation(
                preset="deep_think",
                provider=force_provider or "gemini",
                confidence=0.7,
                estimated_turnaround_s=2400,
                reason="Moderate task with files — Gemini handles file context well",
                alternatives=[
                    {"preset": "thinking_heavy", "provider": "chatgpt", "turnaround": "10m"},
                ],
            )
        return PresetRecommendation(
            preset="thinking_heavy",
            provider=force_provider or "chatgpt",
            confidence=0.75,
            estimated_turnaround_s=600,
            reason="Moderate complexity — thinking preset gives good depth",
            alternatives=[
                {"preset": "auto", "provider": "chatgpt", "turnaround": "2m"},
                {"preset": "pro", "provider": "gemini", "turnaround": "5m"},
            ],
        )

    # --- Complex tasks ---
    if complexity == "complex":
        return PresetRecommendation(
            preset="pro_extended",
            provider=force_provider or "chatgpt",
            confidence=0.8,
            estimated_turnaround_s=1800,
            reason="Complex analysis — Pro mode for highest quality reasoning",
            alternatives=[
                {"preset": "deep_think", "provider": "gemini", "turnaround": "40m"},
            ],
            warnings=["Expected wait ~30min. Consider if partial local analysis could help first."],
        )

    # --- Research tasks ---
    return PresetRecommendation(
        preset="deep_research_chatgpt",
        provider=force_provider or "chatgpt",
        confidence=0.75,
        estimated_turnaround_s=7200,
        reason="Research task — Deep Research mode for comprehensive web search & analysis",
        alternatives=[
            {"preset": "deep_research_gemini", "provider": "gemini", "turnaround": "1h"},
            {"preset": "pro_extended", "provider": "chatgpt", "turnaround": "30m"},
        ],
        warnings=[
            "Deep Research takes 1-2 hours. Ensure the task genuinely requires web research.",
            "Consider splitting into smaller questions for faster turnaround.",
        ],
    )


def validate_preset_choice(
    question: str,
    chosen_preset: str,
    *,
    task_intake: Mapping[str, Any] | None = None,
    scenario_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a manual preset choice and warn if it looks wrong.

    Returns a dict with:
      - ok: bool
      - recommendation: PresetRecommendation if different from chosen
      - warnings: list[str]
    """
    recommended = recommend_preset(question, task_intake=task_intake, scenario_pack=scenario_pack)
    profile = PRESET_PROFILES.get(chosen_preset, {})
    rec_profile = PRESET_PROFILES.get(recommended.preset, {})

    warnings: list[str] = []

    # Check for overkill.
    chosen_cost = profile.get("cost", "unknown")
    rec_cost = rec_profile.get("cost", "unknown")
    cost_rank = {"free": 0, "low": 1, "medium": 2, "high": 3, "very_high": 4}

    if cost_rank.get(chosen_cost, 2) > cost_rank.get(rec_cost, 2) + 1:
        warnings.append(
            f"Chosen preset '{chosen_preset}' ({chosen_cost} cost) is significantly "
            f"more expensive than recommended '{recommended.preset}' ({rec_cost} cost). "
            f"This may waste {profile.get('avg_turnaround_s', 0) // 60}+ minutes."
        )

    # Check for underkill.
    if cost_rank.get(chosen_cost, 2) < cost_rank.get(rec_cost, 2) - 1:
        warnings.append(
            f"Chosen preset '{chosen_preset}' may be too lightweight for this question. "
            f"Recommended: '{recommended.preset}' for better quality."
        )

    return {
        "ok": len(warnings) == 0,
        "chosen_preset": chosen_preset,
        "recommended": recommended.to_dict(),
        "warnings": warnings,
    }
