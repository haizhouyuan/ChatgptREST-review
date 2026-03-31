#!/usr/bin/env python3
"""Run Phase 11 branch coverage validation."""

from __future__ import annotations

from pathlib import Path

from chatgptrest.eval.branch_coverage_validation import (
    run_branch_coverage_validation,
    write_branch_coverage_report,
)
from chatgptrest.eval.datasets import EvalDataset


DATASET_PATH = Path("eval_datasets/phase11_branch_coverage_samples_v1.json")
OUTPUT_DIR = Path("docs/dev_log/artifacts/phase11_branch_coverage_validation_20260322")


def main() -> int:
    dataset = EvalDataset.from_file(DATASET_PATH)
    report = run_branch_coverage_validation(dataset)
    json_path, md_path = write_branch_coverage_report(report, out_dir=OUTPUT_DIR)
    print(f"[phase11] dataset={report.dataset_name}")
    print(f"[phase11] items={report.num_items} passed={report.num_passed} failed={report.num_failed}")
    print(f"[phase11] json={json_path}")
    print(f"[phase11] md={md_path}")
    return 0 if report.num_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
