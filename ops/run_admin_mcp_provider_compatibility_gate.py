#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.eval.admin_mcp_provider_compatibility_gate import (
    run_admin_mcp_provider_compatibility_gate,
    write_admin_mcp_provider_compatibility_gate_report,
)


OUT_DIR = Path("docs/dev_log/artifacts/phase25_admin_mcp_provider_compatibility_gate_20260323")


def _next_report_basename(out_dir: Path) -> str:
    idx = 1
    while True:
        stem = f"report_v{idx}"
        if not (out_dir / f"{stem}.json").exists() and not (out_dir / f"{stem}.md").exists():
            return stem
        idx += 1


def main() -> int:
    report = run_admin_mcp_provider_compatibility_gate()
    json_path, md_path = write_admin_mcp_provider_compatibility_gate_report(
        report,
        out_dir=OUT_DIR,
        basename=_next_report_basename(OUT_DIR),
    )
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
