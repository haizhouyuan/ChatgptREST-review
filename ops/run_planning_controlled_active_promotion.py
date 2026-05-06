#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.groundedness_checker import weighted_groundedness_score
from chatgptrest.evomap.knowledge.retrieval import _planning_query_terms
from chatgptrest.evomap.knowledge.schema import PromotionStatus


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_controlled_active_promotion"
DEFAULT_SOURCE_BUCKET = "planning_controlled"
DEFAULT_MIN_QUALITY = 0.72
DEFAULT_MAX_PER_QUERY = 12

_NOISY_QUESTION_PATTERNS = (
    re.compile(r"memory\.capture", re.I),
    re.compile(r"回执"),
    re.compile(r"^如何"),
    re.compile(r"常见问题/注意事项"),
    re.compile(r"关键经验教训"),
    re.compile(r"提示词"),
    re.compile(r"Deepresearch", re.I),
    re.compile(r"短版正文"),
    re.compile(r"^P\d"),
    re.compile(r"Antigravity", re.I),
)


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _is_noisy_question(question: str) -> bool:
    text = str(question or "").strip()
    if not text:
        return True
    return any(pattern.search(text) for pattern in _NOISY_QUESTION_PATTERNS)


def _doc_groundedness(raw_ref: str, valid_from: float) -> tuple[float, dict[str, Any]]:
    path_exists = os.path.isfile(raw_ref)
    if not path_exists:
        return 0.0, {"path_exists": False, "staleness_score": 0.0}
    staleness_score = 1.0
    if valid_from > 0:
        try:
            mtime = os.path.getmtime(raw_ref)
        except OSError:
            mtime = None
        if mtime is None:
            staleness_score = 0.0
        elif mtime > valid_from:
            staleness_score = 0.5
    overall, weights = weighted_groundedness_score(
        path_score=1.0,
        service_score=0.0,
        staleness_score=staleness_score,
        code_symbol_score=0.0,
        profile_name="planning",
        has_paths=True,
        has_units=False,
        has_valid_from=valid_from > 0,
        has_code_symbols=False,
    )
    return overall, {"path_exists": True, "staleness_score": staleness_score, "weights": weights}


def _entity_match_score(
    query_hits: list[str],
    question: str,
    answer: str,
    raw_ref: str,
    *,
    title: str = "",
) -> int:
    if not query_hits:
        return 0
    haystack = "\n".join([title, question, answer[:600], raw_ref])
    terms = []
    for query in query_hits:
        terms.extend(_planning_query_terms(query))
    scored_terms = [term for term in dict.fromkeys(terms) if len(term.strip()) >= 2]
    return sum(1 for term in scored_terms if term in haystack)


