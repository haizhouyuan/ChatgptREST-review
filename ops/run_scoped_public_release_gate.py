#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.eval.scoped_public_release_gate import run_scoped_public_release_gate, write_scoped_public_release_gate_report


OUT_DIR = Path("docs/dev_log/artifacts/phase17_scoped_public_release_gate_20260322")


def main() -> int:
    report = run_scoped_public_release_gate()
    json_path, md_path = write_scoped_public_release_gate_report(report, out_dir=OUT_DIR)
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

