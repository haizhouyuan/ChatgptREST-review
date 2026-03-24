from __future__ import annotations

import csv
import json
from pathlib import Path

from ops.build_execution_experience_review_decision_scaffold import FIELDNAMES
from ops.export_execution_experience_governance_queues import export_queues


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def test_export_queues_splits_scaffold_by_governance_state(tmp_path: Path) -> None:
    scaffold = tmp_path / "review_decision_scaffold.tsv"
    _write_rows(
        scaffold,
        [
            {
                "candidate_id": "execxp_pending",
                "atom_id": "at_pending",
                "lineage_family_id": "fam_pending",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-pending",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "experience_kind": "lesson",
                "title": "pending",
                "summary": "pending",
                "review_decision": "",
                "groundedness": "",
                "time_sensitivity": "",
                "reviewer_count": "0",
                "expected_reviewer_count": "3",
                "provided_reviewers": "",
                "missing_reviewers": "claudeminmax,codex_auth_only,gemini_no_mcp",
                "distinct_reviewer_decisions": "",
                "suggested_governance_state": "review_pending",
                "suggested_governance_action": "collect_reviews",
                "final_governance_action": "",
                "governance_reviewer": "",
                "governance_notes": "",
            },
            {
                "candidate_id": "execxp_ready",
                "atom_id": "at_ready",
                "lineage_family_id": "fam_ready",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-ready",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "experience_kind": "lesson",
                "title": "ready",
                "summary": "ready",
                "review_decision": "accept",
                "groundedness": "high",
                "time_sensitivity": "evergreen",
                "reviewer_count": "3",
                "expected_reviewer_count": "3",
                "provided_reviewers": "claudeminmax,codex_auth_only,gemini_no_mcp",
                "missing_reviewers": "",
                "distinct_reviewer_decisions": "accept",
                "suggested_governance_state": "decision_ready",
                "suggested_governance_action": "accept_candidate",
                "final_governance_action": "",
                "governance_reviewer": "",
                "governance_notes": "",
            },
        ],
    )

    summary = export_queues(input_tsv=scaffold, output_dir=tmp_path / "queues")
    pending_rows = json.loads(Path(summary["queue_files"]["review_pending"]["json_path"]).read_text(encoding="utf-8"))
    ready_rows = json.loads(Path(summary["queue_files"]["decision_ready"]["json_path"]).read_text(encoding="utf-8"))
    ready_action_rows = json.loads(Path(summary["action_files"]["accept_candidate"]["json_path"]).read_text(encoding="utf-8"))

    assert summary["by_state"] == {"decision_ready": 1, "review_pending": 1}
    assert summary["by_action"] == {"accept_candidate": 1, "collect_reviews": 1}
    assert Path(summary["summary_path"]).exists()
    assert pending_rows[0]["candidate_id"] == "execxp_pending"
    assert ready_rows[0]["candidate_id"] == "execxp_ready"
    assert ready_action_rows[0]["candidate_id"] == "execxp_ready"
