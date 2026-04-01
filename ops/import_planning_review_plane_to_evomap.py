#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgptrest.evomap.knowledge.planning_review_plane import (
    apply_bootstrap_allowlist,
    default_db_path,
    import_review_plane,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import planning review-plane snapshot into canonical EvoMap and apply bootstrap allowlist.")
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--snapshot-dir", required=True)
    parser.add_argument("--review-decisions")
    parser.add_argument("--apply-bootstrap", action="store_true")
    parser.add_argument("--allowlist", help="Defaults to bootstrap_active_allowlist.tsv under snapshot-dir when present.")
    parser.add_argument("--bootstrap-output-dir")
    parser.add_argument("--min-atom-quality", type=float, default=0.58)
    parser.add_argument("--groundedness-threshold", type=float, default=0.6)
    args = parser.parse_args()

    snapshot_dir = Path(args.snapshot_dir)
    decisions = Path(args.review_decisions) if args.review_decisions else None
    import_summary = import_review_plane(db_path=args.db, snapshot_dir=snapshot_dir, review_decisions_path=decisions)
    payload: dict[str, object] = {"ok": True, "import_summary": import_summary}

    if args.apply_bootstrap:
        allowlist = Path(args.allowlist) if args.allowlist else snapshot_dir / "bootstrap_active_allowlist.tsv"
        output_dir = Path(args.bootstrap_output_dir) if args.bootstrap_output_dir else snapshot_dir / "bootstrap_active"
        bootstrap_summary = apply_bootstrap_allowlist(
            db_path=args.db,
            allowlist_path=allowlist,
            output_dir=output_dir,
            min_atom_quality=args.min_atom_quality,
            groundedness_threshold=args.groundedness_threshold,
        )
        payload["bootstrap_summary"] = bootstrap_summary

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
