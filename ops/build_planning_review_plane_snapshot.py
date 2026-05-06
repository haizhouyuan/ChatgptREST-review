#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from chatgptrest.evomap.knowledge.planning_review_plane import (
    DEFAULT_LINEAGE_DIR,
    DEFAULT_PACKAGE_DIR,
    build_service_review_pack,
    build_snapshot,
    default_db_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build planning review-plane snapshot and service review pack.")
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--package-dir", default=str(DEFAULT_PACKAGE_DIR))
    parser.add_argument("--lineage-dir", default=str(DEFAULT_LINEAGE_DIR))
    parser.add_argument(
        "--output-root",
        default="artifacts/monitor/planning_review_plane",
        help="Root directory; actual output uses a UTC timestamp child.",
    )
    args = parser.parse_args()

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_root) / stamp
    result = build_snapshot(
        db_path=args.db,
        package_dir=Path(args.package_dir),
        lineage_dir=Path(args.lineage_dir),
        output_dir=out_dir,
    )
    pack = build_service_review_pack(db_path=args.db, snapshot_dir=out_dir)
    print(
        json.dumps(
            {
                "ok": True,
                "output_dir": str(out_dir),
                "summary": result["summary"],
                "review_pack_items": len(pack["items"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
