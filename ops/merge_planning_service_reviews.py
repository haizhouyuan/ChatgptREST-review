#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatgptrest.evomap.knowledge.planning_review_plane import merge_review_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge planning service review JSON outputs into final review decisions + allowlist.")
    parser.add_argument("--snapshot-dir", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("review_json", nargs="+")
    args = parser.parse_args()

    snapshot_dir = Path(args.snapshot_dir)
    output = Path(args.output) if args.output else snapshot_dir / "planning_review_decisions.tsv"
    summary = merge_review_outputs(
        snapshot_dir=snapshot_dir,
        review_json_paths=[Path(path) for path in args.review_json],
        output_path=output,
    )
    print(json.dumps({"ok": True, "output": str(output), "summary": summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
