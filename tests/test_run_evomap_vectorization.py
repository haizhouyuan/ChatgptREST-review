from __future__ import annotations

from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.run_evomap_vectorization import run_vectorization


def _seed(db_path: Path) -> None:
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO documents (doc_id, source, project, raw_ref, title, meta_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "doc1",
            "planning",
            "planning",
            "/vol1/1000/projects/planning/demo/_review_pack/round1/review_pack.md",
            "review pack",
            '{"planning_review":{"source_bucket":"planning_review_pack"}}',
        ),
    )
    conn.execute(
        """
        INSERT INTO episodes (episode_id, doc_id, episode_type, title)
        VALUES (?, ?, ?, ?)
        """,
        ("ep1", "doc1", "md_section", "episode"),
    )
    conn.execute(
        """
        INSERT INTO atoms (
            atom_id, episode_id, question, answer, canonical_question,
            quality_auto, groundedness, promotion_status, scope_project
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "at1",
            "ep1",
            "绿源来访准备",
            "先准备公司背景和来访接待要点。",
            "绿源来访准备",
            0.92,
            0.8,
            "active",
            "planning",
        ),
    )
    conn.commit()
    conn.close()


def test_run_vectorization_indexes_records(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge.db"
    vec_path = tmp_path / "vectors.db"
    _seed(db_path)

    monkeypatch.setattr(
        "chatgptrest.evomap.knowledge.vector_lane.EvoMapVectorIndex._embed_texts",
        lambda self, texts: [__import__("numpy").asarray([float(i + 1), 0.5], dtype="float32") for i, _ in enumerate(texts)],
    )

    summary = run_vectorization(
        db_path=str(db_path),
        vector_db_path=str(vec_path),
        output_root=tmp_path / "artifacts",
        query="绿源 来访 准备",
        top_k=3,
        batch_size=1,
        save_every_batches=1,
        require_vectors=True,
    )

    assert summary["ok"] is True
    assert summary["records_selected"] == 1
    assert summary["post_probe"]["vector_count"] == 1
    assert summary["index_result"]["batches"] == 1
    assert summary["index_result"]["save_every_batches"] == 1
