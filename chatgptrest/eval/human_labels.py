from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from chatgptrest.eval.evaluator_service import EvaluatorResult


@dataclass
class HumanEvaluationLabel:
    task_id: str = ""
    trace_id: str = ""
    run_id: str = ""
    job_id: str = ""
    task_ref: str = ""
    logical_task_id: str = ""
    labeler: str = ""
    quality_score: float = 0.0
    grounding_score: float = 0.0
    usefulness_score: float = 0.0
    risk_label: str = "unknown"
    accepted: bool = False
    notes: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MetaEvalComparison:
    task_ref: str = ""
    logical_task_id: str = ""
    evaluator_model: str = ""
    quality_delta: float = 0.0
    grounding_delta: float = 0.0
    usefulness_delta: float = 0.0
    risk_match: bool = False
    accepted_match: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HumanLabelSink:
    """File-backed sink for evaluator calibration labels."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def record(self, label: HumanEvaluationLabel) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(label.to_dict(), ensure_ascii=False) + "\n")

    def list_labels(self, *, task_ref: str = "", logical_task_id: str = "") -> list[HumanEvaluationLabel]:
        if not self._path.exists():
            return []
        labels: list[HumanEvaluationLabel] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            label = HumanEvaluationLabel(**payload)
            if task_ref and label.task_ref != task_ref:
                continue
            if logical_task_id and label.logical_task_id != logical_task_id:
                continue
            labels.append(label)
        return labels


def compare_with_human_label(
    evaluator: EvaluatorResult,
    human: HumanEvaluationLabel,
) -> MetaEvalComparison:
    return MetaEvalComparison(
        task_ref=human.task_ref or evaluator.task_ref,
        logical_task_id=human.logical_task_id or evaluator.logical_task_id,
        evaluator_model=evaluator.evaluator_model,
        quality_delta=round(evaluator.quality_score - human.quality_score, 4),
        grounding_delta=round(evaluator.grounding_score - human.grounding_score, 4),
        usefulness_delta=round(evaluator.usefulness_score - human.usefulness_score, 4),
        risk_match=(evaluator.risk_label == human.risk_label),
        accepted_match=((evaluator.risk_label != "high") == human.accepted),
    )
