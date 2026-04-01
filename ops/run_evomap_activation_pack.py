"""Run a narrow EvoMap activation pack for runtime-visible staged atoms.

This tool evaluates a small, governed set of staged atoms against the existing
groundedness rules and, when applied, writes groundedness scores plus audit
records without changing promotion_status. It is designed to turn the current
"one-off manual activation" workflow into a repeatable, reviewable operation.

Typical usage:

    PYTHONPATH=. ./.venv/bin/python ops/run_evomap_activation_pack.py \
      --source agent_activity \
      --limit 10 \
      --threshold 0.5 \
      --report-json /tmp/evomap_activation_pack.json

    PYTHONPATH=. ./.venv/bin/python ops/run_evomap_activation_pack.py \
      --atom-id at_123 \
      --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import time
from dataclasses import asdict, dataclass
from typing import Iterable

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.groundedness_checker import (
    GroundednessAuditRecord,
    check_atom_groundedness,
)

logger = logging.getLogger(__name__)

_DEFAULT_DB = resolve_evomap_knowledge_runtime_db_path()


@dataclass
class ActivationCandidate:
    atom_id: str
    source: str
    project: str
    promotion_status: str
    status: str
    quality_auto: float
    groundedness: float
    valid_from: float
    question: str
    canonical_question: str
    answer: str


@dataclass
class ActivationEvaluation:
    candidate: ActivationCandidate
    overall_score: float
    passed: bool
    evidence: list[str]
    audit_record: GroundednessAuditRecord

    def to_dict(self) -> dict:
        payload = asdict(self.candidate)
        payload.update(
            {
                "overall_score": self.overall_score,
                "passed": self.passed,
                "evidence": list(self.evidence),
                "audit_id": self.audit_record.audit_id,
            }
        )
        return payload


@dataclass
class ActivationPackSummary:
    db_path: str
    threshold: float
    selected: int
    passed: int
    failed: int
    applied: bool
    by_source: dict[str, int]
    evaluations: list[ActivationEvaluation]

    def to_dict(self) -> dict:
        return {
            "db_path": self.db_path,
            "threshold": self.threshold,
            "selected": self.selected,
            "passed": self.passed,
            "failed": self.failed,
            "applied": self.applied,
            "by_source": dict(self.by_source),
            "evaluations": [evaluation.to_dict() for evaluation in self.evaluations],
        }


def _placeholders(values: Iterable[object]) -> str:
    values = list(values)
    if not values:
        raise ValueError("placeholders() requires at least one value")
    return ", ".join("?" for _ in values)


def select_activation_candidates(
    db: KnowledgeDB,
    *,
    atom_ids: list[str] | None = None,
    sources: list[str] | None = None,
    promotion_statuses: tuple[str, ...] = ("staged",),
    min_quality: float = 0.15,
    limit: int = 25,
) -> list[ActivationCandidate]:
    """Select a narrow staged-atom pack for activation review."""
    conn = db.connect()

    clauses = [
        f"a.promotion_status IN ({_placeholders(promotion_statuses)})",
        "a.stability != 'superseded'",
        "a.quality_auto >= ?",
    ]
    params: list[object] = [*promotion_statuses, min_quality]

    if atom_ids:
        clauses.append(f"a.atom_id IN ({_placeholders(atom_ids)})")
        params.extend(atom_ids)

    if sources:
        clauses.append(f"d.source IN ({_placeholders(sources)})")
        params.extend(sources)

    params.append(limit)

    rows = conn.execute(
        f"""
        SELECT
            a.atom_id,
            a.promotion_status,
            a.status,
            a.quality_auto,
            a.groundedness,
            a.valid_from,
            a.question,
            a.canonical_question,
            a.answer,
            COALESCE(d.source, '') AS source,
            COALESCE(d.project, '') AS project
        FROM atoms a
        LEFT JOIN episodes ep ON ep.episode_id = a.episode_id
        LEFT JOIN documents d ON d.doc_id = ep.doc_id
        WHERE {' AND '.join(clauses)}
        ORDER BY a.quality_auto DESC, a.valid_from DESC, a.atom_id ASC
        LIMIT ?
        """,
        params,
    ).fetchall()

    return [
        ActivationCandidate(
            atom_id=row["atom_id"],
            source=row["source"],
            project=row["project"],
            promotion_status=row["promotion_status"],
            status=row["status"],
            quality_auto=row["quality_auto"] or 0.0,
            groundedness=row["groundedness"] or 0.0,
            valid_from=row["valid_from"] or 0.0,
            question=row["question"] or "",
            canonical_question=row["canonical_question"] or "",
            answer=row["answer"] or "",
        )
        for row in rows
    ]


def evaluate_activation_candidates(
    candidates: list[ActivationCandidate],
    *,
    threshold: float = 0.5,
) -> list[ActivationEvaluation]:
    """Run groundedness evaluation on a candidate pack."""
    evaluations: list[ActivationEvaluation] = []
    for candidate in candidates:
        result = check_atom_groundedness(
            candidate.atom_id,
            candidate.answer,
            candidate.valid_from,
        )
        passed = result.overall >= threshold
        audit_record = GroundednessAuditRecord(
            atom_id=candidate.atom_id,
            passed=passed,
            overall_score=result.overall,
            path_score=result.path_score,
            service_score=result.service_score,
            staleness_score=result.staleness_score,
            code_symbol_score=result.code_symbol_score,
            evidence_json=json.dumps(result.evidence),
        )
        evaluations.append(
            ActivationEvaluation(
                candidate=candidate,
                overall_score=result.overall,
                passed=passed,
                evidence=list(result.evidence),
                audit_record=audit_record,
            )
        )
    return evaluations


def apply_activation_evaluations(
    db: KnowledgeDB,
    evaluations: list[ActivationEvaluation],
    *,
    max_retries: int = 15,
    retry_sleep_seconds: float = 2.0,
    busy_timeout_ms: int = 10000,
) -> None:
    """Persist groundedness scores and audit records without changing promotion."""
    conn = db.connect()
    conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")

    updates = [
        (evaluation.overall_score, evaluation.candidate.atom_id)
        for evaluation in evaluations
    ]
    rows = [evaluation.audit_record.to_row() for evaluation in evaluations]

    for attempt in range(max_retries):
        try:
            if updates:
                conn.executemany(
                    "UPDATE atoms SET groundedness = ? WHERE atom_id = ?",
                    updates,
                )

            if rows:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO groundedness_audit
                      (audit_id, atom_id, timestamp, passed, overall_score,
                       path_score, service_score, staleness_score, code_symbol_score, evidence_json)
                    VALUES
                      (:audit_id, :atom_id, :timestamp, :passed, :overall_score,
                       :path_score, :service_score, :staleness_score, :code_symbol_score, :evidence_json)
                    """,
                    rows,
                )

            conn.commit()
            return
        except sqlite3.OperationalError as exc:
            conn.rollback()
            if "locked" not in str(exc).lower() or attempt >= max_retries - 1:
                raise
            time.sleep(retry_sleep_seconds)


