#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.eval.planning_user_readiness_acceptance import export_pack


def main() -> int:
    parser = argparse.ArgumentParser(description="Export planning user-readiness acceptance evidence.")
    parser.add_argument(
        "--output-dir",
        default="docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v1",
        help="Output directory for manifest and markdown report.",
    )
    args = parser.parse_args()

    manifest = export_pack(output_dir=Path(args.output_dir))
    print(Path(args.output_dir) / "manifest.json")
    print(Path(args.output_dir) / "report_v1.md")
    return 0 if manifest["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
