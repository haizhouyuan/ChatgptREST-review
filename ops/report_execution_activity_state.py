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

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _count_map(conn: sqlite3.Connection, sql: str) -> dict[str, int]:
    rows = conn.execute(sql).fetchall()
    return {str(row[0] or ""): int(row[1] or 0) for row in rows}


def report_state(*, db_path: str | Path) -> dict[str, Any]:
    conn = _connect(db_path)
    try:
        total_atoms = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM atoms
                WHERE promotion_reason = 'activity_ingest'
                """
            ).fetchone()[0]
            or 0
        )
        total_documents = int(
            conn.execute(
                """
                SELECT COUNT(DISTINCT d.doc_id)
                FROM atoms a
                JOIN episodes e ON e.episode_id = a.episode_id
                JOIN documents d ON d.doc_id = e.doc_id
                WHERE a.promotion_reason = 'activity_ingest'
                """
            ).fetchone()[0]
            or 0
        )
        total_episodes = int(
            conn.execute(
                """
                SELECT COUNT(DISTINCT e.episode_id)
                FROM atoms a
                JOIN episodes e ON e.episode_id = a.episode_id
                WHERE a.promotion_reason = 'activity_ingest'
                """
            ).fetchone()[0]
            or 0
        )
        sources = _count_map(
            conn,
            """
            SELECT d.source, COUNT(*)
            FROM atoms a
            JOIN episodes e ON e.episode_id = a.episode_id
            JOIN documents d ON d.doc_id = e.doc_id
            WHERE a.promotion_reason = 'activity_ingest'
            GROUP BY d.source
            ORDER BY COUNT(*) DESC, d.source
            """,
        )
        episode_types = _count_map(
            conn,
            """
            SELECT e.episode_type, COUNT(*)
            FROM atoms a
            JOIN episodes e ON e.episode_id = a.episode_id
            WHERE a.promotion_reason = 'activity_ingest'
            GROUP BY e.episode_type
            ORDER BY COUNT(*) DESC, e.episode_type
            """,
        )
        atom_types = _count_map(
            conn,
            """
            SELECT a.atom_type, COUNT(*)
            FROM atoms a
            WHERE a.promotion_reason = 'activity_ingest'
            GROUP BY a.atom_type
            ORDER BY COUNT(*) DESC, a.atom_type
            """,
        )
        promotion_status = _count_map(
            conn,
            """
            SELECT a.promotion_status, COUNT(*)
            FROM atoms a
            WHERE a.promotion_reason = 'activity_ingest'
            GROUP BY a.promotion_status
            ORDER BY COUNT(*) DESC, a.promotion_status
            """,
        )
        atom_status = _count_map(
            conn,
            """
            SELECT a.status, COUNT(*)
            FROM atoms a
            WHERE a.promotion_reason = 'activity_ingest'
            GROUP BY a.status
            ORDER BY COUNT(*) DESC, a.status
            """,
        )

        extension_fields = (
            "task_ref",
            "trace_id",
            "lane_id",
            "role_id",
            "adapter_id",
            "profile_id",
            "executor_kind",
        )
        extension_coverage: dict[str, int] = {}
        for field in extension_fields:
            extension_coverage[field] = int(
                conn.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM atoms
                    WHERE promotion_reason = 'activity_ingest'
                      AND COALESCE(json_extract(applicability, '$.{field}'), '') != ''
                    """
                ).fetchone()[0]
                or 0
            )

        missing_lineage_rows = conn.execute(
            """
            SELECT
              a.atom_id,
              a.canonical_question,
              d.source,
              json_extract(a.applicability, '$.task_ref') AS task_ref,
              json_extract(a.applicability, '$.trace_id') AS trace_id,
              json_extract(a.applicability, '$.lane_id') AS lane_id,
              json_extract(a.applicability, '$.role_id') AS role_id
            FROM atoms a
            JOIN episodes e ON e.episode_id = a.episode_id
            JOIN documents d ON d.doc_id = e.doc_id
            WHERE a.promotion_reason = 'activity_ingest'
              AND (
                COALESCE(json_extract(a.applicability, '$.task_ref'), '') = ''
                OR COALESCE(json_extract(a.applicability, '$.trace_id'), '') = ''
              )
            ORDER BY d.source, a.canonical_question, a.atom_id
            LIMIT 25
            """
        ).fetchall()
        missing_lineage = [
            {
                "atom_id": str(row["atom_id"]),
                "canonical_question": str(row["canonical_question"] or ""),
                "source": str(row["source"] or ""),
                "task_ref": str(row["task_ref"] or ""),
                "trace_id": str(row["trace_id"] or ""),
                "lane_id": str(row["lane_id"] or ""),
                "role_id": str(row["role_id"] or ""),
            }
            for row in missing_lineage_rows
        ]

        archive_atoms = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM atoms a
                JOIN episodes e ON e.episode_id = a.episode_id
                JOIN documents d ON d.doc_id = e.doc_id
                WHERE a.promotion_reason = 'activity_ingest'
                  AND d.source = 'agent_activity'
                """
            ).fetchone()[0]
            or 0
        )
        live_atoms = total_atoms - archive_atoms

        return {
            "db_path": str(db_path),
            "total_documents": total_documents,
            "total_episodes": total_episodes,
            "total_atoms": total_atoms,
            "archive_atoms": archive_atoms,
            "live_atoms": live_atoms,
            "sources": sources,
            "episode_types": episode_types,
            "atom_types": atom_types,
            "promotion_status": promotion_status,
            "atom_status": atom_status,
            "extension_coverage": extension_coverage,
            "missing_lineage_atoms": len(missing_lineage),
            "missing_lineage_examples": missing_lineage,
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report canonical execution-activity state from the EvoMap runtime DB."
    )
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    args = parser.parse_args()
    print(json.dumps(report_state(db_path=args.db), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
