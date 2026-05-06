#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgptrest.evomap.knowledge.planning_review_plane import DEFAULT_LINEAGE_DIR, DEFAULT_PACKAGE_DIR, default_db_path
from chatgptrest.evomap.knowledge.planning_review_refresh import DEFAULT_BASELINE_ROOT, run_refresh


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a new planning review-plane snapshot and compare it to the previous snapshot.")
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--package-dir", default=str(DEFAULT_PACKAGE_DIR))
    parser.add_argument("--lineage-dir", default=str(DEFAULT_LINEAGE_DIR))
    parser.add_argument("--baseline-root", default=str(DEFAULT_BASELINE_ROOT))
    parser.add_argument("--output-root", default="artifacts/monitor/planning_review_plane_refresh")
    args = parser.parse_args()

    payload = run_refresh(
        db_path=args.db,
        package_dir=Path(args.package_dir),
        lineage_dir=Path(args.lineage_dir),
        baseline_root=Path(args.baseline_root),
        output_root=Path(args.output_root),
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
