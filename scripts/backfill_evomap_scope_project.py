#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.db import KnowledgeDB


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _count_blank_scope_project(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM atoms WHERE ifnull(scope_project, '') = ''"
        ).fetchone()[0]
    )


def _count_blank_scope_component(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM atoms WHERE ifnull(scope_component, '') = ''"
        ).fetchone()[0]
    )


def _backfill_scope_project_from_applicability(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """
        UPDATE atoms
        SET scope_project = json_extract(applicability, '$.project')
        WHERE ifnull(scope_project, '') = ''
          AND json_extract(applicability, '$.project') IS NOT NULL
          AND json_extract(applicability, '$.project') <> ''
        """
    )
    return int(cur.rowcount or 0)


def _backfill_scope_component_from_applicability(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """
        UPDATE atoms
        SET scope_component = COALESCE(
            json_extract(applicability, '$.scope_component'),
            json_extract(applicability, '$.component')
        )
        WHERE ifnull(scope_component, '') = ''
          AND COALESCE(
              json_extract(applicability, '$.scope_component'),
              json_extract(applicability, '$.component')
          ) IS NOT NULL
          AND COALESCE(
              json_extract(applicability, '$.scope_component'),
              json_extract(applicability, '$.component')
          ) <> ''
        """
    )
    return int(cur.rowcount or 0)


def _backfill_scope_project_from_documents(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """
        UPDATE atoms
        SET scope_project = (
            SELECT d.project
            FROM episodes e
            JOIN documents d ON d.doc_id = e.doc_id
            WHERE e.episode_id = atoms.episode_id
            LIMIT 1
        )
        WHERE ifnull(scope_project, '') = ''
          AND EXISTS (
              SELECT 1
              FROM episodes e
              JOIN documents d ON d.doc_id = e.doc_id
              WHERE e.episode_id = atoms.episode_id
                AND ifnull(d.project, '') <> ''
          )
        """
    )
    return int(cur.rowcount or 0)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill EvoMap atom scope_project/scope_component from applicability and document lineage."
    )
    parser.add_argument(
        "--db",
        default=resolve_evomap_knowledge_runtime_db_path(),
        help="Path to evomap knowledge SQLite DB.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply updates. Without this flag the script only reports current gaps.",
    )
    args = parser.parse_args()

    db_path = str(Path(args.db).expanduser().resolve())
    KnowledgeDB(db_path=db_path).init_schema()

    conn = _connect(db_path)
    try:
        before_blank_project = _count_blank_scope_project(conn)
        before_blank_component = _count_blank_scope_component(conn)

        if not args.write:
            print(
                {
                    "ok": True,
                    "mode": "dry_run",
                    "db": db_path,
                    "blank_scope_project": before_blank_project,
                    "blank_scope_component": before_blank_component,
                }
            )
            return 0

        applicability_project = _backfill_scope_project_from_applicability(conn)
        applicability_component = _backfill_scope_component_from_applicability(conn)
        lineage_project = _backfill_scope_project_from_documents(conn)
        conn.commit()

        after_blank_project = _count_blank_scope_project(conn)
        after_blank_component = _count_blank_scope_component(conn)
        print(
            {
                "ok": True,
                "mode": "write",
                "db": db_path,
                "updates": {
                    "scope_project_from_applicability": applicability_project,
                    "scope_project_from_documents": lineage_project,
                    "scope_component_from_applicability": applicability_component,
                },
                "remaining": {
                    "blank_scope_project": after_blank_project,
                    "blank_scope_component": after_blank_component,
                },
                "delta": {
                    "scope_project_filled": before_blank_project - after_blank_project,
                    "scope_component_filled": before_blank_component - after_blank_component,
                },
            }
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
