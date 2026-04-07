#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.evomap.knowledge.planning_review_plane import default_db_path
from ops.build_planning_review_priority_bundle import build_priority_queue
from ops.report_planning_review_backlog import report_backlog
from ops.report_planning_review_state import DEFAULT_REFRESH_ROOT, report_state


def _latest_allowlist(refresh_root: Path) -> Path | None:
    candidates: list[Path] = []
    if refresh_root.exists():
        for snapshot_dir in refresh_root.iterdir():
            if not snapshot_dir.is_dir():
                continue
            candidates.extend(snapshot_dir.glob("planning_review_decisions_v*_allowlist.tsv"))
            candidates.extend(snapshot_dir.glob("planning_review_decisions_allowlist.tsv"))
    candidates.sort(key=lambda path: str(path))
    return candidates[-1] if candidates else None


def report_consistency(
    *,
    db_path: str | Path,
    allowlist_path: str | Path,
    top_n: int = 12,
    limit: int = 100,
) -> dict[str, Any]:
    state = report_state(db_path=db_path, allowlist_path=Path(allowlist_path))
    backlog = report_backlog(db_path=db_path, top_n=top_n)
    queue = build_priority_queue(db_path=db_path, limit=limit)

    live_atom_status = state.get("planning_atom_status", {})
    checks = {
        "reviewed_backlog_partition_ok": int(backlog["reviewed_docs"]) + int(backlog["backlog_docs"]) == int(backlog["total_docs"]),
        "allowlist_subset_of_reviewed_ok": int(state["allowlist_docs"]) <= int(state["reviewed_docs"]),
        "allowlist_live_coverage_ok": int(state["allowlist_docs_without_live_atoms"]) == 0,
        "bootstrap_allowlist_alignment_ok": int(state["stale_live_atoms_outside_allowlist"]) == 0,
        "priority_queue_within_candidate_pool_ok": int(queue["selected_docs"]) <= int(queue["candidate_pool_docs"]),
        "candidate_pool_within_backlog_ok": int(queue["candidate_pool_docs"]) <= int(backlog["backlog_docs"]),
        "latest_output_backlog_within_backlog_ok": int(backlog["latest_output_backlog_docs"]) <= int(backlog["backlog_docs"]),
    }

    return {
        "db_path": str(db_path),
        "allowlist_path": str(allowlist_path),
        "allowlist_docs": int(state["allowlist_docs"]),
        "reviewed_docs": int(backlog["reviewed_docs"]),
        "backlog_docs": int(backlog["backlog_docs"]),
        "total_docs": int(backlog["total_docs"]),
        "candidate_pool_docs": int(queue["candidate_pool_docs"]),
        "selected_docs": int(queue["selected_docs"]),
        "latest_output_backlog_docs": int(backlog["latest_output_backlog_docs"]),
        "live_active_atoms": int(live_atom_status.get("active", 0)),
        "live_candidate_atoms": int(live_atom_status.get("candidate", 0)),
        "live_staged_atoms": int(live_atom_status.get("staged", 0)),
        "checks": checks,
        "ok": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit planning review maintenance consistency across reviewed slice, backlog, and bootstrap live atoms.")
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--allowlist", default="")
    parser.add_argument("--refresh-root", default=str(DEFAULT_REFRESH_ROOT))
    parser.add_argument("--top-n", type=int, default=12)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    allowlist_path = Path(args.allowlist) if args.allowlist else _latest_allowlist(Path(args.refresh_root))
    if allowlist_path is None or not allowlist_path.exists():
        raise SystemExit("No allowlist file found. Pass --allowlist explicitly.")
    print(
        json.dumps(
            report_consistency(
                db_path=args.db,
                allowlist_path=allowlist_path,
                top_n=args.top_n,
                limit=args.limit,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
