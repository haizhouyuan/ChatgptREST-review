#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.sqlite_inventory import (
    DEFAULT_ROOTS,
    analyze_sqlite_databases,
    discover_sqlite_databases,
    filter_sqlite_databases,
    ingest_sqlite_inventory,
    inventories_to_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest SQLite inventory into canonical EvoMap knowledge DB")
    parser.add_argument(
        "--roots",
        nargs="*",
        default=[str(path) for path in DEFAULT_ROOTS],
        help="Roots to scan for *.db/*.sqlite/*.sqlite3 files",
    )
    parser.add_argument(
        "--target-db",
        default=resolve_evomap_knowledge_runtime_db_path(),
        help="Canonical EvoMap knowledge DB path",
    )
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=3,
        help="Sample rows per table/view",
    )
    parser.add_argument(
        "--include-target-db",
        action="store_true",
        help="Include --target-db in discovery instead of excluding it by default",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Artifact directory for JSON and Markdown reports",
    )
    args = parser.parse_args()

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir or f"artifacts/monitor/evomap/sqlite_ingest/{stamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    discovered = discover_sqlite_databases(args.roots)
    if not args.include_target_db:
        discovered = filter_sqlite_databases(discovered, exclude_paths=[args.target_db])
    inventories = analyze_sqlite_databases(
        discovered,
        sample_rows=args.sample_rows,
        canonical_target=args.target_db,
    )

    db = KnowledgeDB(args.target_db)
    db.init_schema()
    stats = ingest_sqlite_inventory(db, inventories)
    stats.discovered = len(discovered)
    stats.failures = sum(1 for inv in inventories if inv.errors)
    db.close()

    summary = {
        "stamp": stamp,
        "target_db": str(Path(args.target_db).resolve()),
        "roots": [str(Path(root).expanduser()) for root in args.roots],
        "stats": stats.to_dict(),
        "inventories": [inv.to_dict() for inv in inventories],
    }

    json_path = output_dir / "summary.json"
    md_path = output_dir / "summary.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(inventories_to_markdown(inventories, stats=stats), encoding="utf-8")

    print(f"Discovered {len(discovered)} SQLite files")
    print(f"Ingested inventory into {args.target_db}")
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
