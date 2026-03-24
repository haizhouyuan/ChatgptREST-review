from __future__ import annotations

import csv
import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode, PromotionStatus
from ops.report_planning_review_state import report_state


def _write_allowlist(path: Path, doc_ids: list[str]) -> None:
    fieldnames = [
        "doc_id",
        "title",
        "raw_ref",
        "family_id",
        "review_domain",
        "source_bucket",
        "avg_quality",
        "final_bucket",
        "service_readiness",
        "reviewers",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for doc_id in doc_ids:
            writer.writerow(
                {
                    "doc_id": doc_id,
                    "title": doc_id,
                    "raw_ref": f"/{doc_id}.md",
                    "family_id": "fam",
                    "review_domain": "strategy",
                    "source_bucket": "planning_latest_output",
                    "avg_quality": "0.8",
                    "final_bucket": "service_candidate",
                    "service_readiness": "high",
                    "reviewers": "[]",
                }
            )


def test_report_state_detects_bootstrap_drift(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()

    docs = [
        ("doc_keep", PromotionStatus.ACTIVE.value, "planning_bootstrap_review_verified_fast_path"),
        ("doc_missing", PromotionStatus.STAGED.value, ""),
        ("doc_stale", PromotionStatus.ACTIVE.value, "planning_bootstrap_review_verified_fast_path"),
    ]
    for doc_id, promotion_status, promotion_reason in docs:
        meta = {
            "planning_review": {
                "document_role": "service_candidate",
                "decision": {"final_bucket": "service_candidate"},
            }
        }
        db.put_document(
            Document(
                doc_id=doc_id,
                source="planning",
                project="planning",
                raw_ref=f"/vol1/1000/projects/planning/{doc_id}.md",
                title=doc_id,
                meta_json=json.dumps(meta, ensure_ascii=False),
            )
        )
        db.put_episode(
            Episode(
                episode_id=f"ep_{doc_id}",
                doc_id=doc_id,
                episode_type="md_section",
                title=doc_id,
                summary=doc_id,
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
                question=doc_id,
                answer="answer",
                canonical_question=doc_id,
                quality_auto=0.8,
                promotion_status=promotion_status,
                promotion_reason=promotion_reason,
                valid_from=1.0,
            )
        )

    db.put_document(
        Document(
            doc_id="doc_family",
            source="planning_review_plane",
            project="planning",
            raw_ref="planning://family/fam",
            title="family",
            meta_json="{}",
        )
    )
    db.commit()
    db.close()

    allowlist = tmp_path / "allowlist.tsv"
    _write_allowlist(allowlist, ["doc_keep", "doc_missing"])
    summary = report_state(db_path=db_path, allowlist_path=allowlist)

    assert summary["allowlist_docs"] == 2
    assert summary["reviewed_docs"] == 3
    assert summary["planning_review_plane_docs"] == 1
    assert summary["planning_atom_status"]["active"] == 2
    assert summary["allowlist_docs_without_live_atoms"] == 1
    assert summary["stale_live_atoms_outside_allowlist"] == 1
    assert summary["docs_without_live_atoms"][0]["doc_id"] == "doc_missing"
    assert summary["stale_live_rows"][0]["doc_id"] == "doc_stale"
