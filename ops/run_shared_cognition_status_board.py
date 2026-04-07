#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from chatgptrest.dashboard.shared_cognition_scoreboard import (
    build_shared_cognition_status_board,
    write_shared_cognition_status_board,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _default_out_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    return REPO_ROOT / "docs" / "dev_log" / "artifacts" / f"shared_cognition_status_board_{stamp}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the current shared-cognition status board as JSON + Markdown.")
    parser.add_argument("--out-dir", default=str(_default_out_dir()))
    args = parser.parse_args()

    payload = build_shared_cognition_status_board()
    json_path, md_path = write_shared_cognition_status_board(payload, out_dir=args.out_dir)
    print(
        json.dumps(
            {
                "ok": True,
                "json_path": str(json_path),
                "md_path": str(md_path),
                "remaining_blockers": payload["shared_cognition"]["remaining_blockers"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
