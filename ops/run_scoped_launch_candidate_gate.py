#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.eval.scoped_launch_candidate_gate import (
    run_scoped_launch_candidate_gate,
    write_scoped_launch_candidate_gate_report,
)


OUT_DIR = Path("docs/dev_log/artifacts/phase19_scoped_launch_candidate_gate_20260322")


def _next_report_basename(out_dir: Path) -> str:
    idx = 1
    while True:
        stem = f"report_v{idx}"
        if not (out_dir / f"{stem}.json").exists() and not (out_dir / f"{stem}.md").exists():
            return stem
        idx += 1


def main() -> int:
    report = run_scoped_launch_candidate_gate()
    json_path, md_path = write_scoped_launch_candidate_gate_report(
        report,
        out_dir=OUT_DIR,
        basename=_next_report_basename(OUT_DIR),
    )
    print(
        json.dumps(
            {
                "ok": report.overall_passed,
                "num_checks": report.num_checks,
                "num_passed": report.num_passed,
                "num_failed": report.num_failed,
                "json_path": str(json_path),
                "md_path": str(md_path),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report.overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
