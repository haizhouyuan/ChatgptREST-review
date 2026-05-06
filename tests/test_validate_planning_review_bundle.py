from __future__ import annotations

import csv
import json
from pathlib import Path

from ops.validate_planning_review_bundle import validate_bundle


def _write_bundle(bundle: Path) -> None:
    bundle.mkdir(parents=True, exist_ok=True)
    queue = {
        "db_path": "/tmp/evomap.db",
        "selected_docs": 2,
        "candidate_pool_docs": 5,
        "rows": [
            {
                "doc_id": "doc_a",
                "title": "A",
                "raw_ref": "/a.md",
                "family_id": "fam_a",
                "review_domain": "business_104",
                "source_bucket": "planning_latest_output",
                "document_role": "review_plane",
                "is_latest_output": 1,
                "priority_score": 8,
                "priority_reason": "x",
            },
            {
                "doc_id": "doc_b",
                "title": "B",
                "raw_ref": "/b.md",
                "family_id": "fam_b",
                "review_domain": "governance",
                "source_bucket": "planning_outputs",
                "document_role": "service_candidate",
                "is_latest_output": 0,
                "priority_score": 5,
                "priority_reason": "y",
            },
        ],
    }
    (bundle / "review_queue.json").write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")
    (bundle / "summary.json").write_text(
        json.dumps(
            {
                "db_path": "/tmp/evomap.db",
                "selected_docs": 2,
                "candidate_pool_docs": 5,
                "by_domain": {"business_104": 1, "governance": 1},
                "by_source_bucket": {"planning_latest_output": 1, "planning_outputs": 1},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (bundle / "README.md").write_text("# test\n", encoding="utf-8")
    queue_fields = [
        "doc_id",
        "title",
        "raw_ref",
        "family_id",
        "review_domain",
        "source_bucket",
        "document_role",
        "is_latest_output",
        "priority_score",
        "priority_reason",
    ]
    with (bundle / "review_queue.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=queue_fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(queue["rows"])
    scaffold_fields = queue_fields[:-1] + ["priority_reason", "suggested_bucket", "final_bucket", "reviewer", "review_notes"]
    with (bundle / "review_decisions_template.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "doc_id",
                "title",
                "raw_ref",
                "family_id",
                "review_domain",
                "source_bucket",
                "document_role",
                "priority_score",
                "priority_reason",
                "suggested_bucket",
                "final_bucket",
                "reviewer",
                "review_notes",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        for row in queue["rows"]:
            writer.writerow(
                {
                    "doc_id": row["doc_id"],
                    "title": row["title"],
                    "raw_ref": row["raw_ref"],
                    "family_id": row["family_id"],
                    "review_domain": row["review_domain"],
                    "source_bucket": row["source_bucket"],
                    "document_role": row["document_role"],
                    "priority_score": row["priority_score"],
                    "priority_reason": row["priority_reason"],
                    "suggested_bucket": "",
                    "final_bucket": "",
                    "reviewer": "",
                    "review_notes": "",
                }
            )


def test_validate_bundle_passes_for_consistent_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _write_bundle(bundle)
    result = validate_bundle(bundle_dir=bundle)
    assert result["ok"] is True
    assert all(result["checks"].values())
    assert result["selected_docs"] == 2


def test_validate_bundle_flags_missing_files(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    result = validate_bundle(bundle_dir=bundle)
    assert result["ok"] is False
    assert result["checks"]["required_files_ok"] is False
    assert "review_queue.json" in result["missing_files"]
