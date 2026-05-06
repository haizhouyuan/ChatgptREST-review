from __future__ import annotations

import csv
from pathlib import Path

from ops.compose_execution_experience_review_decisions import FIELDNAMES, compose, next_versioned_decision_name


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def test_compose_execution_experience_decisions_overlays_delta_and_rewrites_accepted(tmp_path: Path) -> None:
    base = tmp_path / "execution_experience_review_decisions_v2.tsv"
    delta = tmp_path / "delta.tsv"
    output = tmp_path / "merged.tsv"
    _write_rows(
        base,
        [
            {
                "candidate_id": "c1",
                "atom_id": "at1",
                "lineage_family_id": "fam1",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-1",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "experience_kind": "lesson",
                "title": "old title",
                "summary": "old summary",
                "review_decision": "accept",
                "groundedness": "high",
                "time_sensitivity": "evergreen",
                "reviewers": "[]",
            }
        ],
    )
    _write_rows(
        delta,
        [
            {
                "candidate_id": "c1",
                "atom_id": "at1",
                "lineage_family_id": "fam1",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-1",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "experience_kind": "lesson",
                "title": "new title",
                "summary": "new summary",
                "review_decision": "revise",
                "groundedness": "medium",
                "time_sensitivity": "versioned",
                "reviewers": "[]",
            },
            {
                "candidate_id": "c2",
                "atom_id": "at2",
                "lineage_family_id": "fam2",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-2",
                "source": "agent_activity",
                "episode_type": "tool.completed",
                "experience_kind": "procedure",
                "title": "proc title",
                "summary": "proc summary",
                "review_decision": "reject",
                "groundedness": "medium",
                "time_sensitivity": "ephemeral",
                "reviewers": "[]",
            },
        ],
    )

    summary = compose(base, delta, output)
    merged = _read_rows(output)
    accepted = _read_rows(output.with_name("merged_accepted.tsv"))

    assert summary["replaced_candidates"] == 1
    assert summary["added_candidates"] == 1
    assert summary["accepted_candidates"] == 1
    assert next_versioned_decision_name(base) == "execution_experience_review_decisions_v3.tsv"
    assert {row["candidate_id"] for row in merged} == {"c1", "c2"}
    assert accepted[0]["candidate_id"] == "c1"
