from __future__ import annotations

import json
import time
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode, PromotionStatus
from ops.run_planning_controlled_active_promotion import run_controlled_active_promotion


def _put_controlled_atom(
    db: KnowledgeDB,
    planning_root: Path,
    *,
    doc_name: str,
    title: str,
    query_hits: list[str],
    atom_id: str,
    atom_type: str,
    question: str,
    answer: str,
    quality_auto: float,
) -> None:
    raw_ref = planning_root / doc_name
    raw_ref.write_text(f"# {title}\n\n{answer}\n", encoding="utf-8")
    doc_id = f"doc_{atom_id}"
    ep_id = f"ep_{atom_id}"
    db.put_document(
        Document(
            doc_id=doc_id,
            source="planning",
            project="planning",
            raw_ref=str(raw_ref),
            title=title,
            meta_json=json.dumps(
                {
                    "planning_review": {
                        "source_bucket": "planning_controlled",
                        "document_role": "controlled",
                    },
                    "targeted_reingest": {
                        "query_hits": query_hits,
                    },
                },
                ensure_ascii=False,
            ),
        )
    )
    db.put_episode(Episode(episode_id=ep_id, doc_id=doc_id, episode_type="md_section", title=title))
    db.put_atom(
        Atom(
            atom_id=atom_id,
            episode_id=ep_id,
            atom_type=atom_type,
            question=question,
            answer=answer,
            canonical_question=question,
            quality_auto=quality_auto,
            valid_from=time.time(),
            promotion_status=PromotionStatus.CANDIDATE.value,
            scope_project="planning",
        )
    )


def test_run_controlled_active_promotion_promotes_only_narrow_targeted_slice(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    planning_root = tmp_path / "planning"
    planning_root.mkdir(parents=True)
    db = KnowledgeDB(str(db_path))
    db.init_schema()

    _put_controlled_atom(
        db,
        planning_root,
        doc_name="green.md",
        title="绿源会前包",
        query_hits=["绿源来访准备"],
        atom_id="good_green",
        atom_type="decision",
        question="绿源的关注点是什么？",
        answer="绿源会面前要确认换色能力、标准化轮型和平台复用边界。",
        quality_auto=0.76,
    )
    _put_controlled_atom(
        db,
        planning_root,
        doc_name="green-noisy.md",
        title="绿源噪声稿",
        query_hits=["绿源来访准备"],
        atom_id="noisy_green",
        atom_type="qa",
        question="如何 memory.capture 回执？",
        answer="这是一条不应进入 active 的回执噪声。",
        quality_auto=0.95,
    )
    _put_controlled_atom(
        db,
        planning_root,
        doc_name="tiger.md",
        title="关节模组合作",
        query_hits=["钛虎机器人关节模组合作"],
        atom_id="good_tiger",
        atom_type="qa",
        question="产能与节拍建模是什么？",
        answer="需要按月产 500/1000/2000 套规划节拍、工位与良率爬坡。",
        quality_auto=0.79,
    )
    db.commit()

    summary = run_controlled_active_promotion(
        db_path=str(db_path),
        output_root=tmp_path / "artifacts",
        min_quality=0.72,
        min_groundedness=0.6,
        max_per_query=4,
        live=True,
    )

    assert summary["stats"]["promoted"] == 2
    assert summary["promoted_by_query"]["绿源来访准备"] == 1
    assert summary["promoted_by_query"]["钛虎机器人关节模组合作"] == 1

    conn = db.connect()
    rows = {
        row["atom_id"]: dict(row)
        for row in conn.execute("SELECT atom_id, promotion_status, promotion_reason, groundedness FROM atoms")
    }
    assert rows["good_green"]["promotion_status"] == PromotionStatus.ACTIVE.value
    assert rows["good_tiger"]["promotion_status"] == PromotionStatus.ACTIVE.value
    assert rows["noisy_green"]["promotion_status"] == PromotionStatus.CANDIDATE.value
    assert rows["good_green"]["groundedness"] >= 0.6
    assert rows["good_tiger"]["groundedness"] >= 0.6
    assert rows["good_green"]["promotion_reason"].startswith("planning_controlled_active:")
