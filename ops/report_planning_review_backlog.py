#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.evomap.knowledge.planning_review_plane import default_db_path


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_pairs(rows: list[sqlite3.Row], key_name: str, value_name: str = "count") -> dict[str, int]:
    return {str(row[key_name] or ""): int(row[value_name] or 0) for row in rows}


def report_backlog(*, db_path: str | Path, top_n: int = 12) -> dict[str, Any]:
    conn = _connect(db_path)

    totals = conn.execute(
        """
        SELECT
            COUNT(*) AS total_docs,
            SUM(CASE WHEN json_extract(meta_json, '$.planning_review.document_role') IS NOT NULL THEN 1 ELSE 0 END) AS role_tagged_docs,
            SUM(CASE WHEN json_extract(meta_json, '$.planning_review.decision.final_bucket') IS NOT NULL THEN 1 ELSE 0 END) AS reviewed_docs,
            SUM(CASE WHEN json_extract(meta_json, '$.planning_review.decision.final_bucket') IS NULL THEN 1 ELSE 0 END) AS backlog_docs
        FROM documents
        WHERE source = 'planning'
        """
    ).fetchone()

    reviewed_by_bucket = conn.execute(
        """
        SELECT json_extract(meta_json, '$.planning_review.decision.final_bucket') AS final_bucket, COUNT(*) AS count
        FROM documents
        WHERE source = 'planning'
          AND json_extract(meta_json, '$.planning_review.decision.final_bucket') IS NOT NULL
        GROUP BY final_bucket
        ORDER BY count DESC, final_bucket
        """
    ).fetchall()

    backlog_by_domain = conn.execute(
        """
        SELECT json_extract(meta_json, '$.planning_review.review_domain') AS review_domain, COUNT(*) AS count
        FROM documents
        WHERE source = 'planning'
          AND json_extract(meta_json, '$.planning_review.decision.final_bucket') IS NULL
        GROUP BY review_domain
        ORDER BY count DESC, review_domain
        """
    ).fetchall()

    backlog_by_bucket = conn.execute(
        """
        SELECT json_extract(meta_json, '$.planning_review.source_bucket') AS source_bucket, COUNT(*) AS count
        FROM documents
        WHERE source = 'planning'
          AND json_extract(meta_json, '$.planning_review.decision.final_bucket') IS NULL
        GROUP BY source_bucket
        ORDER BY count DESC, source_bucket
        """
    ).fetchall()

    backlog_by_role = conn.execute(
        """
        SELECT json_extract(meta_json, '$.planning_review.document_role') AS document_role, COUNT(*) AS count
        FROM documents
        WHERE source = 'planning'
          AND json_extract(meta_json, '$.planning_review.decision.final_bucket') IS NULL
        GROUP BY document_role
        ORDER BY count DESC, document_role
        """
    ).fetchall()

    latest_output_backlog = conn.execute(
        """
        SELECT COUNT(*)
        FROM documents
        WHERE source = 'planning'
          AND json_extract(meta_json, '$.planning_review.decision.final_bucket') IS NULL
          AND json_extract(meta_json, '$.planning_review.is_latest_output') = 1
        """
    ).fetchone()[0]

    top_backlog_families = conn.execute(
        """
        SELECT
            COALESCE(json_extract(meta_json, '$.planning_review.family_id'), '') AS family_id,
            COALESCE(json_extract(meta_json, '$.planning_review.review_domain'), '') AS review_domain,
            COALESCE(json_extract(meta_json, '$.planning_review.source_bucket'), '') AS source_bucket,
            COUNT(*) AS count
        FROM documents
        WHERE source = 'planning'
          AND json_extract(meta_json, '$.planning_review.decision.final_bucket') IS NULL
        GROUP BY family_id, review_domain, source_bucket
        ORDER BY count DESC, family_id, review_domain, source_bucket
        LIMIT ?
        """,
        (int(top_n),),
    ).fetchall()

    sample_latest_output_backlog = conn.execute(
        """
        SELECT doc_id, title, raw_ref,
               COALESCE(json_extract(meta_json, '$.planning_review.family_id'), '') AS family_id,
               COALESCE(json_extract(meta_json, '$.planning_review.review_domain'), '') AS review_domain,
               COALESCE(json_extract(meta_json, '$.planning_review.source_bucket'), '') AS source_bucket
        FROM documents
        WHERE source = 'planning'
          AND json_extract(meta_json, '$.planning_review.decision.final_bucket') IS NULL
          AND json_extract(meta_json, '$.planning_review.is_latest_output') = 1
        ORDER BY updated_at DESC, doc_id
        LIMIT ?
        """,
        (int(top_n),),
    ).fetchall()
    conn.close()

    return {
        "db_path": str(db_path),
        "total_docs": int(totals["total_docs"] or 0),
        "role_tagged_docs": int(totals["role_tagged_docs"] or 0),
        "reviewed_docs": int(totals["reviewed_docs"] or 0),
        "backlog_docs": int(totals["backlog_docs"] or 0),
        "reviewed_by_bucket": _rows_to_pairs(reviewed_by_bucket, "final_bucket"),
        "backlog_by_domain": _rows_to_pairs(backlog_by_domain, "review_domain"),
        "backlog_by_source_bucket": _rows_to_pairs(backlog_by_bucket, "source_bucket"),
        "backlog_by_document_role": _rows_to_pairs(backlog_by_role, "document_role"),
        "latest_output_backlog_docs": int(latest_output_backlog or 0),
        "top_backlog_families": [
            {
                "family_id": str(row["family_id"] or ""),
                "review_domain": str(row["review_domain"] or ""),
                "source_bucket": str(row["source_bucket"] or ""),
                "count": int(row["count"] or 0),
            }
            for row in top_backlog_families
        ],
        "sample_latest_output_backlog": [
            {
                "doc_id": str(row["doc_id"]),
                "title": str(row["title"] or ""),
                "raw_ref": str(row["raw_ref"] or ""),
                "family_id": str(row["family_id"] or ""),
                "review_domain": str(row["review_domain"] or ""),
                "source_bucket": str(row["source_bucket"] or ""),
            }
            for row in sample_latest_output_backlog
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report planning review backlog outside the currently reviewed slice.")
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--top-n", type=int, default=12)
    args = parser.parse_args()
    print(json.dumps(report_backlog(db_path=args.db, top_n=args.top_n), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
