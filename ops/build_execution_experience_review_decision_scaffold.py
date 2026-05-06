#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ops.execution_experience_review_reviewer_identity import load_expected_reviewers


FIELDNAMES = [
    "candidate_id",
    "atom_id",
    "lineage_family_id",
    "lineage_status",
    "task_ref",
    "trace_id",
    "source",
    "episode_type",
    "experience_kind",
    "title",
    "summary",
    "review_decision",
    "groundedness",
    "time_sensitivity",
    "reviewer_count",
    "expected_reviewer_count",
    "provided_reviewers",
    "missing_reviewers",
    "distinct_reviewer_decisions",
    "suggested_governance_state",
    "suggested_governance_action",
    "final_governance_action",
    "governance_reviewer",
    "governance_notes",
]


def _read_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    raise ValueError(f"Expected candidate list JSON at {path}")


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _parse_reviewers(raw: str) -> list[dict[str, Any]]:
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _classify_candidate(
    *,
    review_decision: str,
    distinct_reviewer_decisions: list[str],
    missing_reviewers: list[str],
    has_decision_row: bool,
) -> tuple[str, str]:
    if not has_decision_row:
        return "review_pending", "collect_reviews"
    if review_decision == "defer":
        return "deferred", "needs_followup"
    if len(distinct_reviewer_decisions) > 1:
        return "disputed", "manual_resolution"
    if missing_reviewers:
        return "under_reviewed", "collect_missing_reviews"
    if review_decision == "accept":
        return "decision_ready", "accept_candidate"
    if review_decision == "revise":
        return "decision_ready", "revise_candidate"
    if review_decision == "reject":
        return "decision_ready", "reject_candidate"
    return "review_pending", "collect_reviews"


def build_scaffold(
    *,
    candidates_path: str | Path,
    output_tsv: str | Path,
    decisions_path: str | Path | None = None,
    reviewer_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    candidates = _read_candidates(Path(candidates_path))
    candidate_lookup = {str(row.get("candidate_id") or ""): row for row in candidates}
    candidate_ids = [candidate_id for candidate_id in sorted(candidate_lookup) if candidate_id]
    decision_rows = _read_tsv(Path(decisions_path)) if decisions_path else []
    active_decisions = {
        str(row.get("candidate_id") or ""): row
        for row in decision_rows
        if str(row.get("candidate_id") or "") in candidate_lookup
    }
    expected_reviewers = load_expected_reviewers(Path(reviewer_manifest_path) if reviewer_manifest_path else None)

    scaffold_rows: list[dict[str, Any]] = []
    state_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()
    decision_ready_candidates = 0

    for candidate_id in candidate_ids:
        candidate = candidate_lookup[candidate_id]
        decision_row = active_decisions.get(candidate_id, {})
        reviewers = _parse_reviewers(str(decision_row.get("reviewers") or ""))
        provided_reviewers = sorted(
            {
                str(item.get("reviewer") or "").strip()
                for item in reviewers
                if str(item.get("reviewer") or "").strip()
            }
        )
        missing_reviewers = [reviewer for reviewer in expected_reviewers if reviewer not in provided_reviewers]
        distinct_reviewer_decisions = sorted(
            {
                str(item.get("decision") or "").strip()
                for item in reviewers
                if str(item.get("decision") or "").strip()
            }
        )
        review_decision = str(decision_row.get("review_decision") or "").strip()
        governance_state, governance_action = _classify_candidate(
            review_decision=review_decision,
            distinct_reviewer_decisions=distinct_reviewer_decisions,
            missing_reviewers=missing_reviewers,
            has_decision_row=bool(decision_row),
        )
        state_counter[governance_state] += 1
        action_counter[governance_action] += 1
        if governance_state == "decision_ready":
            decision_ready_candidates += 1

        scaffold_rows.append(
            {
                "candidate_id": candidate_id,
                "atom_id": str(candidate.get("atom_id") or ""),
                "lineage_family_id": str(candidate.get("lineage_family_id") or ""),
                "lineage_status": str(candidate.get("lineage_status") or ""),
                "task_ref": str(candidate.get("task_ref") or ""),
                "trace_id": str(candidate.get("trace_id") or ""),
                "source": str(candidate.get("source") or ""),
                "episode_type": str(candidate.get("episode_type") or ""),
                "experience_kind": str(decision_row.get("experience_kind") or candidate.get("experience_kind") or ""),
                "title": str(decision_row.get("title") or candidate.get("title") or ""),
                "summary": str(decision_row.get("summary") or candidate.get("summary") or ""),
                "review_decision": review_decision,
                "groundedness": str(decision_row.get("groundedness") or ""),
                "time_sensitivity": str(decision_row.get("time_sensitivity") or ""),
                "reviewer_count": len(provided_reviewers),
                "expected_reviewer_count": len(expected_reviewers),
                "provided_reviewers": ",".join(provided_reviewers),
                "missing_reviewers": ",".join(missing_reviewers),
                "distinct_reviewer_decisions": ",".join(distinct_reviewer_decisions),
                "suggested_governance_state": governance_state,
                "suggested_governance_action": governance_action,
                "final_governance_action": "",
                "governance_reviewer": "",
                "governance_notes": "",
            }
        )

    out = Path(output_tsv)
    _write_tsv(out, scaffold_rows)
    summary = {
        "ok": True,
        "candidates_path": str(candidates_path),
        "decisions_path": str(decisions_path) if decisions_path else "",
        "reviewer_manifest_path": str(reviewer_manifest_path) if reviewer_manifest_path else "",
        "output_tsv": str(out),
        "total_candidates": len(scaffold_rows),
        "decision_ready_candidates": decision_ready_candidates,
        "by_governance_state": {key: int(state_counter[key]) for key in sorted(state_counter)},
        "by_governance_action": {key: int(action_counter[key]) for key in sorted(action_counter)},
    }
    summary_path = out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a governance scaffold for execution experience review candidates.")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output-tsv", required=True)
    parser.add_argument("--decisions", default="")
    parser.add_argument("--reviewer-manifest", default="")
    args = parser.parse_args()

    result = build_scaffold(
        candidates_path=args.candidates,
        output_tsv=args.output_tsv,
        decisions_path=Path(args.decisions) if args.decisions else None,
        reviewer_manifest_path=Path(args.reviewer_manifest) if args.reviewer_manifest else None,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
