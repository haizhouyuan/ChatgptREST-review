#!/usr/bin/env python3
"""Run Phase 10 controller route parity validation."""

from __future__ import annotations

from pathlib import Path

from chatgptrest.eval.controller_route_parity_validation import (
    run_controller_route_parity_validation,
    write_controller_route_parity_report,
)
from chatgptrest.eval.datasets import EvalDataset


DATASET_PATH = Path("eval_datasets/phase10_controller_route_parity_samples_v1.json")
OUTPUT_DIR = Path("docs/dev_log/artifacts/phase10_controller_route_parity_validation_20260322")


def main() -> int:
    dataset = EvalDataset.from_file(DATASET_PATH)
    report = run_controller_route_parity_validation(dataset)
    json_path, md_path = write_controller_route_parity_report(report, out_dir=OUTPUT_DIR)
    print(f"[phase10] dataset={report.dataset_name}")
    print(f"[phase10] items={report.num_items} passed={report.num_passed} failed={report.num_failed}")
    print(f"[phase10] json={json_path}")
    print(f"[phase10] md={md_path}")
    return 0 if report.num_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
