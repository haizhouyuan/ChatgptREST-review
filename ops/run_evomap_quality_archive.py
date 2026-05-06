#!/usr/bin/env python3
"""Dry-run/apply archive workflow for obvious low-signal EvoMap atom families."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

from chatgptrest.evomap.knowledge.ingest_quality import classify_archive_families


DEFAULT_DB = Path("data/evomap_knowledge.db")
DEFAULT_STATUSES = ("staged", "candidate")


def collect_candidates(
    *,
    db_path: Path,
    statuses: tuple[str, ...] = DEFAULT_STATUSES,
    families: set[str] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in statuses)
        rows = conn.execute(
            f"""
            SELECT atom_id, question, canonical_question, answer, promotion_status, promotion_reason
            FROM atoms
            WHERE promotion_status IN ({placeholders})
            """,
            statuses,
        ).fetchall()
    finally:
        conn.close()

    candidates: list[dict[str, object]] = []
    family_counter: Counter[str] = Counter()
    for row in rows:
        row_dict = dict(row)
        row_families = classify_archive_families(row_dict)
        if families is not None:
            row_families = [family for family in row_families if family in families]
        if not row_families:
            continue
        family_counter.update(row_families)
        candidates.append(
            {
                "atom_id": row_dict["atom_id"],
                "promotion_status": row_dict["promotion_status"],
                "families": row_families,
                "question": row_dict["question"],
                "canonical_question": row_dict["canonical_question"],
            }
        )

    summary = {
        "db_path": str(db_path),
        "statuses": list(statuses),
        "candidate_count": len(candidates),
        "family_counts": dict(sorted(family_counter.items())),
    }
    return candidates, summary


def apply_archive(
    *,
    db_path: Path,
    candidates: list[dict[str, object]],
) -> dict[str, object]:
    if not candidates:
        return {"updated": 0, "families": {}}

    conn = sqlite3.connect(db_path)
    try:
        updated = 0
        family_counter: Counter[str] = Counter()
        for item in candidates:
            atom_id = str(item["atom_id"])
            families = [str(f) for f in list(item.get("families") or []) if str(f).strip()]
            family_counter.update(families)
            cursor = conn.execute(
                """
                UPDATE atoms
                SET promotion_status = 'archived',
                    promotion_reason = ?
                WHERE atom_id = ?
                  AND promotion_status IN ('staged', 'candidate')
                """,
                ("quality_archive:" + ",".join(families), atom_id),
            )
            updated += max(cursor.rowcount, 0)
        conn.commit()
        return {"updated": updated, "families": dict(sorted(family_counter.items()))}
    finally:
        conn.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to EvoMap knowledge DB")
    parser.add_argument("--family", action="append", dest="families", default=[], help="Limit to specific archive families")
    parser.add_argument("--apply", action="store_true", help="Apply archive updates instead of dry-run only")
    parser.add_argument("--output-json", default="", help="Optional path for JSON summary")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    db_path = Path(args.db).expanduser()
    families = {str(item).strip() for item in args.families if str(item).strip()} or None

    candidates, summary = collect_candidates(db_path=db_path, families=families)
    payload: dict[str, object] = {
        "ok": True,
        "mode": "apply" if args.apply else "dry_run",
        "summary": summary,
        "sample_candidates": candidates[:25],
    }
    if args.apply:
        payload["apply_result"] = apply_archive(db_path=db_path, candidates=candidates)

    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
