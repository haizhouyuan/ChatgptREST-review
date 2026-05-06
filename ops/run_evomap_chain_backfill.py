#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.chain_builder import (
    backfill_canonical_question,
    backfill_valid_from,
    build_chains,
)
from chatgptrest.evomap.knowledge.db import KnowledgeDB

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "evomap_chain_backfill"


def _metrics(db_path: str | Path) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        """
        SELECT
          COUNT(*) AS total_atoms,
          SUM(CASE WHEN valid_from IS NULL OR valid_from=0 THEN 1 ELSE 0 END) AS valid_from_missing,
          SUM(CASE WHEN canonical_question IS NULL OR trim(canonical_question)='' THEN 1 ELSE 0 END) AS canonical_missing,
          SUM(CASE WHEN chain_id IS NOT NULL AND trim(chain_id)!='' THEN 1 ELSE 0 END) AS chain_id_nonempty,
          SUM(CASE WHEN promotion_status='candidate' THEN 1 ELSE 0 END) AS candidate_atoms,
          SUM(CASE WHEN promotion_status='superseded' THEN 1 ELSE 0 END) AS superseded_atoms
        FROM atoms
        """
    ).fetchone()
    conn.close()
    return {
        "total_atoms": int(row[0] or 0),
        "valid_from_missing": int(row[1] or 0),
        "canonical_missing": int(row[2] or 0),
        "chain_id_nonempty": int(row[3] or 0),
        "candidate_atoms": int(row[4] or 0),
        "superseded_atoms": int(row[5] or 0),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_chain_backfill(
    *,
    db_path: str | Path,
    output_root: Path,
    live: bool,
    build_chains_mode: str,
    apply_promotion_semantics: bool | None = None,
) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    before = _metrics(db_path)

    target_db = Path(db_path)
    if not live:
        target_db = run_dir / "backfill_copy.db"
        shutil.copy2(db_path, target_db)

    db = KnowledgeDB(str(target_db))
    db.init_schema()
    valid_from_stats = backfill_valid_from(db)
    canonical_stats = backfill_canonical_question(db)
    db.close()
    after_backfill = _metrics(target_db)

    chain_target = ""
    chain_stats: dict[str, Any] | None = None
    chain_before: dict[str, int] | None = None
    chain_after: dict[str, int] | None = None

    if build_chains_mode != "skip":
        if build_chains_mode == "copy":
            chain_copy = run_dir / "chain_build_copy.db"
            shutil.copy2(target_db, chain_copy)
            chain_target = str(chain_copy)
        else:
            chain_target = str(target_db)

        if apply_promotion_semantics is None:
            apply_promotion_semantics = build_chains_mode != "live"

        chain_before = _metrics(chain_target)
        chain_db = KnowledgeDB(chain_target)
        chain_db.init_schema()
        chain_stats_obj = build_chains(
            chain_db,
            apply_promotion_semantics=bool(apply_promotion_semantics),
        )
        chain_db.close()
        chain_stats = asdict(chain_stats_obj)
        chain_after = _metrics(chain_target)

    summary = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if live else "dry_run",
        "db_path": str(db_path),
        "backfill_target_db": str(target_db),
        "build_chains_mode": build_chains_mode,
        "apply_promotion_semantics": bool(apply_promotion_semantics) if build_chains_mode != "skip" else None,
        "run_dir": str(run_dir),
        "metrics_before": before,
        "metrics_after_backfill": after_backfill,
        "valid_from_backfill": asdict(valid_from_stats),
        "canonical_backfill": asdict(canonical_stats),
        "chain_build_target": chain_target,
        "chain_metrics_before": chain_before,
        "chain_metrics_after": chain_after,
        "chain_build": chain_stats,
    }
    _write_json(run_dir / "summary.json", summary)
    readme = [
        "# EvoMap Chain Backfill",
        "",
        f"- `mode`: `{summary['mode']}`",
        f"- `build_chains_mode`: `{build_chains_mode}`",
        f"- `apply_promotion_semantics`: `{summary['apply_promotion_semantics']}`",
        f"- `valid_from_missing`: `{before['valid_from_missing']} -> {after_backfill['valid_from_missing']}`",
        f"- `canonical_missing`: `{before['canonical_missing']} -> {after_backfill['canonical_missing']}`",
        f"- `chain_id_nonempty`: `{before['chain_id_nonempty']}`",
    ]
    if chain_after is not None:
        readme.extend(
            [
                "",
                "## Chain Build",
                "",
                f"- `target`: `{chain_target}`",
                f"- `chain_id_nonempty`: `{chain_before['chain_id_nonempty']} -> {chain_after['chain_id_nonempty']}`",
                f"- `candidate_atoms`: `{chain_before['candidate_atoms']} -> {chain_after['candidate_atoms']}`",
                f"- `superseded_atoms`: `{chain_before['superseded_atoms']} -> {chain_after['superseded_atoms']}`",
            ]
        )
    (run_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill EvoMap valid_from/canonical_question and optionally build chains.")
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--live", action="store_true", help="Kept for contract parity; backfill always writes to target DB.")
    parser.add_argument(
        "--build-chains-mode",
        choices=("skip", "copy", "live"),
        default="copy",
        help="Run chain construction on a DB copy (default) or the live DB.",
    )
    parser.add_argument(
        "--apply-promotion-semantics",
        action="store_true",
        help="Allow build_chains to rewrite promotion_status/promotion_reason. Default is off for live chain apply.",
    )
    args = parser.parse_args()

    summary = run_chain_backfill(
        db_path=args.db,
        output_root=Path(args.output_root),
        live=args.live,
        build_chains_mode=args.build_chains_mode,
        apply_promotion_semantics=bool(args.apply_promotion_semantics) if args.build_chains_mode != "skip" else None,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
