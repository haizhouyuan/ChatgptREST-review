#!/usr/bin/env python3
"""Run the OpenClaw dynamic replay gate and write a versioned artifact."""

from __future__ import annotations

from pathlib import Path

from chatgptrest.eval.openclaw_dynamic_replay_gate import (
    run_openclaw_dynamic_replay_gate,
    write_openclaw_dynamic_replay_report,
)


OUTPUT_DIR = Path(
    "/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase20_openclaw_dynamic_replay_gate_20260322"
)


def _next_report_basename(out_dir: Path) -> str:
    version = 1
    while (out_dir / f"report_v{version}.json").exists() or (out_dir / f"report_v{version}.md").exists():
        version += 1
    return f"report_v{version}"


def main() -> int:
    report = run_openclaw_dynamic_replay_gate()
    basename = _next_report_basename(OUTPUT_DIR)
    json_path, md_path = write_openclaw_dynamic_replay_report(report, out_dir=OUTPUT_DIR, basename=basename)
    print(json_path)
    print(md_path)
    return 0 if report.num_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
