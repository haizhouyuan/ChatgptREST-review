from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.build_execution_activity_review_bundle import build_bundle


def test_build_bundle_writes_expected_files(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()

    db.put_document(
        Document(
            doc_id="doc_exec",
            source="agent_activity",
            project="ChatgptREST",
            raw_ref="/tmp/doc_exec.jsonl",
            title="doc_exec",
        )
    )
    db.put_episode(
        Episode(
            episode_id="ep_exec",
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
    db.put_atom(
        Atom(
            atom_id="at_exec",
            episode_id="ep_exec",
            atom_type="lesson",
            question="at_exec",
            answer="finished the execution review queue",
            canonical_question="activity: team.run.completed",
            status="candidate",
            promotion_status="staged",
            promotion_reason="activity_ingest",
            applicability=json.dumps(
                {
                    "task_ref": "issue-114",
                    "trace_id": "trace-114",
                    "lane_id": "main",
                    "role_id": "devops",
                    "adapter_id": "controller_lane_wrapper",
                    "profile_id": "mainline_runtime",
                    "executor_kind": "codex.controller",
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            valid_from=1.0,
        )
    )
    db.commit()
    db.close()

    out = tmp_path / "bundle"
    result = build_bundle(db_path=db_path, output_dir=out)

    assert result["ok"] is True
    assert result["selected_atoms"] == 1
    assert (out / "review_queue.json").exists()
    assert (out / "review_queue.tsv").exists()
    assert (out / "summary.json").exists()
    assert (out / "README.md").exists()
    assert "activity: team.run.completed" in (out / "README.md").read_text(encoding="utf-8")
