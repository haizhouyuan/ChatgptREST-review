#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.evomap.knowledge.planning_review_plane import default_db_path


NOISE_TITLE_RE = re.compile(r"^(readme|runlog|request|answer|问pro|问 Pro|summary)", re.I)
HIGH_SIGNAL_BUCKETS = {
    "planning_latest_output": 5,
    "planning_outputs": 4,
    "planning_strategy": 4,
    "planning_budget": 4,
    "planning_kb": 3,
    "planning_skills": 3,
    "planning_aios": 3,
}


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
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
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _score_row(row: sqlite3.Row) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    bucket = str(row["source_bucket"] or "")
    title = str(row["title"] or "")
    raw_ref = str(row["raw_ref"] or "")
    role = str(row["document_role"] or "")
    latest_output = int(row["is_latest_output"] or 0)

    bucket_score = HIGH_SIGNAL_BUCKETS.get(bucket, 0)
    if bucket_score:
        score += bucket_score
        reasons.append(f"bucket:{bucket}")
    if latest_output:
        score += 2
        reasons.append("latest_output")
    if role == "service_candidate":
        score += 2
        reasons.append("role:service_candidate")
    elif role == "review_plane":
        score += 1
        reasons.append("role:review_plane")

    if NOISE_TITLE_RE.search(title.strip()):
        return 0, ["title:noise_excluded"]
    if raw_ref.lower().endswith("/readme.md"):
        return 0, ["path:readme_excluded"]
    if "/06_会话摘要/" in raw_ref:
        return 0, ["path:session_summary_excluded"]
    if "/_review_pack/" in raw_ref:
        score -= 2
        reasons.append("path:review_material")

    return score, reasons


def build_priority_queue(*, db_path: str | Path, limit: int = 100) -> dict[str, Any]:
    conn = _connect(db_path)
    rows = conn.execute(
        """
        SELECT
            d.doc_id,
            d.title,
            d.raw_ref,
            COALESCE(json_extract(d.meta_json, '$.planning_review.family_id'), '') AS family_id,
            COALESCE(json_extract(d.meta_json, '$.planning_review.review_domain'), '') AS review_domain,
            COALESCE(json_extract(d.meta_json, '$.planning_review.source_bucket'), '') AS source_bucket,
            COALESCE(json_extract(d.meta_json, '$.planning_review.document_role'), '') AS document_role,
            COALESCE(json_extract(d.meta_json, '$.planning_review.is_latest_output'), 0) AS is_latest_output
        FROM documents d
        WHERE d.source = 'planning'
          AND json_extract(d.meta_json, '$.planning_review.decision.final_bucket') IS NULL
          AND COALESCE(json_extract(d.meta_json, '$.planning_review.document_role'), '') NOT IN ('archive_only', 'controlled')
        ORDER BY d.updated_at DESC, d.doc_id
        """
    ).fetchall()
    conn.close()

    selected: list[dict[str, Any]] = []
    backlog_rows = 0
    for row in rows:
        score, reasons = _score_row(row)
        if score <= 0:
            continue
        backlog_rows += 1
        selected.append(
            {
                "doc_id": str(row["doc_id"]),
                "title": str(row["title"] or ""),
                "raw_ref": str(row["raw_ref"] or ""),
                "family_id": str(row["family_id"] or ""),
                "review_domain": str(row["review_domain"] or ""),
                "source_bucket": str(row["source_bucket"] or ""),
                "document_role": str(row["document_role"] or ""),
                "is_latest_output": int(row["is_latest_output"] or 0),
                "priority_score": score,
                "priority_reason": ",".join(reasons),
            }
        )
    selected.sort(
        key=lambda row: (
            -int(row["priority_score"]),
            row["review_domain"],
            row["source_bucket"],
            row["doc_id"],
        )
    )
    selected = selected[:limit]

    by_domain: dict[str, int] = {}
    by_bucket: dict[str, int] = {}
    for row in selected:
        by_domain[row["review_domain"]] = by_domain.get(row["review_domain"], 0) + 1
        by_bucket[row["source_bucket"]] = by_bucket.get(row["source_bucket"], 0) + 1

    return {
        "db_path": str(db_path),
        "selected_docs": len(selected),
        "candidate_pool_docs": backlog_rows,
        "by_domain": by_domain,
        "by_source_bucket": by_bucket,
        "rows": selected,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Planning Review Priority Bundle",
        "",
        "## Summary",
        "",
        f"- `db_path`: `{report['db_path']}`",
        f"- `selected_docs`: `{report['selected_docs']}`",
        f"- `candidate_pool_docs`: `{report['candidate_pool_docs']}`",
        "",
        "## By Domain",
        "",
    ]
    for key, value in sorted(report["by_domain"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## By Source Bucket", ""])
    for key, value in sorted(report["by_source_bucket"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Rows", ""])
    for row in report["rows"][:20]:
        lines.extend(
            [
                f"- `{row['doc_id']}` score=`{row['priority_score']}` `{row['source_bucket']}` `{row['review_domain']}`",
                f"  - title: `{row['title']}`",
                f"  - family: `{row['family_id']}`",
                f"  - reason: `{row['priority_reason']}`",
            ]
        )
    return "\n".join(lines) + "\n"


def build_bundle(*, db_path: str | Path, output_dir: str | Path, limit: int = 100) -> dict[str, Any]:
    report = build_priority_queue(db_path=db_path, limit=limit)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "review_queue.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_tsv(out / "review_queue.tsv", report["rows"])
    (out / "summary.json").write_text(
        json.dumps(
            {
                "db_path": report["db_path"],
                "selected_docs": report["selected_docs"],
                "candidate_pool_docs": report["candidate_pool_docs"],
                "by_domain": report["by_domain"],
                "by_source_bucket": report["by_source_bucket"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out / "README.md").write_text(_render_markdown(report), encoding="utf-8")
    return {
        "ok": True,
        "output_dir": str(out),
        "selected_docs": report["selected_docs"],
        "files": [
            str(out / "review_queue.json"),
            str(out / "review_queue.tsv"),
            str(out / "summary.json"),
            str(out / "README.md"),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic review priority bundle for planning backlog.")
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(build_bundle(db_path=args.db, output_dir=args.output_dir, limit=args.limit), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
