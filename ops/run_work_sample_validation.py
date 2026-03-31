#!/usr/bin/env python3
"""Run business work-sample validation for planning/research front-door asks."""

from __future__ import annotations

import argparse
from pathlib import Path

from chatgptrest.eval.datasets import EvalDataset
from chatgptrest.eval.work_sample_validation import run_work_sample_validation, write_work_sample_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        default="eval_datasets/phase7_business_work_samples_v1.json",
        help="Path to the work-sample dataset JSON",
    )
    parser.add_argument(
        "--out-dir",
        default="docs/dev_log/artifacts/phase7_business_work_sample_validation_20260322",
        help="Directory to write report_v1.json and report_v1.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = EvalDataset.from_file(args.dataset)
    report = run_work_sample_validation(dataset)
    json_path, md_path = write_work_sample_report(report, out_dir=args.out_dir)
    print(f"dataset={dataset.name}")
    print(f"items={report.num_items}")
    print(f"passed={report.num_passed}")
    print(f"failed={report.num_failed}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    return 0 if report.num_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
