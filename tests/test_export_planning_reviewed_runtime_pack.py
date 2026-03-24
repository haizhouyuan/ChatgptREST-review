from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode, PromotionStatus
from ops.export_planning_reviewed_runtime_pack import export_runtime_pack


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
                    "raw_ref": f"/vol1/1000/projects/planning/{doc_id}.md",
                    "family_id": "fam",
                    "review_domain": "business_104",
                    "source_bucket": "planning_latest_output",
                    "avg_quality": "0.81",
                    "final_bucket": "service_candidate",
                    "service_readiness": "high",
                    "reviewers": "[]",
                }
            )


def _put_doc(
    db: KnowledgeDB,
    doc_id: str,
    *,
    reviewed: bool,
    promotion_statuses: list[str],
) -> None:
    meta = {
        "planning_review": {
            "family_id": "fam",
            "review_domain": "business_104",
            "source_bucket": "planning_latest_output",
            "document_role": "service_candidate",
            "is_latest_output": True,
            "decision": {
                "final_bucket": "service_candidate" if reviewed else None,
                "service_readiness": "high" if reviewed else None,
            },
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
    for idx, status in enumerate(promotion_statuses, start=1):
        db.put_atom(
            Atom(
                atom_id=f"at_{doc_id}_{idx}",
                episode_id=f"ep_{doc_id}",
                atom_type="procedure",
                question=f"{doc_id}-{idx}",
                answer="answer",
                canonical_question=f"{doc_id}-{idx}",
                quality_auto=0.82,
                promotion_status=status,
                promotion_reason="planning_bootstrap_review_verified_fast_path" if status in {PromotionStatus.ACTIVE.value, PromotionStatus.CANDIDATE.value} else "",
                valid_from=1.0,
            )
        )


def test_export_runtime_pack_includes_only_allowlist_and_live_atoms(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    _put_doc(db, "doc_keep", reviewed=True, promotion_statuses=[PromotionStatus.ACTIVE.value, PromotionStatus.STAGED.value])
    _put_doc(db, "doc_drop", reviewed=False, promotion_statuses=[PromotionStatus.STAGED.value])
    db.commit()
    db.close()

    allowlist = tmp_path / "allowlist.tsv"
    _write_allowlist(allowlist, ["doc_keep"])
    out = tmp_path / "pack"
    result = export_runtime_pack(db_path=db_path, allowlist_path=allowlist, output_dir=out)

    assert result["ok"] is True
    assert result["exported_docs"] == 1
    assert result["exported_atoms"] == 1

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["checks"]["exported_docs_match_allowlist_ok"] is True
    assert manifest["checks"]["staged_atoms_excluded_ok"] is True
    docs_tsv = (out / "docs.tsv").read_text(encoding="utf-8")
    atoms_tsv = (out / "atoms.tsv").read_text(encoding="utf-8")
    assert "doc_keep" in docs_tsv
    assert "doc_drop" not in docs_tsv
    assert "staged" not in atoms_tsv.lower()


def test_export_runtime_pack_raises_on_allowlist_live_drift(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    _put_doc(db, "doc_missing", reviewed=True, promotion_statuses=[PromotionStatus.STAGED.value])
    db.commit()
    db.close()

    allowlist = tmp_path / "allowlist.tsv"
    _write_allowlist(allowlist, ["doc_missing"])
    with pytest.raises(RuntimeError, match="requires clean allowlist/bootstrap alignment"):
        export_runtime_pack(db_path=db_path, allowlist_path=allowlist, output_dir=tmp_path / "pack")
