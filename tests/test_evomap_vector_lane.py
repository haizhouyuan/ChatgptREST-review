from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode, PromotionStatus, Stability
from chatgptrest.evomap.knowledge.vector_lane import (
    EvoMapVectorIndex,
    fetch_records_for_vectorization,
    probe_vector_store,
)


def _seed_atom(db: KnowledgeDB, *, atom_id: str, question: str, answer: str, promotion_status: str) -> None:
    doc_id = f"doc_{atom_id}"
    db.put_document(
        Document(
            doc_id=doc_id,
            source="planning",
            project="planning",
            raw_ref=f"/planning/outputs/{atom_id}.md",
            title=question[:80],
            meta_json=json.dumps({"planning_review": {"source_bucket": "planning_outputs"}}, ensure_ascii=False),
        )
    )
    db.put_episode(Episode(episode_id=f"ep_{atom_id}", doc_id=doc_id, episode_type="md_section", title=question[:80]))
    db.put_atom(
        Atom(
            atom_id=atom_id,
            episode_id=f"ep_{atom_id}",
            question=question,
            answer=answer,
            scope_project="planning",
            quality_auto=0.85,
            groundedness=0.9,
            status="reviewed",
            stability=Stability.VERSIONED.value,
            promotion_status=promotion_status,
        )
    )


def test_vectorize_records_persists_vectors(tmp_path: Path, monkeypatch) -> None:
    db = KnowledgeDB(db_path=":memory:")
    db.init_schema()
    _seed_atom(db, atom_id="at_a", question="合同底线", answer="付款节点和验收条款要写死。", promotion_status=PromotionStatus.ACTIVE.value)
    _seed_atom(db, atom_id="at_b", question="供应商准备", answer="要准备价格、交期和质量条款。", promotion_status=PromotionStatus.CANDIDATE.value)

    records = fetch_records_for_vectorization(db, promotion_statuses=("active", "candidate"), scope_projects=("planning",))
    assert {record.atom_id for record in records} == {"at_a", "at_b"}

    vector_db = tmp_path / "evomap_vectors.db"
    index = EvoMapVectorIndex(vector_db)
    monkeypatch.setattr(
        index,
        "_embed_texts",
        lambda texts: [np.array([float(i + 1), 0.5], dtype=np.float32) for i, _ in enumerate(texts)],
    )

    stats = index.index_records(records)
    index.close()

    assert stats["indexed"] == 2
    probe = probe_vector_store(vector_db)
    assert probe["exists"] is True
    assert probe["vector_count"] == 2
