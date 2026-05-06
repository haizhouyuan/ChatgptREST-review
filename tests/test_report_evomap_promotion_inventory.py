from __future__ import annotations

import json
import time
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode, PromotionStatus
from ops.report_evomap_promotion_inventory import build_promotion_inventory, write_promotion_inventory_artifacts


def _seed_db(path: Path) -> None:
    db = KnowledgeDB(str(path))
    db.init_schema()
    now = time.time()
    rows = [
        ("doc_planning_a", "planning", "planning", "ops review", PromotionStatus.STAGED.value, "", "planning", 1.0, {"planning_review": {"source_bucket": "planning_review_pack"}}),
        ("doc_planning_b", "planning", "planning", "bootstrap reviewed", PromotionStatus.ACTIVE.value, "planning_bootstrap_review_verified", "planning", now, {"planning_review": {"source_bucket": "planning_latest_output"}}),
        ("doc_openclaw_a", "openclaw", "shortmobility", "plugin sync", PromotionStatus.STAGED.value, "plugin_capture", "shortmobility", now, {}),
    ]
    for doc_id, source, project, title, promotion_status, promotion_reason, scope_project, valid_from, meta in rows:
        db.put_document(
            Document(
                doc_id=doc_id,
                source=source,
                project=project,
                raw_ref=f"/vol1/1000/projects/{project}/{doc_id}.md",
                title=title,
                meta_json=json.dumps(meta, ensure_ascii=False),
            )
        )
        db.put_episode(
            Episode(
                episode_id=f"ep_{doc_id}",
                doc_id=doc_id,
                episode_type="md_section",
                title=title,
                summary=title,
                start_ref=f"/{doc_id}.md",
                end_ref=f"/{doc_id}.md",
                time_start=1.0,
                time_end=1.0,
            )
        )
        db.put_atom(
            Atom(
                atom_id=f"at_{doc_id}",
                episode_id=f"ep_{doc_id}",
                atom_type="procedure",
                question=title,
                answer="answer",
                canonical_question=title,
                quality_auto=0.8,
                promotion_status=promotion_status,
                promotion_reason=promotion_reason,
                scope_project=scope_project,
                valid_from=valid_from,
            )
        )
    db.commit()
    db.close()


def test_build_promotion_inventory_reports_source_project_and_blockers(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)

    summary = build_promotion_inventory(db_path=db_path, top_n=10)

    assert summary["counts"]["atoms"] == 3
    assert summary["counts"]["active"] == 1
    assert summary["counts"]["staged"] == 2
    assert summary["counts"]["projects"] == 2
    assert summary["likely_blockers"]["blank_promotion_reason_staged_atoms"] == 1
    assert summary["likely_blockers"]["recent_staged_atoms"] == 1
    assert summary["likely_blockers"]["recent_blank_promotion_reason_staged_atoms"] == 0
    assert summary["rates"]["recent_blank_promotion_reason_ratio"] == 0.0
    assert summary["critical_rollout"]["source"] == "planning"
    assert summary["critical_rollout"]["counts"]["total"] == 2
    assert summary["critical_rollout"]["counts"]["servable"] == 1
    assert summary["critical_rollout"]["rates"]["servable_ratio"] == 0.5
    assert len(summary["critical_rollout"]["buckets_without_servable_atoms"]) == 1
    assert summary["critical_rollout"]["buckets_without_servable_atoms"][0]["bucket"] == "planning_review_pack"
    assert len(summary["critical_rollout"]["buckets_without_active_atoms"]) == 1
    assert any(row["source"] == "openclaw" for row in summary["likely_blockers"]["sources_without_active_atoms"])
    assert any(row["project"] == "shortmobility" for row in summary["likely_blockers"]["projects_without_active_atoms"])


def test_write_promotion_inventory_artifacts_writes_expected_files(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    summary = build_promotion_inventory(db_path=db_path, top_n=10)

    written = write_promotion_inventory_artifacts(summary, tmp_path / "out", "sample")

    assert len(written) == 5
    assert all(path.exists() for path in written)
    summary_json = json.loads((tmp_path / "out" / "promotion_inventory_sample.json").read_text(encoding="utf-8"))
    assert summary_json["counts"]["atoms"] == 3
    report = (tmp_path / "out" / "promotion_blockers_sample.md").read_text(encoding="utf-8")
    assert "Critical Rollout Buckets" in report
