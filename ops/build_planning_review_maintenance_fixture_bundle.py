#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


FIELDNAMES = [
    "scenario",
    "doc_id",
    "title",
    "review_domain",
    "source_bucket",
    "document_role",
    "expected_check",
    "expected_status",
    "notes",
]


FIXTURES = [
    {
        "scenario": "allowlist_missing_live_atom",
        "doc_id": "doc_missing_live",
        "title": "缺 live atom 的 allowlist 文档",
        "review_domain": "business_104",
        "source_bucket": "planning_latest_output",
        "document_role": "service_candidate",
        "expected_check": "allowlist_live_coverage_ok",
        "expected_status": "false",
        "notes": "reviewed + allowlist, but no active/candidate atom should exist",
    },
    {
        "scenario": "stale_bootstrap_outside_allowlist",
        "doc_id": "doc_stale_bootstrap",
        "title": "脱离 allowlist 的旧 bootstrap 原子",
        "review_domain": "governance",
        "source_bucket": "planning_outputs",
        "document_role": "service_candidate",
        "expected_check": "bootstrap_allowlist_alignment_ok",
        "expected_status": "false",
        "notes": "active/candidate bootstrap atom exists for doc outside allowlist",
    },
    {
        "scenario": "latest_output_backlog_hotspot",
        "doc_id": "doc_latest_backlog",
        "title": "高优先最新产物 backlog",
        "review_domain": "strategy",
        "source_bucket": "planning_strategy",
        "document_role": "review_plane",
        "expected_check": "latest_output_backlog_within_backlog_ok",
        "expected_status": "true",
        "notes": "latest output remains unreviewed and should surface in backlog/priority audits",
    },
    {
        "scenario": "archive_only_should_not_enter_candidate_pool",
        "doc_id": "doc_archive_only",
        "title": "archive_only 文档不应进入 candidate pool",
        "review_domain": "reducer",
        "source_bucket": "planning_review_pack",
        "document_role": "archive_only",
        "expected_check": "candidate_pool_within_backlog_ok",
        "expected_status": "true",
        "notes": "archive_only rows are backlog but should be excluded from priority queue",
    },
]


def build_fixture_bundle(*, output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "fixture_summary.json").write_text(
        json.dumps(
            {
                "fixture_count": len(FIXTURES),
                "scenarios": [row["scenario"] for row in FIXTURES],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with (out / "fixture_cases.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(FIXTURES)

    (out / "README.md").write_text(
        "\n".join(
            [
                "# Planning Review Maintenance Fixture Bundle",
                "",
                "This bundle captures stable maintenance drift scenarios used by review-plane tooling tests.",
                "",
                "## Scenarios",
                "",
                *[
                    f"- `{row['scenario']}`: {row['notes']}"
                    for row in FIXTURES
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "ok": True,
        "output_dir": str(out),
        "fixture_count": len(FIXTURES),
        "files": [
            str(out / "fixture_summary.json"),
            str(out / "fixture_cases.tsv"),
            str(out / "README.md"),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a small fixture bundle for planning review maintenance drift scenarios.")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(build_fixture_bundle(output_dir=args.output_dir), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
