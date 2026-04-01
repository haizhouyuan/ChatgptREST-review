from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.build_execution_lineage_remediation_bundle import build_bundle


def test_build_bundle_writes_remediation_and_decision_inputs(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()

    db.put_document(
        Document(
            doc_id="doc_exec",
            source="agent_activity",
            project="ChatgptREST",
            raw_ref="/tmp/doc_exec.json",
            title="doc_exec",
        )
    )
    db.put_episode(
        Episode(
            episode_id="ep_exec_1",
            doc_id="doc_exec",
            episode_type="team.run.completed",
            title="team.run.completed",
            summary="team.run.completed",
            start_ref="doc_exec:1",
            end_ref="doc_exec:1",
            time_start=1.0,
            time_end=1.0,
        )
    )
    db.put_episode(
        Episode(
            episode_id="ep_exec_2",
            doc_id="doc_exec",
            episode_type="workflow.completed",
            title="workflow.completed",
            summary="workflow.completed",
            start_ref="doc_exec:2",
            end_ref="doc_exec:2",
            time_start=2.0,
            time_end=2.0,
        )
    )
    db.put_episode(
        Episode(
            episode_id="ep_exec_3",
            doc_id="doc_exec",
            episode_type="tool.completed",
            title="tool.completed",
            summary="tool.completed",
            start_ref="doc_exec:3",
            end_ref="doc_exec:3",
            time_start=3.0,
            time_end=3.0,
        )
    )
    db.put_atom(
        Atom(
            atom_id="at_sparse",
            episode_id="ep_exec_1",
            atom_type="lesson",
            question="at_sparse",
            answer="sparse execution event",
            canonical_question="activity: team.run.completed",
            status="candidate",
            promotion_status="staged",
            promotion_reason="activity_ingest",
            applicability=json.dumps(
                {"task_ref": "issue-115", "trace_id": "trace-115"},
                ensure_ascii=False,
                sort_keys=True,
            ),
            valid_from=1.0,
        )
    )
    db.put_atom(
        Atom(
            atom_id="at_rich",
            episode_id="ep_exec_2",
            atom_type="lesson",
            question="at_rich",
            answer="richer execution event",
            canonical_question="activity: workflow.completed",
            status="candidate",
            promotion_status="staged",
            promotion_reason="activity_ingest",
            applicability=json.dumps(
                {
                    "task_ref": "issue-115",
                    "trace_id": "trace-115",
                    "lane_id": "main",
                    "role_id": "devops",
                    "adapter_id": "controller_lane_wrapper",
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            valid_from=2.0,
        )
    )
    db.put_atom(
        Atom(
            atom_id="at_full",
            episode_id="ep_exec_3",
            atom_type="lesson",
            question="at_full",
            answer="fully decorated execution event",
            canonical_question="activity: tool.completed",
            status="candidate",
            promotion_status="staged",
            promotion_reason="activity_ingest",
            applicability=json.dumps(
                {
                    "task_ref": "issue-116",
                    "trace_id": "trace-116",
                    "lane_id": "main",
                    "role_id": "devops",
                    "adapter_id": "controller_lane_wrapper",
                    "profile_id": "mainline_runtime",
                    "executor_kind": "codex.controller",
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            valid_from=3.0,
        )
    )
    db.commit()
    db.close()

    out = tmp_path / "bundle"
    result = build_bundle(db_path=db_path, output_dir=out)

    assert result["ok"] is True
    assert result["selected_atoms"] == 3
    assert result["correlation_groups"] == 2
    assert result["rows_review_ready"] == 1
    assert result["rows_remediation_candidate"] == 1
    assert result["rows_manual_review_required"] == 1
    assert (out / "identity_correlation_audit.json").exists()
    assert (out / "lineage_remediation_manifest.json").exists()
    assert (out / "review_decision_input.json").exists()
    assert (out / "review_decision_input.tsv").exists()
    assert (out / "summary.json").exists()
    assert (out / "README.md").exists()

    audit = json.loads((out / "identity_correlation_audit.json").read_text(encoding="utf-8"))
    mixed_group = next(item for item in audit["groups"] if item["task_ref"] == "issue-115")
    assert mixed_group["cluster_status"] == "mixed_identity_richness"
    assert mixed_group["extension_union"] == ["adapter_id", "lane_id", "role_id"]

    manifest = json.loads((out / "lineage_remediation_manifest.json").read_text(encoding="utf-8"))
    sparse_row = next(item for item in manifest["rows"] if item["atom_id"] == "at_sparse")
    rich_row = next(item for item in manifest["rows"] if item["atom_id"] == "at_rich")
    full_row = next(item for item in manifest["rows"] if item["atom_id"] == "at_full")
    assert sparse_row["candidate_fill_fields"] == ["adapter_id", "lane_id", "role_id"]
    assert sparse_row["decision_bucket"] == "remediation_candidate"
    assert sparse_row["remediation_action"] == "correlate_fill_from_group"
    assert rich_row["candidate_fill_fields"] == []
    assert rich_row["decision_bucket"] == "manual_review_required"
    assert rich_row["remediation_action"] == "hold_sparse_lineage"
    assert full_row["decision_bucket"] == "review_ready"
    assert full_row["remediation_action"] == "none"
