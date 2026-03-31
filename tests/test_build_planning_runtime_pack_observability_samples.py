from __future__ import annotations

import csv
import json
from pathlib import Path

from ops.build_planning_runtime_pack_observability_samples import build_samples


def _write_pack(pack: Path) -> None:
    pack.mkdir(parents=True, exist_ok=True)
    (pack / "manifest.json").write_text(
        json.dumps(
            {
                "pack_type": "planning_reviewed_runtime_pack_v1",
                "scope": {"opt_in_only": True, "default_runtime_cutover": False},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
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
                "title": "执行计划",
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
                "question": "执行计划是什么",
                "canonical_question": "执行计划是什么",
            }
        )


def test_build_samples_writes_expected_files(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    _write_pack(pack)
    out = tmp_path / "out"
    result = build_samples(pack_dir=pack, output_dir=out)
    assert result["ok"] is True
    assert result["sample_event_count"] == 5
    assert (out / "usage_event_samples.jsonl").exists()
    assert (out / "event_schema.json").exists()
    assert (out / "incident_template.md").exists()
    lines = (out / "usage_event_samples.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 5
