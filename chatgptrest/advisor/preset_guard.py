"""
PresetGuard: Multi-layer defense against preset mis-selection.

Both Pro and Gemini identified preset waste as a top issue.
Pro recommends 4 layers: rules → history → checkpoint → feedback.
Gemini recommends: circuit breaker + hard gatekeeping.

This module prevents expensive deep/pro requests when simpler presets suffice,
and blocks inappropriate preset choices based on task characteristics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class PresetDecision:
    """Result of preset guard evaluation."""

    recommended_preset: str
    original_preset: str
    was_overridden: bool = False
    override_reason: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    confidence: float = 1.0


# ─────────────────────────────────────────────
# Preset classification matrix
# ─────────────────────────────────────────────
# Pro insight: "DeepThink 只在自主模式+开放式+高价值同时成立时启用"

PRESET_MATRIX = {
    # deliverable_type → (max_preset, recommended_preset)
    "summary":       ("normal", "normal"),
    "scorecard":     ("normal", "normal"),
    "answer":        ("pro", "normal"),
    "code_patch":    ("pro", "pro"),
    "report":        ("deepthink", "pro"),
    "research_memo": ("deepthink", "pro"),
    "dataset":       ("pro", "normal"),
}

# difficulty → minimum preset
DIFFICULTY_PRESET = {
    1: "normal",
    2: "normal",
    3: "pro",
    4: "pro",
    5: "deepthink",
}


def evaluate_preset(
    *,
    requested_preset: str = "auto",
    mode: str = "interactive",
    deliverable_type: str = "answer",
    difficulty: int = 2,
    latency_budget_s: int = 600,
    evidence_mode: str = "none",
) -> PresetDecision:
    """
    Multi-layer preset guard evaluation.

    Layer 1: Hard rules (mode + deliverable + latency constraints)
    Layer 2: Difficulty-based recommendation
    Layer 3: Evidence mode constraints
    """
    warnings: list[str] = []
    final_preset = requested_preset
    was_overridden = False
    override_reason = None

    # ── Layer 1: Hard rules ──────────────────────────

    # Rule 1: Interactive mode forbids deepthink
    if mode == "interactive" and requested_preset == "deepthink":
        final_preset = "pro"
        was_overridden = True
        override_reason = "交互模式禁止使用 deepthink（延迟预算不足）"
        warnings.append(
            f"DeepThink 在交互模式下被降级为 Pro "
            f"(latency_budget={latency_budget_s}s)"
        )

    # Rule 2: Short latency budget caps at pro
    if latency_budget_s <= 1800 and requested_preset == "deepthink":
        if not was_overridden:
            final_preset = "pro"
            was_overridden = True
            override_reason = f"延迟预算 {latency_budget_s}s ≤ 1800s，不允许 deepthink"
        warnings.append(f"延迟预算 {latency_budget_s}s 不足以支持 deepthink")

    # Rule 3: Simple deliverables cap at normal
    max_preset, recommended = PRESET_MATRIX.get(
        deliverable_type, ("pro", "normal")
    )
    if _preset_level(requested_preset) > _preset_level(max_preset):
        final_preset = max_preset
        was_overridden = True
        override_reason = (
            f"产物类型 '{deliverable_type}' 的上限是 {max_preset}，"
            f"不需要 {requested_preset}"
        )
        warnings.append(
            f"产物 {deliverable_type} 不需要 {requested_preset}，"
            f"降级到 {max_preset}"
        )

    # ── Layer 2: Auto-select based on difficulty ─────

    if final_preset == "auto" or requested_preset == "auto":
        recommended_by_difficulty = DIFFICULTY_PRESET.get(difficulty, "normal")
        # Don't exceed max for deliverable type
        if _preset_level(recommended_by_difficulty) > _preset_level(max_preset):
            recommended_by_difficulty = max_preset

        # Autonomous mode + high difficulty = allow deepthink
        if (
            mode == "autonomous"
            and difficulty >= 4
            and deliverable_type in ("research_memo", "report")
        ):
            recommended_by_difficulty = "deepthink"

        final_preset = recommended_by_difficulty
        was_overridden = requested_preset != "auto"

    # ── Layer 3: Evidence mode constraints ───────────

    if evidence_mode in ("none", "kb") and final_preset == "deepthink":
        final_preset = "pro"
        was_overridden = True
        override_reason = (
            f"evidence_mode='{evidence_mode}' 不需要深度推理，"
            f"降级到 Pro"
        )
        warnings.append(
            f"无外部证据需求时不应使用 deepthink"
        )

    # ── Guard: DeepThink requires all three conditions ──
    # Pro's "very practical hard rule":
    # DeepThink only when autonomous + open-ended + high-value ALL hold

    if final_preset == "deepthink":
        conditions_met = [
            mode == "autonomous",
            deliverable_type in ("research_memo", "report"),
            difficulty >= 4,
        ]
        if not all(conditions_met):
            final_preset = "pro"
            was_overridden = True
            missing = []
            if mode != "autonomous":
                missing.append("非自主模式")
            if deliverable_type not in ("research_memo", "report"):
                missing.append(f"产物类型'{deliverable_type}'非开放式")
            if difficulty < 4:
                missing.append(f"难度{difficulty}<4")
            override_reason = f"DeepThink 三条件未全满足: {', '.join(missing)}"
            warnings.append(override_reason)

    return PresetDecision(
        recommended_preset=final_preset,
        original_preset=requested_preset,
        was_overridden=was_overridden,
        override_reason=override_reason,
        warnings=warnings,
        confidence=0.9 if not was_overridden else 0.7,
    )


def _preset_level(preset: str) -> int:
    """Convert preset name to numeric level for comparison."""
    levels = {
        "normal": 1,
        "auto": 2,
        "pro": 3,
        "pro_extended": 3,
        "thinking_heavy": 3,
        "thinking_extended": 4,
        "deepthink": 4,
        "deep_think": 4,
        "deep_research": 5,
    }
    return levels.get(preset, 2)
