from __future__ import annotations

import csv
import json
from pathlib import Path

from ops.run_planning_runtime_pack_offline_validation import run_validation


def _write_pack(pack: Path) -> None:
    pack.mkdir(parents=True, exist_ok=True)
    docs_fields = [
        "doc_id",
        "title",
        "raw_ref",
        "family_id",
        "review_domain",
        "source_bucket",
        "document_role",
        "final_bucket",
        "service_readiness",
        "is_latest_output",
        "updated_at",
        "updated_at_iso",
        "live_active_atoms",
        "live_candidate_atoms",
    ]
    docs_rows = [
        {
            "doc_id": "doc_budget",
            "title": "2026预算关键数字汇总表",
            "raw_ref": "/budget.md",
            "family_id": "",
            "review_domain": "budget",
            "source_bucket": "planning_budget",
            "document_role": "service_candidate",
            "final_bucket": "service_candidate",
            "service_readiness": "high",
            "is_latest_output": 0,
            "updated_at": 1,
            "updated_at_iso": "2026-03-11T00:00:00+00:00",
            "live_active_atoms": 2,
            "live_candidate_atoms": 0,
        },
        {
            "doc_id": "doc_exec",
            "title": "104关节模组代工执行计划",
            "raw_ref": "/exec.md",
            "family_id": "",
            "review_domain": "business_104",
            "source_bucket": "planning_latest_output",
            "document_role": "review_plane",
            "final_bucket": "service_candidate",
            "service_readiness": "high",
            "is_latest_output": 1,
            "updated_at": 1,
            "updated_at_iso": "2026-03-11T00:00:00+00:00",
            "live_active_atoms": 2,
            "live_candidate_atoms": 0,
        },
    ]
    with (pack / "docs.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=docs_fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(docs_rows)
    atoms_fields = [
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
    ]
    with (pack / "atoms.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=atoms_fields, delimiter="\t")
        writer.writeheader()
        writer.writerow(
            {
                "doc_id": "doc_budget",
                "atom_id": "at_budget",
                "episode_id": "ep_budget",
                "atom_type": "procedure",
                "promotion_status": "active",
                "promotion_reason": "planning_bootstrap_review_verified",
                "quality_auto": 0.8,
                "value_auto": 0.5,
                "question": "预算关键数字是什么",
                "canonical_question": "预算关键数字是什么",
            }
        )


def test_run_validation_reports_hits(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    _write_pack(pack)
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "query_id": "budget",
                        "query": "预算关键数字",
                        "expected_review_domains": ["budget"],
                        "expected_source_buckets": ["planning_budget"],
                        "expected_title_tokens": ["预算", "关键数字"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    result = run_validation(pack_dir=pack, spec_path=spec, output_dir=out, top_k=3)
    assert result["ok"] is True
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["domain_hits"] == 1
    assert summary["bucket_hits"] == 1
    assert summary["token_hits"] == 1
