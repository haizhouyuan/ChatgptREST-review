#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from ops.build_execution_activity_lineage_registry import build_lineage_registry, write_lineage_registry
from ops.build_execution_activity_review_bundle import build_bundle
from ops.build_execution_activity_review_scaffold import build_scaffold
from ops.compose_execution_activity_review_decisions import compose, next_versioned_decision_name
from ops.export_execution_activity_review_queue import build_review_queue
from ops.export_execution_experience_candidates import export_candidates
from ops.report_execution_activity_state import report_state


DEFAULT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "execution_activity_review_cycle"


def _new_cycle_dir(root: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = root / ts
    if not candidate.exists():
        return candidate
    idx = 1
    while True:
        candidate = root / f"{ts}_{idx:02d}"
        if not candidate.exists():
            return candidate
        idx += 1


def _decision_file(snapshot_dir: Path) -> Path | None:
    candidates = sorted(snapshot_dir.glob("execution_review_decisions_v*.tsv"))
    if candidates:
        return candidates[-1]
    path = snapshot_dir / "execution_review_decisions.tsv"
    if path.exists():
        return path
    return None


def _latest_decision_dir(root: Path, *, exclude: Path | None = None) -> Path | None:
    if not root.exists():
        return None
    candidates = [path for path in root.iterdir() if path.is_dir() and path != exclude and _decision_file(path)]
    candidates.sort(key=lambda path: path.name)
    return candidates[-1] if candidates else None


def run_cycle(
    *,
    db_path: str | Path,
    output_root: str | Path,
    limit: int = 1000,
    review_decisions_path: str | Path | None = None,
    base_decisions_path: str | Path | None = None,
) -> dict[str, Any]:
    out = _new_cycle_dir(Path(output_root))
    out.mkdir(parents=True, exist_ok=True)

    audit = report_state(db_path=db_path)
    (out / "state_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    queue = build_review_queue(db_path=db_path, limit=limit)
    (out / "review_queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lineage_report = build_lineage_registry(db_path=db_path, limit=limit)
    lineage_output = write_lineage_registry(lineage_report, out / "lineage")

    bundle = build_bundle(db_path=db_path, output_dir=out / "bundle", limit=limit)
    scaffold = build_scaffold(
        db_path=db_path,
        output_tsv=out / "bundle" / "review_decisions_template.tsv",
        limit=limit,
    )

    decision_source_dir = ""
    base_decision_file: Path | None
    if base_decisions_path:
        base_decision_file = Path(base_decisions_path)
    else:
        previous_dir = _latest_decision_dir(Path(output_root), exclude=out)
        base_decision_file = _decision_file(previous_dir) if previous_dir else None
        decision_source_dir = str(previous_dir) if previous_dir else ""

    merged_decisions_path = ""
    allowlist_path = ""
    compose_summary: dict[str, Any] = {}
    experience_summary: dict[str, Any] = {}
    if review_decisions_path:
        delta = Path(review_decisions_path)
        output_name = next_versioned_decision_name(base_decision_file)
        merged = out / output_name
        compose_summary = compose(base_decision_file if base_decision_file and base_decision_file.exists() else None, delta, merged)
        merged_decisions_path = str(merged)
        allowlist_path = str(Path(compose_summary["allowlist_path"]))
        experience_result = export_candidates(
            db_path=db_path,
            decisions_path=merged,
            output_dir=out / "experience",
        )
        experience_summary = {
            "output_dir": experience_result["output_dir"],
            "summary_path": experience_result["summary_path"],
            "experience_candidates": experience_result["experience_candidates"],
        }

    summary = {
        "db_path": str(db_path),
        "output_dir": str(out),
        "selected_atoms": queue["selected_atoms"],
        "audit_missing_lineage_atoms": audit["missing_lineage_atoms"],
        "lineage_families": lineage_report["summary"]["lineage_families"],
        "lineage_gap_atoms": lineage_report["summary"]["gap_atoms"],
        "lineage_dir": lineage_output["output_dir"],
        "bundle_dir": bundle["output_dir"],
        "scaffold_tsv": scaffold["output_tsv"],
        "decision_source_dir": decision_source_dir,
        "base_decisions_path": str(base_decision_file) if base_decision_file else "",
        "merged_decisions_path": merged_decisions_path,
        "allowlist_path": allowlist_path,
        "compose_summary": compose_summary,
        "experience_summary": experience_summary,
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the execution activity review maintenance cycle."
    )
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--output-root", default=str(DEFAULT_ROOT))
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--review-decisions", default="", help="Optional execution review decision TSV to merge into the latest baseline.")
    parser.add_argument("--base-decisions", default="", help="Optional full baseline decision TSV to overlay against.")
    args = parser.parse_args()

    summary = run_cycle(
        db_path=args.db,
        output_root=args.output_root,
        limit=args.limit,
        review_decisions_path=Path(args.review_decisions) if args.review_decisions else None,
        base_decisions_path=Path(args.base_decisions) if args.base_decisions else None,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
