from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chatgptrest.advisor.qa_inspector import QualityReport8D


FAILURE_TAGS: tuple[str, ...] = (
    "parse_error",
    "incomplete",
    "inaccurate",
    "weak_grounding",
    "kb_underused",
    "low_actionability",
    "poor_communication",
)


@dataclass
class EvaluatorResult:
    evaluator_name: str
    evaluator_model: str
    task_id: str = ""
    channel: str = ""
    user_id: str = ""
    trace_id: str = ""
    run_id: str = ""
    job_id: str = ""
    task_ref: str = ""
    logical_task_id: str = ""
    identity_confidence: str = ""
    quality_score: float = 0.0
    grounding_score: float = 0.0
    usefulness_score: float = 0.0
    risk_label: str = "unknown"
    verdict: str = ""
    failure_tags: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    corrective_actions: list[str] = field(default_factory=list)
    prevention_measures: list[str] = field(default_factory=list)
    knowledge_atoms: list[str] = field(default_factory=list)
    raw_evaluation: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _risk_label(report: "QualityReport8D") -> str:
    if report.overall_verdict == "parse_error":
        return "high"
    if report.accuracy.score <= 2:
        return "high"
    if report.total_score() >= 21:
        return "low"
    if report.total_score() >= 13:
        return "medium"
    return "high"


def _failure_tags(report: "QualityReport8D") -> list[str]:
    tags: list[str] = []
    if report.overall_verdict == "parse_error":
        tags.append("parse_error")
    if report.completeness.score <= 2:
        tags.append("incomplete")
    if report.accuracy.score <= 2:
        tags.append("inaccurate")
    if report.kb_utilization.score <= 2:
        tags.extend(["weak_grounding", "kb_underused"])
    if report.actionability.score <= 2:
        tags.append("low_actionability")
    if report.communication.score <= 2:
        tags.append("poor_communication")
    return list(dict.fromkeys(tags))


def from_qa_report(
    report: "QualityReport8D",
    *,
    trace_id: str = "",
    run_id: str = "",
    job_id: str = "",
    task_ref: str = "",
    logical_task_id: str = "",
    identity_confidence: str = "",
) -> EvaluatorResult:
    total = float(report.max_total() or 1)
    quality_score = round(report.total_score() / total, 4)
    grounding_score = round((report.accuracy.score + report.kb_utilization.score) / 10.0, 4)
    usefulness_score = round(
        (report.completeness.score + report.actionability.score + report.communication.score) / 15.0,
        4,
    )
    strengths = (
        list(report.completeness.strengths[:2])
        + list(report.accuracy.strengths[:2])
        + list(report.actionability.strengths[:2])
    )
    weaknesses = (
        list(report.completeness.weaknesses[:2])
        + list(report.accuracy.weaknesses[:2])
        + list(report.kb_utilization.weaknesses[:2])
        + list(report.actionability.weaknesses[:2])
        + list(report.communication.weaknesses[:2])
    )
    return EvaluatorResult(
        evaluator_name="qa_inspector",
        evaluator_model=report.evaluator_model,
        task_id=report.task_id,
        channel=report.channel,
        user_id=report.user_id,
        trace_id=trace_id,
        run_id=run_id,
        job_id=job_id,
        task_ref=task_ref,
        logical_task_id=logical_task_id,
        identity_confidence=identity_confidence,
        quality_score=quality_score,
        grounding_score=grounding_score,
        usefulness_score=usefulness_score,
        risk_label=_risk_label(report),
        verdict=report.overall_verdict,
        failure_tags=_failure_tags(report),
        strengths=strengths[:8],
        weaknesses=weaknesses[:8],
        corrective_actions=list(report.corrective_actions[:5]),
        prevention_measures=list(report.prevention_measures[:5]),
        knowledge_atoms=list(report.knowledge_atoms[:5]),
        raw_evaluation=report.raw_evaluation[:5000],
    )


class EvaluatorService:
    """Adapter layer that converts existing QA inspector reports into evaluator records."""

    def from_reports(
        self,
        reports: list["QualityReport8D"],
        *,
        trace_id: str = "",
        run_id: str = "",
        job_id: str = "",
        task_ref: str = "",
        logical_task_id: str = "",
        identity_confidence: str = "",
    ) -> list[EvaluatorResult]:
        return [
            from_qa_report(
                report,
                trace_id=trace_id,
                run_id=run_id,
                job_id=job_id,
                task_ref=task_ref,
                logical_task_id=logical_task_id,
                identity_confidence=identity_confidence,
            )
            for report in reports
        ]
