from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from ops.run_planning_targeted_reingest import run_targeted_reingest


def test_run_targeted_reingest_seeds_controlled_candidates(tmp_path: Path) -> None:
    planning_root = tmp_path / "planning"
    twowheel_dir = planning_root / "两轮车车身业务"
    twowheel_dir.mkdir(parents=True)
    (twowheel_dir / "2026-03-30_绿源会中问题单_打印版_v1.md").write_text(
        "\n".join(
            [
                "---",
                "title: 绿源会中问题单 打印版",
                "---",
                "# 绿源会中问题单 打印版",
                "",
                "这份问题单用于绿源会面准备，重点确认平台复用边界、轮库回应和下一轮方案包。",
            ]
        ),
        encoding="utf-8",
    )
    (twowheel_dir / "通用准备稿.md").write_text(
        "# 通用准备稿\n\n这是一份泛化的现场准备说明，不针对某个客户。\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()

    summary = run_targeted_reingest(
        db_path=str(db_path),
        planning_root=planning_root,
        queries=("绿源来访准备",),
        output_root=tmp_path / "artifacts",
        max_files_per_query=4,
        candidate_min_quality=0.6,
        live=True,
    )

    assert summary["selected_file_count"] >= 1
    assert summary["stats"]["docs_written"] >= 1
    assert summary["stats"]["atoms_written"] >= 1
    assert summary["stats"]["candidate_seeded"] >= 1

    conn = db.connect()
    row = conn.execute(
        """
        SELECT d.meta_json, a.promotion_status, a.scope_project
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        JOIN documents d ON d.doc_id = e.doc_id
        WHERE d.raw_ref LIKE '%绿源会中问题单%'
        LIMIT 1
        """
    ).fetchone()
    assert row is not None
    meta = json.loads(row["meta_json"])
    assert meta["planning_review"]["source_bucket"] == "planning_controlled"
    assert meta["planning_review"]["document_role"] == "controlled"
    assert row["promotion_status"] == "candidate"
    assert row["scope_project"] == "planning"
