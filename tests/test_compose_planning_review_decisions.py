from __future__ import annotations

import csv
from pathlib import Path

from ops.compose_planning_review_decisions import compose


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
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
        writer.writerows(rows)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def test_compose_overlays_delta_and_rewrites_allowlist(tmp_path: Path) -> None:
    base = tmp_path / "base.tsv"
    delta = tmp_path / "delta.tsv"
    output = tmp_path / "merged.tsv"
    _write_rows(
        base,
        [
            {
                "doc_id": "d1",
                "title": "doc1",
                "raw_ref": "/doc1.md",
                "family_id": "f1",
                "review_domain": "strategy",
                "source_bucket": "planning_strategy",
                "avg_quality": "0.8",
                "final_bucket": "service_candidate",
                "service_readiness": "high",
                "reviewers": "[]",
            },
            {
                "doc_id": "d2",
                "title": "doc2",
                "raw_ref": "/doc2.md",
                "family_id": "f1",
                "review_domain": "budget",
                "source_bucket": "planning_budget",
                "avg_quality": "0.7",
                "final_bucket": "service_candidate",
                "service_readiness": "medium",
                "reviewers": "[]",
            },
        ],
    )
    _write_rows(
        delta,
        [
            {
                "doc_id": "d2",
                "title": "doc2",
                "raw_ref": "/doc2.md",
                "family_id": "f1",
                "review_domain": "budget",
                "source_bucket": "planning_budget",
                "avg_quality": "0.7",
                "final_bucket": "review_only",
                "service_readiness": "low",
                "reviewers": "[]",
            },
            {
                "doc_id": "d3",
                "title": "doc3",
                "raw_ref": "/doc3.md",
                "family_id": "f2",
                "review_domain": "governance",
                "source_bucket": "planning_kb",
                "avg_quality": "0.9",
                "final_bucket": "procedure",
                "service_readiness": "high",
                "reviewers": "[]",
            },
        ],
    )

    summary = compose(base, delta, output)
    merged = _read_rows(output)
    allowlist = _read_rows(output.with_name("merged_allowlist.tsv"))

    assert summary["base_docs"] == 2
    assert summary["delta_docs"] == 2
    assert summary["replaced_docs"] == 1
    assert summary["added_docs"] == 1
    assert summary["final_docs"] == 3
    assert {row["doc_id"] for row in merged} == {"d1", "d2", "d3"}
    assert {row["doc_id"] for row in allowlist} == {"d1", "d3"}
