from __future__ import annotations

import csv
import json
from pathlib import Path

from ops.compose_execution_experience_review_decisions import FIELDNAMES
from ops.export_execution_experience_acceptance_pack import export_pack


def _write_decisions(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def test_export_pack_filters_to_accept_candidates(tmp_path: Path) -> None:
    candidates = tmp_path / "experience_candidates.json"
    candidates.write_text(
        json.dumps(
            [
                {"candidate_id": "execxp_accept", "atom_id": "at1", "experience_kind": "lesson", "title": "keep", "summary": "keep"},
                {"candidate_id": "execxp_revise", "atom_id": "at2", "experience_kind": "procedure", "title": "rewrite", "summary": "rewrite"},
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
                "candidate_id": "execxp_revise",
                "atom_id": "at2",
                "lineage_family_id": "fam2",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-2",
                "source": "agent_activity",
                "episode_type": "tool.completed",
                "experience_kind": "procedure",
                "title": "rewrite",
                "summary": "rewrite",
                "review_decision": "revise",
                "groundedness": "medium",
                "time_sensitivity": "versioned",
                "reviewers": "[]",
            },
        ],
    )

    result = export_pack(candidates_path=candidates, decisions_path=decisions, output_dir=tmp_path / "accepted_pack")
    accepted = json.loads((tmp_path / "accepted_pack" / "accepted_candidates.json").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "accepted_pack" / "manifest.json").read_text(encoding="utf-8"))

    assert result["accepted_candidates"] == 1
    assert accepted[0]["candidate_id"] == "execxp_accept"
    assert manifest["scope"]["review_plane_only"] is True
    assert manifest["scope"]["default_runtime_cutover"] is False
    assert manifest["checks"]["accept_only_decisions_ok"] is True
