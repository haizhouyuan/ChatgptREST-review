#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.review_experiment import inventory_summary, write_inventory_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Build EvoMap canonical DB inventory artifacts")
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--output-dir", default="artifacts/monitor/evomap/inventory")
    parser.add_argument("--stamp", default=dt.datetime.now().strftime("%Y%m%d"))
    args = parser.parse_args()

    summary = inventory_summary(args.db)
    written = write_inventory_artifacts(summary, args.output_dir, args.stamp)
    print(f"Inventory written to {Path(args.output_dir)}")
    for path in written:
        print(path)


if __name__ == "__main__":
    main()

