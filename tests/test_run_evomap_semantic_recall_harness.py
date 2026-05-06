from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.run_evomap_semantic_recall_harness import run_harness


def _seed(db_path: Path) -> None:
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    db.put_document(
        Document(
            doc_id="doc1",
            source="planning",
            project="planning",
            raw_ref="/planning/两轮车车身业务/2026-03-19_绿源拜访会议纪要.md",
            title="绿源拜访会议纪要",
            meta_json=json.dumps({"planning_review": {"source_bucket": "planning_outputs"}}, ensure_ascii=False),
        )
    )
    db.put_episode(Episode(episode_id="ep1", doc_id="doc1", episode_type="md_section", title="绿源拜访会议纪要"))
    db.put_atom(
        Atom(
            atom_id="at1",
            episode_id="ep1",
            question="绿源拜访会议纪要是什么？",
            answer="绿源来访前要准备公司背景、产线参观和合作议题。",
            canonical_question="绿源拜访会议纪要",
            quality_auto=0.82,
            groundedness=0.8,
            status="reviewed",
            promotion_status="candidate",
            scope_project="planning",
        )
    )
    db.commit()


def test_run_harness_reports_nonzero_hits(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge.db"
    vec_path = tmp_path / "vectors.db"
    _seed(db_path)

    summary = run_harness(
        db_path=str(db_path),
        vector_db_path=str(vec_path),
        output_root=tmp_path / "artifacts",
        queries=["绿源来访准备"],
        result_limit=3,
    )

    assert summary["ok"] is True
    assert summary["query_count"] == 1
    assert summary["queries"][0]["hit_count"] >= 1
    assert summary["queries"][0]["hits"][0]["atom_id"] == "at1"
