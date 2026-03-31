#!/usr/bin/env python3
"""Run Phase 12 core ask launch gate."""

from __future__ import annotations

from pathlib import Path

from chatgptrest.eval.core_ask_launch_gate import (
    run_core_ask_launch_gate,
    write_core_ask_launch_gate_report,
)


OUTPUT_DIR = Path("docs/dev_log/artifacts/phase12_core_ask_launch_gate_20260322")


def main() -> int:
    report = run_core_ask_launch_gate()
    json_path, md_path = write_core_ask_launch_gate_report(report, out_dir=OUTPUT_DIR)
    print(f"[phase12] overall_passed={report.overall_passed}")
    print(f"[phase12] json={json_path}")
    print(f"[phase12] md={md_path}")
    return 0 if report.overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
