from __future__ import annotations

import csv
import json
from pathlib import Path

from ops.audit_planning_runtime_pack_sensitivity import audit_pack


def _write_pack(pack: Path, *, title: str = "执行计划") -> None:
    pack.mkdir(parents=True, exist_ok=True)
    with (pack / "docs.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["doc_id", "title", "raw_ref", "family_id", "review_domain", "source_bucket", "document_role", "final_bucket", "service_readiness", "is_latest_output", "updated_at", "updated_at_iso", "live_active_atoms", "live_candidate_atoms"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {
                "doc_id": "doc_a",
                "title": title,
                "raw_ref": "/a.md",
                "family_id": "",
                "review_domain": "business_104",
                "source_bucket": "planning_latest_output",
                "document_role": "service_candidate",
                "final_bucket": "service_candidate",
                "service_readiness": "high",
                "is_latest_output": 1,
                "updated_at": 1,
                "updated_at_iso": "2026-03-11T00:00:00+00:00",
                "live_active_atoms": 1,
                "live_candidate_atoms": 0,
            }
        )
    with (pack / "atoms.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["doc_id", "atom_id", "episode_id", "atom_type", "promotion_status", "promotion_reason", "quality_auto", "value_auto", "question", "canonical_question"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {
                "doc_id": "doc_a",
                "atom_id": "at_a",
                "episode_id": "ep_a",
                "atom_type": "procedure",
                "promotion_status": "active",
                "promotion_reason": "planning_bootstrap_review_verified",
                "quality_auto": 0.8,
                "value_auto": 0.5,
                "question": "执行步骤",
                "canonical_question": "执行步骤",
            }
        )


def test_audit_pack_passes_for_clean_pack(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    _write_pack(pack)
    out = tmp_path / "out"
    result = audit_pack(pack_dir=pack, output_dir=out)
    assert result["ok"] is True
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["flagged_docs"] == 0
    assert summary["flagged_atoms"] == 0


def test_audit_pack_flags_sensitive_title(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    _write_pack(pack, title="面试执行计划")
    out = tmp_path / "out"
    result = audit_pack(pack_dir=pack, output_dir=out)
    assert result["ok"] is False
    flagged = json.loads((out / "flagged_docs.json").read_text(encoding="utf-8"))
    assert flagged[0]["hits"] == ["面试"]


def test_audit_pack_respects_manual_review_approvals(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    _write_pack(pack)
    with (pack / "atoms.tsv").open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "doc_id",
                "atom_id",
                "episode_id",
                "atom_type",
                "promotion_status",
                "promotion_reason",
                "quality_auto",
                "value_auto",
                "question",
                "canonical_question",
            ],
            delimiter="\t",
        )
        writer.writerow(
            {
                "doc_id": "doc_a",
                "atom_id": "at_sensitive",
                "episode_id": "ep_sensitive",
                "atom_type": "qa",
                "promotion_status": "active",
                "promotion_reason": "planning_bootstrap_review_verified",
                "quality_auto": 0.8,
                "value_auto": 0.5,
                "question": "合同条款怎么约束",
                "canonical_question": "合同条款怎么约束",
            }
        )

    review_spec = tmp_path / "review.json"
    review_spec.write_text(
        json.dumps(
            {
                "atoms": [
                    {
                        "atom_id": "at_sensitive",
                        "disposition": "approved_for_internal_opt_in",
                        "reason": "manual review accepted this internal-only planning atom",
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    result = audit_pack(pack_dir=pack, output_dir=out, review_spec_path=review_spec)
    assert result["ok"] is True
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["flagged_atoms"] == 1
    assert summary["approved_flagged_atoms"] == 1
    assert summary["unresolved_flagged_atoms"] == 0
    approved = json.loads((out / "approved_flagged_atoms.json").read_text(encoding="utf-8"))
    assert approved[0]["atom_id"] == "at_sensitive"
