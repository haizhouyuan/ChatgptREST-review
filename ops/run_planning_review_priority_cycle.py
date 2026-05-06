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

from chatgptrest.evomap.knowledge.planning_review_plane import default_db_path
from ops.build_planning_review_priority_bundle import build_bundle, build_priority_queue
from ops.build_planning_review_scaffold import build_scaffold
from ops.report_planning_review_backlog import report_backlog
from ops.report_planning_review_consistency import report_consistency
from ops.report_planning_review_state import DEFAULT_REFRESH_ROOT, report_state


DEFAULT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_review_priority_cycle"


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


def run_cycle(
    *,
    db_path: str | Path,
    output_root: str | Path,
    allowlist_path: str | Path | None = None,
    refresh_root: str | Path = DEFAULT_REFRESH_ROOT,
    limit: int = 100,
    require_consistent: bool = False,
) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(output_root) / ts
    out.mkdir(parents=True, exist_ok=True)

    resolved_allowlist = Path(allowlist_path) if allowlist_path else _latest_allowlist(Path(refresh_root))
    if resolved_allowlist is None:
        raise FileNotFoundError("No planning allowlist found. Pass --allowlist explicitly.")

    state = report_state(db_path=db_path, allowlist_path=resolved_allowlist)
    backlog = report_backlog(db_path=db_path, top_n=max(limit, 12))
    queue = build_priority_queue(db_path=db_path, limit=limit)
    consistency = report_consistency(
        db_path=db_path,
        allowlist_path=resolved_allowlist,
        top_n=max(limit, 12),
        limit=limit,
    )

    (out / "state_audit.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "backlog_audit.json").write_text(json.dumps(backlog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "review_queue.json").write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "consistency_audit.json").write_text(json.dumps(consistency, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    bundle = build_bundle(db_path=db_path, output_dir=out / "bundle", limit=limit)
    scaffold = build_scaffold(
        db_path=db_path,
        output_tsv=out / "bundle" / "review_decisions_template.tsv",
        limit=limit,
    )

    summary = {
        "db_path": str(db_path),
        "allowlist_path": str(resolved_allowlist),
        "output_dir": str(out),
        "reviewed_docs": state["reviewed_docs"],
        "backlog_docs": backlog["backlog_docs"],
        "selected_docs": queue["selected_docs"],
        "latest_output_backlog_docs": backlog["latest_output_backlog_docs"],
        "consistency_ok": consistency["ok"],
        "bundle_dir": bundle["output_dir"],
        "scaffold_tsv": scaffold["output_tsv"],
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if require_consistent and not consistency["ok"]:
        raise RuntimeError(f"Planning review consistency drift detected. See {out / 'consistency_audit.json'}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the planning priority review maintenance cycle.")
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--output-root", default=str(DEFAULT_ROOT))
    parser.add_argument("--allowlist", default="")
    parser.add_argument("--refresh-root", default=str(DEFAULT_REFRESH_ROOT))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--require-consistent", action="store_true")
    args = parser.parse_args()

    summary = run_cycle(
        db_path=args.db,
        output_root=args.output_root,
        allowlist_path=Path(args.allowlist) if args.allowlist else None,
        refresh_root=args.refresh_root,
        limit=args.limit,
        require_consistent=args.require_consistent,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
