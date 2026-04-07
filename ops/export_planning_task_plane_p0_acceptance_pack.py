#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.eval.planning_task_plane_p0_acceptance import export_pack


def main() -> int:
    parser = argparse.ArgumentParser(description="Export planning task plane P0 acceptance evidence.")
    parser.add_argument(
        "--output-dir",
        default="docs/dev_log/artifacts/planning_task_plane_p0_acceptance_pack_20260404_v1",
        help="Output directory for manifest and markdown report.",
    )
    parser.add_argument(
        "--unmocked-scenario-id",
        action="append",
        default=[],
        help="Scenario id that should run through unmocked W4 ingress/writeback helpers.",
    )
    args = parser.parse_args()

    manifest = export_pack(
        output_dir=Path(args.output_dir),
        unmocked_scenario_ids=list(args.unmocked_scenario_id or []),
    )
    print(Path(args.output_dir) / "manifest.json")
    print(Path(args.output_dir) / "report_v1.md")
    return 0 if manifest["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
