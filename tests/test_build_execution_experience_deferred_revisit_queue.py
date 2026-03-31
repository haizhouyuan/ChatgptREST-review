from __future__ import annotations

import csv
import json
from pathlib import Path

from ops.build_execution_experience_deferred_revisit_queue import build_queue
from ops.compose_execution_experience_review_decisions import FIELDNAMES


def _write_decisions(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def test_build_queue_filters_to_deferred_candidates(tmp_path: Path) -> None:
    candidates = tmp_path / "experience_candidates.json"
    candidates.write_text(
        json.dumps(
            [
                {"candidate_id": "execxp_accept", "atom_id": "at1", "experience_kind": "lesson", "title": "keep", "summary": "keep"},
                {"candidate_id": "execxp_defer", "atom_id": "at2", "experience_kind": "procedure", "title": "hold", "summary": "hold"},
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    decisions = tmp_path / "execution_experience_review_decisions_v1.tsv"
    _write_decisions(
        decisions,
        [
            {
                "candidate_id": "execxp_accept",
                "atom_id": "at1",
                "lineage_family_id": "fam1",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-1",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "experience_kind": "lesson",
                "title": "keep",
                "summary": "keep",
                "review_decision": "accept",
                "groundedness": "high",
                "time_sensitivity": "evergreen",
                "reviewers": "[]",
            },
            {
                "candidate_id": "execxp_defer",
                "atom_id": "at2",
                "lineage_family_id": "fam2",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-2",
                "source": "agent_activity",
                "episode_type": "tool.completed",
                "experience_kind": "procedure",
                "title": "hold",
                "summary": "hold",
                "review_decision": "defer",
                "groundedness": "medium",
                "time_sensitivity": "versioned",
                "reviewers": "[]",
            },
        ],
    )

    result = build_queue(candidates_path=candidates, decisions_path=decisions, output_tsv=tmp_path / "deferred_revisit_queue.tsv")
    rows = list(csv.DictReader((tmp_path / "deferred_revisit_queue.tsv").open("r", encoding="utf-8", newline=""), delimiter="\t"))

    assert result["total_deferred_candidates"] == 1
    assert result["by_kind"] == {"procedure": 1}
    assert rows[0]["candidate_id"] == "execxp_defer"
    assert rows[0]["review_decision"] == "defer"
    assert rows[0]["revisit_after"] == ""
