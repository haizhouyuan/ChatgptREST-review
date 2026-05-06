"""
Acceptance Checker + Scorecard: Unified verification pipeline.

Pro insight: "把 repair.check / autofix 升格为正式验收流水线"
Pro recommends 6 dimensions: completeness, evidence, consistency,
actionability, traceability, latency_efficiency.

Verification flow:
1. Hard check (Python rules) → required artifacts, schema, sections
2. Soft check (local model) → logical consistency, evidence support
3. repair.check (existing) → system-level checks
4. repair.autofix → minor fixes only
5. Scorecard → 6-dimension scoring
6. Archive + index → accepted outputs to KB/memory
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class ScorecardDimension:
    """A single scoring dimension."""

    name: str
    score: float  # 0.0 to 1.0
    max_score: float = 1.0
    notes: str = ""


@dataclass
class Scorecard:
    """
    6-dimension quality scorecard for task deliverables.
    Both Pro and Gemini agreed on a structured scoring approach.
    """

    dimensions: dict[str, ScorecardDimension] = field(default_factory=dict)
    overall: float = 0.0
    accepted: bool = False
    hard_failures: list[str] = field(default_factory=list)
    soft_warnings: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def compute_overall(self) -> float:
        """Compute weighted overall score."""
        if not self.dimensions:
            return 0.0
        total = sum(d.score for d in self.dimensions.values())
        self.overall = total / len(self.dimensions)
        return self.overall

    def is_accepted(self, threshold: float = 0.80) -> bool:
        """Check if scorecard passes acceptance threshold."""
        if self.hard_failures:
            self.accepted = False
            return False
        self.accepted = self.overall >= threshold
        return self.accepted

    def to_dict(self) -> dict:
        return {
            "overall": round(self.overall, 3),
            "accepted": self.accepted,
            "dimensions": {
                name: {
                    "score": round(d.score, 3),
                    "notes": d.notes,
                }
                for name, d in self.dimensions.items()
            },
            "hard_failures": self.hard_failures,
            "soft_warnings": self.soft_warnings,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# Acceptance check definitions per deliverable type
# ─────────────────────────────────────────────

ACCEPTANCE_REQUIREMENTS = {
    "answer": {
        "required_sections": [],
        "min_length_chars": 100,
        "require_evidence": False,
    },
    "research_memo": {
        "required_sections": ["结论", "证据", "风险", "下一步"],
        "min_length_chars": 1000,
        "require_evidence": True,
        "min_evidence_items": 5,
    },
    "report": {
        "required_sections": ["摘要", "分析", "结论"],
        "min_length_chars": 2000,
        "require_evidence": True,
        "min_evidence_items": 3,
    },
    "dataset": {
        "required_sections": [],
        "min_length_chars": 0,
        "require_schema": True,
        "require_freshness": True,
    },
    "code_patch": {
        "required_sections": ["变更说明", "影响范围"],
        "min_length_chars": 100,
        "require_evidence": False,
    },
    "summary": {
        "required_sections": [],
        "min_length_chars": 50,
        "require_evidence": False,
    },
    "scorecard": {
        "required_sections": [],
        "min_length_chars": 0,
        "require_evidence": False,
    },
}


def run_hard_checks(
    content: str,
    deliverable_type: str,
    *,
    artifacts: Optional[list[str]] = None,
) -> tuple[list[str], list[str]]:
    """
    Layer 1: Hard-check validation (Python rule-based).

    Returns (failures, warnings).
    Failures = must fix before acceptance.
    Warnings = should fix but not blocking.
    """
    failures: list[str] = []
    warnings: list[str] = []
    requirements = ACCEPTANCE_REQUIREMENTS.get(
        deliverable_type,
        ACCEPTANCE_REQUIREMENTS["answer"],
    )

    # Check minimum length
    min_len = requirements.get("min_length_chars", 0)
    if len(content) < min_len:
        failures.append(
            f"内容长度 {len(content)} chars < 最低要求 {min_len} chars"
        )

    # Check required sections
    for section in requirements.get("required_sections", []):
        if section not in content:
            failures.append(f"缺少必需章节: '{section}'")

    # Check for TODO/placeholder markers
    todo_markers = ["TODO", "FIXME", "TBD", "待补充", "占位符", "placeholder"]
    for marker in todo_markers:
        if marker in content:
            warnings.append(f"发现占位标记: '{marker}'")

    # Check evidence requirements
    if requirements.get("require_evidence", False):
        min_evidence = requirements.get("min_evidence_items", 0)
        # Simple heuristic: count reference-like patterns
        evidence_count = _count_evidence_items(content)
        if evidence_count < min_evidence:
            warnings.append(
                f"证据数量 {evidence_count} < 建议最低 {min_evidence}"
            )

    # Check empty content
    stripped = content.strip()
    if not stripped:
        failures.append("产物内容为空")

    # Check for self-contradiction markers
    contradiction_markers = ["但与上述矛盾", "然而前面说", "inconsistent with"]
    for marker in contradiction_markers:
        if marker.lower() in content.lower():
            warnings.append(f"可能存在自相矛盾: 发现 '{marker}'")

    return failures, warnings


def _count_evidence_items(content: str) -> int:
    """Count evidence-like patterns in content."""
    import re

    patterns = [
        r'\[?\d+\]',           # [1], [2] style references
        r'来源[:：]',           # 来源: ...
        r'source[:：]',         # source: ...
        r'参考[:：]',           # 参考: ...
        r'https?://\S+',       # URLs
        r'根据.{2,10}数据',     # 根据XX数据
        r'据.{2,10}报告',       # 据XX报告
    ]

    count = 0
    for pattern in patterns:
        count += len(re.findall(pattern, content, re.IGNORECASE))

    return min(count, 20)  # cap at 20


def generate_scorecard(
    content: str,
    deliverable_type: str,
    *,
    latency_s: Optional[float] = None,
    expected_latency_s: Optional[float] = None,
) -> Scorecard:
    """
    Generate a 6-dimension scorecard for a deliverable.

    Dimensions (from Pro's recommendation):
    1. completeness - Are all required sections present?
    2. evidence - Is the content backed by evidence?
    3. consistency - Is the content internally consistent?
    4. actionability - Are there clear, actionable takeaways?
    5. traceability - Can decisions be traced to evidence?
    6. latency_efficiency - Was time used well?
    """
    scorecard = Scorecard()
    failures, warnings = run_hard_checks(content, deliverable_type)
    scorecard.hard_failures = failures
    scorecard.soft_warnings = warnings

    requirements = ACCEPTANCE_REQUIREMENTS.get(
        deliverable_type,
        ACCEPTANCE_REQUIREMENTS["answer"],
    )

    # ── Completeness ─────────────────────────────
    required_sections = requirements.get("required_sections", [])
    if required_sections:
        found = sum(1 for s in required_sections if s in content)
        score = found / len(required_sections)
    else:
        min_len = requirements.get("min_length_chars", 100)
        score = min(len(content) / max(min_len, 1), 1.0)
    scorecard.dimensions["completeness"] = ScorecardDimension(
        name="completeness", score=round(score, 3),
        notes=f"{len(content)} chars, {len(failures)} hard failures",
    )

    # ── Evidence ─────────────────────────────────
    evidence_count = _count_evidence_items(content)
    min_evidence = requirements.get("min_evidence_items", 1)
    evidence_score = min(evidence_count / max(min_evidence, 1), 1.0)
    scorecard.dimensions["evidence"] = ScorecardDimension(
        name="evidence", score=round(evidence_score, 3),
        notes=f"{evidence_count} evidence items found",
    )

    # ── Consistency ──────────────────────────────
    consistency_score = 1.0
    if any("矛盾" in w or "inconsistent" in w.lower() for w in warnings):
        consistency_score = 0.5
    if failures:
        consistency_score = max(consistency_score - 0.2, 0.0)
    scorecard.dimensions["consistency"] = ScorecardDimension(
        name="consistency", score=round(consistency_score, 3),
    )

    # ── Actionability ────────────────────────────
    action_keywords = [
        "建议", "recommend", "应该", "should", "下一步", "next step",
        "行动", "action", "计划", "plan", "优先", "priority",
    ]
    action_count = sum(
        1 for kw in action_keywords if kw.lower() in content.lower()
    )
    actionability_score = min(action_count / 3, 1.0)
    scorecard.dimensions["actionability"] = ScorecardDimension(
        name="actionability", score=round(actionability_score, 3),
        notes=f"{action_count} action keywords found",
    )

    # ── Traceability ─────────────────────────────
    traceability_score = min(evidence_score * 1.2, 1.0)
    if any("TODO" in w or "占位" in w for w in warnings):
        traceability_score = max(traceability_score - 0.3, 0.0)
    scorecard.dimensions["traceability"] = ScorecardDimension(
        name="traceability", score=round(traceability_score, 3),
    )

    # ── Latency Efficiency ───────────────────────
    if latency_s and expected_latency_s and expected_latency_s > 0:
        ratio = expected_latency_s / latency_s
        latency_score = min(ratio, 1.0)
    else:
        latency_score = 0.8  # neutral default
    scorecard.dimensions["latency_efficiency"] = ScorecardDimension(
        name="latency_efficiency", score=round(latency_score, 3),
        notes=f"actual={latency_s}s, expected={expected_latency_s}s" if latency_s else "no timing data",
    )

    scorecard.compute_overall()
    scorecard.is_accepted()

    return scorecard
