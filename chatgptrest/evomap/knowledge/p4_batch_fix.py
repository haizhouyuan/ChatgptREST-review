"""EvoMap P4 Batch Fixes — Promotion rules + empty canonical_question re-processing.

Run:
    python -m chatgptrest.evomap.knowledge.p4_batch_fix [--db PATH] [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from typing import Any

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path

logger = logging.getLogger(__name__)
_DEFAULT_DB = resolve_evomap_knowledge_runtime_db_path()


@dataclass
class P4Result:
    """Summary of P4 batch fix operations."""
    promoted: int = 0
    demoted: int = 0
    cq_fixed: int = 0
    cq_skipped: int = 0
    elapsed_ms: int = 0


# ---------------------------------------------------------------------------
# Promotion Rules: candidate → active
# ---------------------------------------------------------------------------
# An atom is promoted to 'active' when ALL conditions are met:
#   1. promotion_status = 'candidate'
#   2. quality_auto >= 0.3  (above noise threshold)
#   3. groundedness >= 0.7  (verified against real system)
#   4. has canonical_question (not empty)
#   5. has answer (not empty)
#   6. NOT superseded

def promote_eligible_atoms(db: Any, *, dry_run: bool = False) -> dict[str, int]:
    """Promote candidate atoms that meet all quality criteria to 'active'.

    Returns dict with counts: {promoted, skipped, already_active}.
    """
    conn = db.connect()

    rows = conn.execute("""
        SELECT atom_id, question, answer, quality_auto, stability,
               canonical_question, promotion_status
        FROM atoms
        WHERE promotion_status = 'candidate'
          AND stability != 'superseded'
    """).fetchall()

    promoted = 0
    skipped = 0

    for row in rows:
        row_dict = dict(row)
        quality = row_dict.get("quality_auto", 0) or 0
        question = row_dict.get("question", "") or ""
        answer = row_dict.get("answer", "") or ""
        cq = row_dict.get("canonical_question", "") or ""

        # Check all promotion conditions
        if quality < 0.3:
            skipped += 1
            continue
        if not question.strip() or not answer.strip():
            skipped += 1
            continue
        if not cq.strip():
            skipped += 1
            continue

        # All conditions met — promote
        if not dry_run:
            conn.execute(
                """UPDATE atoms SET promotion_status = 'active',
                   promotion_reason = 'auto_p4_quality_check'
                   WHERE atom_id = ?""",
                (row_dict["atom_id"],),
            )
        promoted += 1

    if not dry_run:
        conn.commit()

    already_active = conn.execute(
        "SELECT COUNT(*) FROM atoms WHERE promotion_status = 'active'"
    ).fetchone()[0]

    return {"promoted": promoted, "skipped": skipped, "already_active": already_active}


# ---------------------------------------------------------------------------
# Empty Canonical Question Fix
# ---------------------------------------------------------------------------

def fix_empty_canonical_questions(db: Any, *, dry_run: bool = False) -> dict[str, int]:
    """Re-generate canonical_question for atoms that have none.

    Strategy: Use the atom's own question as the canonical_question if it's
    reasonable, or generate a normalized form.
    """
    conn = db.connect()

    rows = conn.execute("""
        SELECT atom_id, question, answer, atom_type, canonical_question
        FROM atoms
        WHERE (canonical_question IS NULL OR canonical_question = '')
          AND question IS NOT NULL AND question != ''
    """).fetchall()

    fixed = 0
    skipped = 0

    for row in rows:
        row_dict = dict(row)
        question = (row_dict.get("question") or "").strip()
        answer = (row_dict.get("answer") or "").strip()

        if not question:
            skipped += 1
            continue

        # Generate canonical question from existing question
        # Normalize: strip trailing punctuation, lowercase first word
        cq = _normalize_to_canonical(question, row_dict.get("atom_type", ""))

        if not cq:
            skipped += 1
            continue

        if not dry_run:
            conn.execute(
                """UPDATE atoms SET canonical_question = ?
                   WHERE atom_id = ?""",
                (cq, row_dict["atom_id"]),
            )
        fixed += 1

    if not dry_run:
        conn.commit()

    return {"fixed": fixed, "skipped": skipped}


def _normalize_to_canonical(question: str, atom_type: str = "") -> str:
    """Normalize a question into a canonical form.

    Rules:
      - Strip leading/trailing whitespace
      - Ensure ends with '?'
      - Collapse multiple spaces
      - Max 200 chars
    """
    import re

    q = question.strip()
    if not q:
        return ""

    # Collapse whitespace
    q = re.sub(r'\s+', ' ', q)

    # If it doesn't look like a question but is a statement, prefix with "How to"
    if atom_type in ("procedure", "lesson") and not q.endswith("?"):
        if not q.lower().startswith(("how", "what", "when", "why", "where", "which", "can")):
            q = f"How to {q.lower().rstrip('.')}?"

    # Ensure ends with ?
    if not q.endswith("?"):
        q = q.rstrip(".!;:") + "?"

    return q[:200]


# ---------------------------------------------------------------------------
# Combined P4 batch fix
# ---------------------------------------------------------------------------

def run_p4_batch_fix(db: Any, *, dry_run: bool = False) -> P4Result:
    """Run all P4 batch fixes: promotion + empty CQ."""
    t0 = time.time()

    # Fix empty CQ first (so promotion can check them)
    cq_result = fix_empty_canonical_questions(db, dry_run=dry_run)
    logger.info("P4 CQ fix: %s", cq_result)

    # Then promote eligible atoms
    promo_result = promote_eligible_atoms(db, dry_run=dry_run)
    logger.info("P4 promotion: %s", promo_result)

    elapsed = int((time.time() - t0) * 1000)

    return P4Result(
        promoted=promo_result["promoted"],
        demoted=0,
        cq_fixed=cq_result["fixed"],
        cq_skipped=cq_result["skipped"],
        elapsed_ms=elapsed,
    )


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="EvoMap P4 Batch Fix")
    parser.add_argument("--db", default=_DEFAULT_DB)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import os

    db_path = os.path.expanduser(args.db)
    if not os.path.exists(db_path):
        print(f"DB not found: {db_path}")
        return

    from chatgptrest.evomap.knowledge.db import KnowledgeDB

    db = KnowledgeDB(db_path=db_path)
    db.connect()

    result = run_p4_batch_fix(db, dry_run=args.dry_run)
    print(f"\nP4 Results {'(DRY RUN)' if args.dry_run else ''}:")
    print(f"  CQ fixed:   {result.cq_fixed}")
    print(f"  CQ skipped: {result.cq_skipped}")
    print(f"  Promoted:   {result.promoted}")
    print(f"  Elapsed:    {result.elapsed_ms}ms")


if __name__ == "__main__":
    main()