def run_controlled_active_promotion(
    *,
    db_path: str,
    output_root: Path,
    min_quality: float,
    min_groundedness: float,
    max_per_query: int,
    live: bool,
) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    conn = _connect(db_path)
    rows = conn.execute(
        """
        SELECT
          a.atom_id,
          a.atom_type,
          a.question,
          a.answer,
          a.quality_auto,
          a.groundedness,
          a.valid_from,
          a.promotion_status,
          d.raw_ref,
          d.title,
          d.meta_json
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        JOIN documents d ON d.doc_id = e.doc_id
        WHERE d.source = 'planning'
          AND COALESCE(json_extract(d.meta_json, '$.planning_review.source_bucket'), '') = ?
          AND a.promotion_status = ?
          AND json_extract(d.meta_json, '$.targeted_reingest.query_hits') IS NOT NULL
        ORDER BY COALESCE(a.quality_auto, 0.0) DESC, a.atom_id
        """,
        (DEFAULT_SOURCE_BUCKET, PromotionStatus.CANDIDATE.value),
    ).fetchall()

    stats = Counter()
    promoted_by_query = Counter()
    promoted_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    per_query_kept = defaultdict(int)

    for row in rows:
        atom_id = str(row["atom_id"])
        question = str(row["question"] or "")
        answer = str(row["answer"] or "")
        raw_ref = str(row["raw_ref"] or "")
        quality_auto = float(row["quality_auto"] or 0.0)
        valid_from = float(row["valid_from"] or 0.0)
        atom_type = str(row["atom_type"] or "").strip().lower()
        try:
            meta = json.loads(str(row["meta_json"] or "{}"))
        except Exception:
            meta = {}
        query_hits = [
            str(item).strip()
            for item in list(dict(meta.get("targeted_reingest") or {}).get("query_hits") or [])
            if str(item).strip()
        ]
        stats["scanned"] += 1
        if atom_type not in {"qa", "decision"}:
            stats["skipped_atom_type"] += 1
            skipped_rows.append({"atom_id": atom_id, "reason": "atom_type", "question": question, "raw_ref": raw_ref})
            continue
        if quality_auto < min_quality:
            stats["skipped_quality"] += 1
            skipped_rows.append({"atom_id": atom_id, "reason": "quality", "question": question, "raw_ref": raw_ref})
            continue
        if _is_noisy_question(question):
            stats["skipped_question_shape"] += 1
            skipped_rows.append({"atom_id": atom_id, "reason": "question_shape", "question": question, "raw_ref": raw_ref})
            continue
        if _entity_match_score(query_hits, question, answer, raw_ref, title=str(row["title"] or "")) <= 0:
            stats["skipped_query_match"] += 1
            skipped_rows.append({"atom_id": atom_id, "reason": "query_match", "question": question, "raw_ref": raw_ref})
            continue
        primary_query = query_hits[0]
        if per_query_kept[primary_query] >= max_per_query:
            stats["skipped_query_cap"] += 1
            skipped_rows.append({"atom_id": atom_id, "reason": "query_cap", "question": question, "raw_ref": raw_ref})
            continue
        groundedness_score, grounding_meta = _doc_groundedness(raw_ref, valid_from)
        if groundedness_score < min_groundedness:
            stats["skipped_groundedness"] += 1
            skipped_rows.append({"atom_id": atom_id, "reason": "groundedness", "question": question, "raw_ref": raw_ref})
            continue

        per_query_kept[primary_query] += 1
        promoted_by_query[primary_query] += 1
        stats["eligible"] += 1
        promoted_rows.append(
            {
                "atom_id": atom_id,
                "query": primary_query,
                "question": question,
                "quality_auto": round(quality_auto, 6),
                "groundedness": round(groundedness_score, 6),
                "raw_ref": raw_ref,
            }
        )
        if live:
            reason = f"planning_controlled_active:{primary_query}"
            conn.execute(
                "UPDATE atoms SET promotion_status = ?, promotion_reason = ?, groundedness = ? WHERE atom_id = ?",
                (PromotionStatus.ACTIVE.value, reason, groundedness_score, atom_id),
            )
            conn.execute(
                """
                INSERT INTO promotion_audit
                (audit_id, atom_id, from_status, to_status, reason, actor, groundedness_result, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"pa_{uuid.uuid4().hex[:12]}",
                    atom_id,
                    PromotionStatus.CANDIDATE.value,
                    PromotionStatus.ACTIVE.value,
                    reason,
                    "planning_controlled_active_runner",
                    json.dumps(
                        {
                            "mode": "doc_grounded_targeted_controlled",
                            "groundedness_score": groundedness_score,
                            **grounding_meta,
                        },
                        ensure_ascii=False,
                    ),
                    time.time(),
                ),
            )
            stats["promoted"] += 1

    if live:
        conn.commit()
    after_counts = conn.execute(
        """
        SELECT
          SUM(CASE WHEN a.promotion_status='active' THEN 1 ELSE 0 END) AS active_atoms,
          SUM(CASE WHEN a.promotion_status='candidate' THEN 1 ELSE 0 END) AS candidate_atoms,
          SUM(CASE WHEN a.promotion_status='staged' THEN 1 ELSE 0 END) AS staged_atoms
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        JOIN documents d ON d.doc_id = e.doc_id
        WHERE d.source = 'planning'
          AND COALESCE(json_extract(d.meta_json, '$.planning_review.source_bucket'), '') = ?
        """,
        (DEFAULT_SOURCE_BUCKET,),
    ).fetchone()
    conn.close()

    summary = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if live else "dry_run",
        "db_path": str(db_path),
        "run_dir": str(run_dir),
        "selection": {
            "source_bucket": DEFAULT_SOURCE_BUCKET,
            "min_quality": min_quality,
            "min_groundedness": min_groundedness,
            "max_per_query": max_per_query,
        },
        "stats": dict(stats),
        "promoted_by_query": dict(promoted_by_query),
        "after_counts": {
            "active": int(after_counts["active_atoms"] or 0),
            "candidate": int(after_counts["candidate_atoms"] or 0),
            "staged": int(after_counts["staged_atoms"] or 0),
        },
        "artifacts": {
            "summary_json": str(run_dir / "summary.json"),
            "promoted_json": str(run_dir / "promoted.json"),
            "skipped_json": str(run_dir / "skipped.json"),
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "promoted.json").write_text(json.dumps(promoted_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "skipped.json").write_text(json.dumps(skipped_rows[:500], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "README.md").write_text(
        "\n".join(
            [
                "# Planning Controlled Active Promotion",
                "",
                f"- `mode`: `{summary['mode']}`",
                f"- `promoted`: `{stats.get('promoted', 0)}`",
                f"- `eligible`: `{stats.get('eligible', 0)}`",
                f"- `after_counts`: `{summary['after_counts']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote a narrow targeted planning_controlled slice to active with document-grounded gating.")
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--min-quality", type=float, default=DEFAULT_MIN_QUALITY)
    parser.add_argument("--min-groundedness", type=float, default=0.60)
    parser.add_argument("--max-per-query", type=int, default=DEFAULT_MAX_PER_QUERY)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    summary = run_controlled_active_promotion(
        db_path=args.db,
        output_root=Path(args.output_root),
        min_quality=float(args.min_quality),
        min_groundedness=float(args.min_groundedness),
        max_per_query=max(1, int(args.max_per_query)),
        live=bool(args.live),
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
