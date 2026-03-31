#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ops.run_execution_experience_controller_surfaces_smoke import run_smoke as run_controller_surfaces_smoke


def run_rollup_smoke(*, output_dir: str | Path, limit: int = 50) -> dict[str, Any]:
    base = run_controller_surfaces_smoke(output_dir=output_dir, limit=limit)
    cycle_dir = Path(base["paths"]["controller_packet"]).parent
    progress_delta_path = cycle_dir / "progress_delta.json"
    controller_update_note_path = cycle_dir / "controller_update_note.md"

    summary = {
        "ok": True,
        "output_dir": str(Path(output_dir)),
        "mode": str(base.get("mode") or ""),
        "recommended_action": str(base.get("recommended_action") or ""),
        "reason": str(base.get("reason") or ""),
        "progress_signal": "",
        "paths": {
            **dict(base.get("paths") or {}),
            "progress_delta": str(progress_delta_path),
            "controller_update_note": str(controller_update_note_path),
        },
    }
    if progress_delta_path.exists():
        progress_delta = json.loads(progress_delta_path.read_text(encoding="utf-8"))
        if isinstance(progress_delta, dict):
            status = progress_delta.get("status") if isinstance(progress_delta.get("status"), dict) else {}
            summary["progress_signal"] = str(status.get("progress_signal") or "")

    summary_path = Path(output_dir) / "controller_rollup_smoke_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a seeded smoke for the full execution experience controller rollup surfaces.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    result = run_rollup_smoke(output_dir=args.output_dir, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
