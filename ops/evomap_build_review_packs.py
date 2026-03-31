#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.review_experiment import (
    build_atom_pack,
    build_family_pack,
    build_noise_pack,
    write_review_pack,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build EvoMap review packs from canonical DB")
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--output-dir", default="artifacts/monitor/evomap/review_packs")
    parser.add_argument("--seed", type=int, default=20260310)
    parser.add_argument("--stamp", default=dt.datetime.now().strftime("%Y%m%d"))
    args = parser.parse_args()

    out = Path(args.output_dir) / args.stamp
    out.mkdir(parents=True, exist_ok=True)

    manual_gold = build_atom_pack(
        args.db,
        [
            {"source": "maint", "count": 8, "min_quality": 0.45},
            {"source": "planning", "project": "planning", "count": 12, "min_quality": 0.55},
            {"source": "planning", "project": "research", "count": 8, "min_quality": 0.55},
            {"source": "chatgptrest", "count": 8, "min_quality": 0.55},
            {"source": "antigravity", "count": 8, "min_quality": 0.55},
            {"source": "agent_activity", "count": 4, "min_quality": 0.45},
        ],
        seed=args.seed,
        pack_id="manual_gold_atoms",
    )

    expanded_service = build_atom_pack(
        args.db,
        [
            {"source": "maint", "count": 12, "min_quality": 0.35},
            {"source": "planning", "project": "planning", "count": 18, "min_quality": 0.45},
            {"source": "planning", "project": "research", "count": 12, "min_quality": 0.45},
            {"source": "chatgptrest", "count": 12, "min_quality": 0.45},
            {"source": "antigravity", "count": 12, "min_quality": 0.45},
            {"source": "agent_activity", "count": 6, "min_quality": 0.35},
        ],
        seed=args.seed + 1,
        pack_id="expanded_service_atoms",
    )

    noise_pack = build_noise_pack(
        args.db,
        limit_per_bucket=3,
        seed=args.seed + 2,
        pack_id="noise_atoms",
    )
    family_pack = build_family_pack(
        args.db,
        limit=18,
        seed=args.seed + 3,
        pack_id="version_families",
    )

    written = []
    for pack in [manual_gold, expanded_service, noise_pack, family_pack]:
        written.extend(write_review_pack(pack, out))

    print(f"Review packs written to {out}")
    for path in written:
        print(path)


if __name__ == "__main__":
    main()

