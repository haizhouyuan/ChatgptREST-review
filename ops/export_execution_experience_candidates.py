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

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from ops.compose_execution_activity_review_decisions import KEEP_BUCKETS


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def export_candidates(*, db_path: str | Path, decisions_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    decision_rows = _read_tsv(Path(decisions_path))
    keep_rows = [row for row in decision_rows if row.get("final_bucket", "") in KEEP_BUCKETS]
    atom_ids = [row["atom_id"] for row in keep_rows]
    atom_lookup: dict[str, sqlite3.Row] = {}

    if atom_ids:
        conn = _connect(db_path)
        try:
            placeholders = ",".join("?" for _ in atom_ids)
            rows = conn.execute(
                f"""
                SELECT
                  a.atom_id,
                  a.answer,
                  a.canonical_question,
                  d.source,
                  e.episode_type
                FROM atoms a
                JOIN episodes e ON e.episode_id = a.episode_id
                JOIN documents d ON d.doc_id = e.doc_id
                WHERE a.atom_id IN ({placeholders})
                """,
                atom_ids,
            ).fetchall()
            atom_lookup = {str(row["atom_id"]): row for row in rows}
        finally:
            conn.close()

    candidates: list[dict[str, Any]] = []
    for row in keep_rows:
        atom = atom_lookup.get(row["atom_id"])
        canonical_question = row.get("canonical_question", "")
        if not canonical_question and atom is not None:
            canonical_question = str(atom["canonical_question"] or "")
        answer_preview = str(atom["answer"] or "")[:240] if atom else ""
        final_bucket = row.get("final_bucket", "")
        experience_kind = row.get("experience_kind", "") or final_bucket
        title = row.get("experience_title", "") or canonical_question
        summary = row.get("experience_summary", "") or answer_preview
        candidates.append(
            {
                "candidate_id": f"execxp_{row['atom_id']}",
                "atom_id": row["atom_id"],
                "lineage_family_id": row.get("lineage_family_id", ""),
                "lineage_status": row.get("lineage_status", ""),
                "task_ref": row.get("task_ref", ""),
                "trace_id": row.get("trace_id", ""),
                "source": row.get("source", "") or (str(atom["source"] or "") if atom else ""),
                "episode_type": row.get("episode_type", "") or (str(atom["episode_type"] or "") if atom else ""),
                "experience_kind": experience_kind,
                "title": title,
                "summary": summary,
                "reviewer": row.get("reviewer", ""),
                "review_notes": row.get("review_notes", ""),
            }
        )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = {
        "db_path": str(db_path),
        "decisions_path": str(decisions_path),
        "experience_candidates": len(candidates),
        "by_kind": {
            kind: sum(1 for row in candidates if row["experience_kind"] == kind)
            for kind in sorted({row["experience_kind"] for row in candidates})
        },
    }
    (out / "experience_candidates.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_tsv(
        out / "experience_candidates.tsv",
        candidates,
        [
            "candidate_id",
            "atom_id",
            "lineage_family_id",
            "lineage_status",
            "task_ref",
            "trace_id",
            "source",
            "episode_type",
            "experience_kind",
            "title",
            "summary",
            "reviewer",
            "review_notes",
        ],
    )
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "output_dir": str(out),
        "summary_path": str(out / "summary.json"),
        "experience_candidates": len(candidates),
        "files": [
            str(out / "experience_candidates.json"),
            str(out / "experience_candidates.tsv"),
            str(out / "summary.json"),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export review-backed execution experience candidates.")
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    result = export_candidates(db_path=args.db, decisions_path=args.decisions, output_dir=args.output_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
