from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExperimentCandidate:
    candidate_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    decision_id: str = ""
    decision_type: str = ""
    owner: str = ""
    stage: str = "proposed"
    rollback_trigger: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentRun:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    candidate_id: str = ""
    stage: str = "offline_replay"
    owner: str = ""
    outcome: str = "pending"
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperimentRegistry:
    """File-backed registry for observer-only experiment lifecycle tracking."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"candidates": [], "runs": []}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def register_candidate(self, candidate: ExperimentCandidate) -> ExperimentCandidate:
        payload = self._read()
        payload["candidates"].append(candidate.to_dict())
        self._write(payload)
        return candidate

    def start_run(
        self,
        *,
        candidate_id: str,
        stage: str,
        owner: str,
        rollback_trigger: str = "",
    ) -> ExperimentRun:
        if stage == "canary" and not rollback_trigger.strip():
            raise ValueError("rollback_trigger is required for canary experiments")
        payload = self._read()
        run = ExperimentRun(
            candidate_id=candidate_id,
            stage=stage,
            owner=owner,
            evidence={"rollback_trigger": rollback_trigger.strip()},
        )
        payload["runs"].append(run.to_dict())
        self._write(payload)
        return run

    def record_result(
        self,
        *,
        run_id: str,
        outcome: str,
        evidence: dict[str, Any] | None = None,
    ) -> ExperimentRun:
        payload = self._read()
        for row in payload["runs"]:
            if row.get("run_id") != run_id:
                continue
            row["outcome"] = str(outcome or "").strip() or "unknown"
            row["updated_at"] = time.time()
            if evidence:
                merged = dict(row.get("evidence") or {})
                merged.update(dict(evidence))
                row["evidence"] = merged
            self._write(payload)
            return ExperimentRun(**row)
        raise KeyError(f"unknown experiment run: {run_id}")

    def list_runs(self, *, candidate_id: str = "") -> list[ExperimentRun]:
        payload = self._read()
        runs = [ExperimentRun(**row) for row in payload["runs"]]
        if candidate_id:
            runs = [run for run in runs if run.candidate_id == candidate_id]
        return runs
