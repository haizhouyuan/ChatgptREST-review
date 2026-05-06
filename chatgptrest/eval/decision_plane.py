from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from chatgptrest.eval.evaluator_service import EvaluatorResult


@dataclass
class RetrievalEvidence:
    artifact_id: str
    source: str = ""
    selected: bool = False
    used_in_answer: bool = False
    staged_influence: bool = False
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImprovementDecision:
    decision_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    decision_type: str = ""
    task_ref: str = ""
    logical_task_id: str = ""
    evaluator_model: str = ""
    status: str = "proposed"
    rationale: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DecisionPlane:
    """Observer-only improvement proposal generator."""

    def propose(
        self,
        *,
        evaluations: Iterable[EvaluatorResult],
        retrieval_evidence: Iterable[RetrievalEvidence] = (),
    ) -> list[ImprovementDecision]:
        evals = list(evaluations)
        evidence = list(retrieval_evidence)
        decisions: list[ImprovementDecision] = []
        decisions.extend(self._promotion_proposals(evals))
        decisions.extend(self._suppression_proposals(evals, evidence))
        return decisions

    def _promotion_proposals(self, evaluations: list[EvaluatorResult]) -> list[ImprovementDecision]:
        proposals: list[ImprovementDecision] = []
        for item in evaluations:
            if item.quality_score < 0.8 or item.risk_label == "high":
                continue
            if not item.knowledge_atoms:
                continue
            proposals.append(
                ImprovementDecision(
                    decision_type="promotion_proposal",
                    task_ref=item.task_ref,
                    logical_task_id=item.logical_task_id,
                    evaluator_model=item.evaluator_model,
                    rationale="high-quality evaluated outcome with reusable knowledge atoms",
                    evidence=[
                        {"quality_score": item.quality_score},
                        {"knowledge_atoms": list(item.knowledge_atoms)},
                        {"risk_label": item.risk_label},
                    ],
                )
            )
        return proposals

    def _suppression_proposals(
        self,
        evaluations: list[EvaluatorResult],
        retrieval_evidence: list[RetrievalEvidence],
    ) -> list[ImprovementDecision]:
        needs_suppression = any(
            "weak_grounding" in item.failure_tags or "kb_underused" in item.failure_tags
            for item in evaluations
        )
        if not needs_suppression:
            return []

        proposals: list[ImprovementDecision] = []
        for item in retrieval_evidence:
            if item.used_in_answer:
                continue
            if not (item.selected or item.staged_influence):
                continue
            proposals.append(
                ImprovementDecision(
                    decision_type="suppression_proposal",
                    rationale="selected retrieval evidence was unused or staged-biased during a weak-grounding outcome",
                    evidence=[item.to_dict()],
                )
            )
        return proposals
