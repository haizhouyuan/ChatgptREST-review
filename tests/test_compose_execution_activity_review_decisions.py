from __future__ import annotations

import csv
from pathlib import Path

from ops.compose_execution_activity_review_decisions import FIELDNAMES, compose, next_versioned_decision_name


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def test_compose_execution_decisions_overlays_delta_and_rewrites_allowlist(tmp_path: Path) -> None:
    base = tmp_path / "execution_review_decisions_v2.tsv"
    delta = tmp_path / "delta.tsv"
    output = tmp_path / "merged.tsv"
    _write_rows(
        base,
        [
            {
                "atom_id": "at1",
                "lineage_family_id": "fam1",
                "lineage_status": "complete",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "atom_type": "lesson",
                "task_ref": "issue-115",
                "trace_id": "trace-1",
                "canonical_question": "activity: workflow.completed",
                "suggested_bucket": "lesson",
                "final_bucket": "lesson",
                "lineage_action": "keep_lineage",
                "experience_kind": "lesson",
                "experience_title": "completed workflow",
                "experience_summary": "keep",
                "reviewer": "r1",
                "review_notes": "base",
            }
        ],
    )
    _write_rows(
        delta,
        [
            {
                "atom_id": "at1",
                "lineage_family_id": "fam1",
                "lineage_status": "complete",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "atom_type": "lesson",
                "task_ref": "issue-115",
                "trace_id": "trace-1",
                "canonical_question": "activity: workflow.completed",
                "suggested_bucket": "lesson",
                "final_bucket": "correction",
                "lineage_action": "keep_lineage",
                "experience_kind": "correction",
                "experience_title": "fix completed workflow",
                "experience_summary": "delta",
                "reviewer": "r2",
                "review_notes": "delta",
            },
            {
                "atom_id": "at2",
                "lineage_family_id": "fam1",
                "lineage_status": "complete",
                "source": "agent_activity",
                "episode_type": "tool.completed",
                "atom_type": "lesson",
                "task_ref": "issue-115",
                "trace_id": "trace-2",
                "canonical_question": "activity: tool.completed",
                "suggested_bucket": "lesson",
                "final_bucket": "review_only",
                "lineage_action": "keep_lineage",
                "experience_kind": "",
                "experience_title": "",
                "experience_summary": "",
                "reviewer": "r2",
                "review_notes": "hold",
            },
        ],
    )

    summary = compose(base, delta, output)
    merged = _read_rows(output)
    allowlist = _read_rows(output.with_name("merged_allowlist.tsv"))

    assert summary["replaced_atoms"] == 1
    assert summary["added_atoms"] == 1
    assert summary["allowlist_atoms"] == 1
    assert next_versioned_decision_name(base) == "execution_review_decisions_v3.tsv"
    assert {row["atom_id"] for row in merged} == {"at1", "at2"}
    assert allowlist[0]["atom_id"] == "at1"