def run_activation_pack(
    db: KnowledgeDB,
    *,
    atom_ids: list[str] | None = None,
    sources: list[str] | None = None,
    promotion_statuses: tuple[str, ...] = ("staged",),
    min_quality: float = 0.15,
    threshold: float = 0.5,
    limit: int = 25,
    apply: bool = False,
    max_retries: int = 15,
    retry_sleep_seconds: float = 2.0,
    busy_timeout_ms: int = 10000,
) -> ActivationPackSummary:
    """Select, evaluate, and optionally persist a narrow activation pack."""
    candidates = select_activation_candidates(
        db,
        atom_ids=atom_ids,
        sources=sources,
        promotion_statuses=promotion_statuses,
        min_quality=min_quality,
        limit=limit,
    )
    evaluations = evaluate_activation_candidates(candidates, threshold=threshold)
    if apply and evaluations:
        apply_activation_evaluations(
            db,
            evaluations,
            max_retries=max_retries,
            retry_sleep_seconds=retry_sleep_seconds,
            busy_timeout_ms=busy_timeout_ms,
        )

    by_source: dict[str, int] = {}
    passed = 0
    for evaluation in evaluations:
        by_source[evaluation.candidate.source] = by_source.get(evaluation.candidate.source, 0) + 1
        if evaluation.passed:
            passed += 1

    return ActivationPackSummary(
        db_path=db.db_path,
        threshold=threshold,
        selected=len(evaluations),
        passed=passed,
        failed=len(evaluations) - passed,
        applied=apply,
        by_source=by_source,
        evaluations=evaluations,
    )


def _write_report(path: str, summary: ActivationPackSummary) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Run a narrow EvoMap activation pack")
    parser.add_argument("--db", default=_DEFAULT_DB)
    parser.add_argument("--atom-id", action="append", dest="atom_ids", default=[])
    parser.add_argument("--source", action="append", dest="sources", default=[])
    parser.add_argument("--promotion-status", action="append", dest="promotion_statuses", default=[])
    parser.add_argument("--min-quality", type=float, default=0.15)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--max-retries", type=int, default=15)
    parser.add_argument("--retry-sleep-seconds", type=float, default=2.0)
    parser.add_argument("--busy-timeout-ms", type=int, default=10000)
    parser.add_argument("--report-json")
    args = parser.parse_args()

    db_path = os.path.expanduser(args.db)
    if not os.path.exists(db_path):
        print(f"DB not found: {db_path}")
        return 1

    promotion_statuses = tuple(args.promotion_statuses or ["staged"])
    with KnowledgeDB(db_path=db_path) as db:
        summary = run_activation_pack(
            db,
            atom_ids=args.atom_ids or None,
            sources=args.sources or None,
            promotion_statuses=promotion_statuses,
            min_quality=args.min_quality,
            threshold=args.threshold,
            limit=args.limit,
            apply=args.apply,
            max_retries=args.max_retries,
            retry_sleep_seconds=args.retry_sleep_seconds,
            busy_timeout_ms=args.busy_timeout_ms,
        )

    if args.report_json:
        _write_report(args.report_json, summary)

    print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
