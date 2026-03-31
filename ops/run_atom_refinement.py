#!/usr/bin/env python3
"""Batch atom refinement via ChatgptREST LLM bridge.

Usage:
    # Dry run (show what would be refined):
    python3 ops/run_atom_refinement.py --dry-run

    # Refine first 10 atoms (validation):
    python3 ops/run_atom_refinement.py --limit 10

    # Refine all high-value atoms:
    python3 ops/run_atom_refinement.py --limit 500 --min-answer-chars 200

    # Use specific preset:
    python3 ops/run_atom_refinement.py --preset pro_extended --limit 50
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.atom_refiner import AtomRefiner, RefinerConfig
from chatgptrest.evomap.knowledge.chain_builder import run_p1_migration
from chatgptrest.evomap.knowledge.extractors.antigravity_extractor import (
    AntigravityExtractor,
)
from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("atom_refinement")

# ---------------------------------------------------------------------------
# Default DB path
# ---------------------------------------------------------------------------

_DEFAULT_DB = resolve_evomap_knowledge_runtime_db_path()


def _get_db(db_path: str) -> KnowledgeDB:
    """Get or create KnowledgeDB."""
    db = KnowledgeDB(db_path=db_path)
    db.connect()
    db.init_schema()
    return db


def _ensure_extraction(db: KnowledgeDB) -> None:
    """Run AntigravityExtractor if DB is empty."""
    conn = db.connect()
    atom_count = conn.execute("SELECT COUNT(*) FROM atoms").fetchone()[0]
    if atom_count == 0:
        logger.info("DB is empty, running AntigravityExtractor first...")
        ext = AntigravityExtractor(db)
        ext.extract_all()
        stats = db.stats()
        logger.info(
            "Extraction complete: docs=%d episodes=%d atoms=%d",
            stats.get("documents", 0),
            stats.get("episodes", 0),
            stats.get("atoms", 0),
        )
    else:
        logger.info("DB has %d atoms, skipping extraction", atom_count)


def _show_stats(db: KnowledgeDB, min_answer_chars: int = 100) -> None:
    """Show current atom statistics."""
    conn = db.connect()
    total = conn.execute("SELECT COUNT(*) FROM atoms").fetchone()[0]
    unrefined = conn.execute(
        "SELECT COUNT(*) FROM atoms WHERE canonical_question = '' OR canonical_question IS NULL"
    ).fetchone()[0]
    scored = conn.execute(
        "SELECT COUNT(*) FROM atoms WHERE status = 'scored'"
    ).fetchone()[0]
    refineable = conn.execute(
        """SELECT COUNT(*) FROM atoms
           WHERE (canonical_question = '' OR canonical_question IS NULL)
             AND LENGTH(answer) >= ?""",
        (min_answer_chars,),
    ).fetchone()[0]
    short_unrefined = conn.execute(
        """SELECT COUNT(*) FROM atoms
           WHERE (canonical_question = '' OR canonical_question IS NULL)
             AND LENGTH(answer) < ?""",
        (min_answer_chars,),
    ).fetchone()[0]
    
    print(f"\n{'='*60}")
    print(f"Atom Statistics:")
    print(f"  Total:     {total}")
    print(f"  Unrefined: {unrefined}")
    print(f"  Scored:    {scored}")
    print(f"  Refineable (>= {min_answer_chars} chars): {refineable}")
    print(f"  Short unrefined: {short_unrefined}")
    print(f"{'='*60}\n")


def _backup_db(db_path: str) -> str:
    """Create a timestamped DB backup before in-place migration."""
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.bak.{ts}"
    shutil.copy2(db_path, backup_path)
    logger.info("DB backup created at %s", backup_path)
    return backup_path


def _report_to_dict(report) -> dict:
    """Convert dataclass-like reports to plain JSON-serializable objects."""
    if hasattr(report, "__dict__"):
        data = {}
        for key, value in report.__dict__.items():
            if hasattr(value, "__dict__"):
                data[key] = _report_to_dict(value)
            else:
                data[key] = value
        return data
    return dict(report)


def _write_report(report_path: str | None, payload: dict) -> None:
    """Persist JSON report if a path is provided."""
    if not report_path:
        return
    dirpath = os.path.dirname(report_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
    logger.info("Wrote report to %s", report_path)


def _dry_run(db: KnowledgeDB, limit: int, min_chars: int) -> None:
    """Show what would be refined without actually doing it."""
    conn = db.connect()
    rows = conn.execute(
        """SELECT atom_id, question, LENGTH(answer) as alen, atom_type
           FROM atoms 
           WHERE (canonical_question = '' OR canonical_question IS NULL)
             AND LENGTH(answer) >= ?
           ORDER BY LENGTH(answer) DESC
           LIMIT ?""",
        (min_chars, limit),
    ).fetchall()
    
    print(f"\nWould refine {len(rows)} atoms (min_chars={min_chars}):\n")
    for i, r in enumerate(rows, 1):
        d = dict(r)
        print(f"  {i:3d}. [{d['atom_type']:16s}] ({d['alen']:4d} chars) {d['question'][:80]}")
    
    batches = (len(rows) + 9) // 10  # batch_size=10
    print(f"\n  → {batches} LLM calls needed (batch=10)")
    print(f"  → ~{batches} minutes at ~60s/call")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch atom refinement via ChatgptREST")
    parser.add_argument("--db", default=_DEFAULT_DB, help="KnowledgeDB path")
    parser.add_argument("--limit", type=int, default=10, help="Max atoms to refine")
    parser.add_argument("--batch-size", type=int, default=10, help="Atoms per LLM call")
    parser.add_argument("--min-answer-chars", type=int, default=100, help="Min answer length")
    parser.add_argument("--model", default="gpt-5.4", help="Codex model")
    parser.add_argument("--reasoning-effort", default="high", help="Reasoning effort: low/medium/high")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    parser.add_argument("--p1-migrate", action="store_true", help="Run P1 valid_from backfill + evolution chain migration after refinement")
    parser.add_argument("--p1-only", action="store_true", help="Run only P1 migration (skip refinement)")
    parser.add_argument("--report-json", default="", help="Write refine/P1 report JSON to this path")
    parser.add_argument("--no-backup", action="store_true", help="Skip DB backup before P1 migration")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:18711",
        help="(unused, legacy) ChatgptREST REST API is 18711; public MCP is 18712/mcp",
    )
    args = parser.parse_args()

    db = _get_db(args.db)
    _ensure_extraction(db)
    _show_stats(db, args.min_answer_chars)

    if args.dry_run:
        _dry_run(db, args.limit, args.min_answer_chars)
        return

    if args.p1_only and not args.p1_migrate:
        parser.error("--p1-only requires --p1-migrate")

    if args.p1_only:
        backup_path = ""
        if not args.no_backup:
            backup_path = _backup_db(args.db)
        report = run_p1_migration(db)
        payload = {
            "mode": "p1-only",
            "db": args.db,
            "backup_path": backup_path,
            "report": _report_to_dict(report),
        }
        _write_report(args.report_json or "", payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        _show_stats(db, args.min_answer_chars)
        return

    # Build LLM bridge (Codex CLI)
    from chatgptrest.evomap.knowledge.llm_bridge import CodexBridge, BridgeConfig

    bridge = CodexBridge(config=BridgeConfig(
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        min_call_interval=1.0,
    ))

    # Build refiner
    config = RefinerConfig(
        batch_size=args.batch_size,
        min_answer_chars=args.min_answer_chars,
    )
    refiner = AtomRefiner(db=db, llm_fn=bridge.call, config=config)

    logger.info(
        "Starting LLM refinement: limit=%d, batch=%d, model=%s reasoning=%s",
        args.limit, args.batch_size, args.model, args.reasoning_effort,
    )
    start = time.time()

    result = refiner.refine_all(limit=args.limit)

    elapsed = time.time() - start
    logger.info(
        "Refinement complete: refined=%d, skipped=%d, errors=%d in %.1fs",
        result.refined, result.skipped, result.errors, elapsed,
    )

    print(f"\n{'='*60}")
    print(f"Refinement Results:")
    print(f"  Refined: {result.refined}")
    print(f"  Skipped: {result.skipped}")
    print(f"  Errors:  {result.errors}")
    print(f"  Time:    {elapsed:.1f}s ({elapsed/60:.1f}m)")
    print(f"  Bridge:  {bridge.stats}")
    print(f"{'='*60}")

    if args.p1_migrate:
        backup_path = ""
        if not args.no_backup:
            backup_path = _backup_db(args.db)
        p1_report = run_p1_migration(db)
        payload = {
            "mode": "refine+p1",
            "db": args.db,
            "backup_path": backup_path,
            "refine": {
                "refined": result.refined,
                "skipped": result.skipped,
                "errors": result.errors,
                "elapsed_ms": result.elapsed_ms,
                "bridge": bridge.stats,
            },
            "p1": _report_to_dict(p1_report),
        }
        _write_report(args.report_json or "", payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

    _show_stats(db, args.min_answer_chars)


if __name__ == "__main__":
    main()
