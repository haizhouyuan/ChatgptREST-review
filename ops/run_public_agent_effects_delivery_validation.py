#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.eval.public_agent_effects_delivery_validation import (
    run_public_agent_effects_delivery_validation,
    write_public_agent_effects_delivery_report,
)


OUT_DIR = Path("docs/dev_log/artifacts/public_agent_effects_delivery_validation_20260323")


def _next_report_basename(out_dir: Path) -> str:
    idx = 1
    while (out_dir / f"report_v{idx}.json").exists() or (out_dir / f"report_v{idx}.md").exists():
        idx += 1
    return f"report_v{idx}"


def main() -> int:
    report = run_public_agent_effects_delivery_validation()
    basename = _next_report_basename(OUT_DIR)
    json_path, md_path = write_public_agent_effects_delivery_report(report, out_dir=OUT_DIR, basename=basename)
    print(
        json.dumps(
            {
                "ok": report.num_failed == 0,
                "num_checks": report.num_checks,
                "num_passed": report.num_passed,
                "num_failed": report.num_failed,
                "json_path": str(json_path),
                "md_path": str(md_path),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report.num_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
