#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.evomap.knowledge.planning_review_plane import default_db_path


DEFAULT_REFRESH_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_review_plane_refresh"


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _latest_allowlist(refresh_root: Path) -> Path | None:
    if not refresh_root.exists():
        return None
    candidates: list[Path] = []
    for snapshot_dir in refresh_root.iterdir():
        if not snapshot_dir.is_dir():
            continue
        candidates.extend(snapshot_dir.glob("planning_review_decisions_v*_allowlist.tsv"))
        candidates.extend(snapshot_dir.glob("planning_review_decisions_allowlist.tsv"))
    candidates.sort(key=lambda path: str(path))
    return candidates[-1] if candidates else None


def report_state(*, db_path: str | Path, allowlist_path: Path) -> dict[str, Any]:
    allow_rows = _read_tsv(allowlist_path)
    allow_doc_ids = {row["doc_id"] for row in allow_rows}
    conn = _connect(db_path)

    reviewed_docs = conn.execute(
        """
        SELECT COUNT(*)
        FROM documents
        WHERE source = 'planning'
          AND json_extract(meta_json, '$.planning_review.decision.final_bucket') IS NOT NULL
        """
    ).fetchone()[0]
    family_docs = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE source = 'planning_review_plane'"
    ).fetchone()[0]
    atom_status_rows = conn.execute(
        """
        SELECT a.promotion_status, COUNT(*) AS c
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        JOIN documents d ON d.doc_id = e.doc_id
        WHERE d.source = 'planning'
        GROUP BY a.promotion_status
        """
    ).fetchall()
    atom_status = {str(row["promotion_status"] or ""): int(row["c"] or 0) for row in atom_status_rows}

    docs_without_live_atoms = conn.execute(
        """
        SELECT d.doc_id, d.raw_ref, d.title
        FROM documents d
        WHERE d.source = 'planning'
          AND d.doc_id IN (
            SELECT value FROM json_each(?)
          )
          AND NOT EXISTS (
            SELECT 1
            FROM atoms a
            JOIN episodes e ON e.episode_id = a.episode_id
            WHERE e.doc_id = d.doc_id
              AND a.promotion_status IN ('active', 'candidate')
          )
        ORDER BY d.doc_id
        """,
        (json.dumps(sorted(allow_doc_ids), ensure_ascii=False),),
    ).fetchall()

    stale_live_atoms = conn.execute(
        """
        SELECT e.doc_id, a.atom_id, a.promotion_status, a.promotion_reason
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        JOIN documents d ON d.doc_id = e.doc_id
        WHERE d.source = 'planning'
          AND a.promotion_status IN ('active', 'candidate')
          AND a.promotion_reason LIKE 'planning_bootstrap%'
        ORDER BY e.doc_id, a.atom_id
        """
    ).fetchall()
    stale_live_rows = [
        {
            "doc_id": str(row["doc_id"]),
            "atom_id": str(row["atom_id"]),
            "promotion_status": str(row["promotion_status"] or ""),
            "promotion_reason": str(row["promotion_reason"] or ""),
        }
        for row in stale_live_atoms
        if str(row["doc_id"]) not in allow_doc_ids
    ]

    reviewed_but_unclassified = conn.execute(
        """
        SELECT COUNT(*)
        FROM documents
        WHERE source = 'planning'
          AND json_extract(meta_json, '$.planning_review.document_role') IS NOT NULL
          AND json_extract(meta_json, '$.planning_review.decision.final_bucket') IS NULL
        """
    ).fetchone()[0]
    conn.close()

    summary = {
        "db_path": str(db_path),
        "allowlist_path": str(allowlist_path),
        "allowlist_docs": len(allow_rows),
        "reviewed_docs": int(reviewed_docs or 0),
        "planning_review_plane_docs": int(family_docs or 0),
        "planning_atom_status": atom_status,
        "allowlist_docs_without_live_atoms": len(docs_without_live_atoms),
        "stale_live_atoms_outside_allowlist": len(stale_live_rows),
        "reviewed_but_unclassified_docs": int(reviewed_but_unclassified or 0),
        "docs_without_live_atoms": [
            {"doc_id": str(row["doc_id"]), "title": str(row["title"] or ""), "raw_ref": str(row["raw_ref"] or "")}
            for row in docs_without_live_atoms
        ],
        "stale_live_rows": stale_live_rows,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Report planning review-plane / bootstrap maintenance state from canonical EvoMap.")
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--allowlist", default="")
    parser.add_argument("--refresh-root", default=str(DEFAULT_REFRESH_ROOT))
    args = parser.parse_args()

    allowlist_path = Path(args.allowlist) if args.allowlist else _latest_allowlist(Path(args.refresh_root))
    if allowlist_path is None or not allowlist_path.exists():
        raise SystemExit("No allowlist file found. Pass --allowlist explicitly.")
    print(json.dumps(report_state(db_path=args.db, allowlist_path=allowlist_path), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
