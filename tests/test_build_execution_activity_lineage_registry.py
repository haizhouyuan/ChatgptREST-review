from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.build_execution_activity_lineage_registry import build_lineage_registry, write_lineage_registry


def test_build_lineage_registry_groups_ready_and_gap_atoms(tmp_path: Path) -> None:
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
            episode_id="ep_ready",
            doc_id="doc_exec",
            episode_type="workflow.completed",
            title="workflow.completed",
            summary="workflow.completed",
            start_ref="doc_exec:1",
            end_ref="doc_exec:1",
            time_start=1.0,
            time_end=1.0,
            source_ext=json.dumps({"provider": "openai-codex", "model": "gpt-5.4"}, ensure_ascii=False),
        )
    )
    db.put_atom(
        Atom(
            atom_id="at_ready",
            episode_id="ep_ready",
            atom_type="lesson",
            question="at_ready",
            answer="completed an execution cycle",
            canonical_question="activity: workflow.completed",
            status="candidate",
            promotion_status="staged",
            promotion_reason="activity_ingest",
            applicability=json.dumps(
                {"task_ref": "issue-115", "trace_id": "trace-115"},
                ensure_ascii=False,
                sort_keys=True,
            ),
            valid_from=2.0,
        )
    )
    db.put_episode(
        Episode(
            episode_id="ep_gap",
            doc_id="doc_exec",
            episode_type="agent.task.closeout",
            title="agent.task.closeout",
            summary="agent.task.closeout",
            start_ref="doc_exec:2",
            end_ref="doc_exec:2",
            time_start=1.0,
            time_end=1.0,
        )
    )
    db.put_atom(
        Atom(
            atom_id="at_gap",
            episode_id="ep_gap",
            atom_type="lesson",
            question="at_gap",
            answer="closeout without lineage anchors",
            canonical_question="",
            status="candidate",
            promotion_status="staged",
            promotion_reason="activity_ingest",
            applicability="{}",
            valid_from=1.0,
        )
    )
    db.commit()
    db.close()

    report = build_lineage_registry(db_path=db_path)
    written = write_lineage_registry(report, tmp_path / "lineage")

    assert report["summary"]["selected_atoms"] == 2
    assert report["summary"]["lineage_families"] == 2
    assert report["summary"]["gap_atoms"] == 1
    assert report["families"][0]["review_ready_atoms"] == 1
    assert report["gaps"][0]["lineage_action"] == "archive_only_until_anchor_available"
    assert Path(written["summary_path"]).exists()
    assert (tmp_path / "lineage" / "lineage_family_registry.tsv").exists()
