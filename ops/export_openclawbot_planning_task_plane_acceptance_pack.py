#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.eval.openclawbot_planning_task_plane_acceptance import export_pack


def main() -> int:
    parser = argparse.ArgumentParser(description="Export OpenClawBot planning task plane acceptance evidence.")
    parser.add_argument(
        "--output-dir",
        default="docs/dev_log/artifacts/openclawbot_planning_task_plane_acceptance_pack_20260403_v3",
        help="Output directory for manifest and markdown report.",
    )
    parser.add_argument(
        "--scenario-id",
        action="append",
        dest="scenario_ids",
        help="Optional scenario id to limit export. Can be passed multiple times.",
    )
    parser.add_argument(
        "--skip-branch",
        action="store_true",
        help="Skip the project_diagnosis -> leadership_report branch case.",
    )
    args = parser.parse_args()

    manifest = export_pack(
        output_dir=Path(args.output_dir),
        scenario_ids=args.scenario_ids,
        include_branch=not args.skip_branch,
    )
    print(Path(args.output_dir) / "manifest.json")
    print(Path(args.output_dir) / "report_v1.md")
    return 0 if manifest["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
