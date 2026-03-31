#!/usr/bin/env python3
"""Run Phase 8 multi-ingress business work-sample validation."""

from __future__ import annotations

import sys
from pathlib import Path

from chatgptrest.eval.datasets import EvalDataset
from chatgptrest.eval.multi_ingress_work_sample_validation import (
    run_multi_ingress_work_sample_validation,
    write_multi_ingress_work_sample_report,
)


DATASET_PATH = Path("eval_datasets/phase8_multi_ingress_work_samples_v1.json")
OUTPUT_DIR = Path("docs/dev_log/artifacts/phase8_multi_ingress_work_sample_validation_20260322")


def main() -> int:
    dataset = EvalDataset.from_file(DATASET_PATH)
    report = run_multi_ingress_work_sample_validation(dataset)
    json_path, md_path = write_multi_ingress_work_sample_report(report, out_dir=OUTPUT_DIR)
    print(f"[phase8] dataset={report.dataset_name}")
    print(f"[phase8] items={report.num_items} cases={report.num_cases} passed={report.num_passed} failed={report.num_failed}")
    print(f"[phase8] json={json_path}")
    print(f"[phase8] md={md_path}")
    return 0 if report.num_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
