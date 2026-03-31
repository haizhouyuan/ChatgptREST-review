#!/usr/bin/env python3
"""Run Phase 9 /v3/agent/turn route-level business work-sample validation."""

from __future__ import annotations

import sys
from pathlib import Path

from chatgptrest.eval.agent_v3_route_work_sample_validation import (
    run_agent_v3_route_work_sample_validation,
    write_agent_v3_route_work_sample_report,
)
from chatgptrest.eval.datasets import EvalDataset


DATASET_PATH = Path("eval_datasets/phase9_agent_v3_route_work_samples_v1.json")
OUTPUT_DIR = Path("docs/dev_log/artifacts/phase9_agent_v3_route_work_sample_validation_20260322")


def main() -> int:
    dataset = EvalDataset.from_file(DATASET_PATH)
    report = run_agent_v3_route_work_sample_validation(dataset)
    json_path, md_path = write_agent_v3_route_work_sample_report(report, out_dir=OUTPUT_DIR)
    print(f"[phase9] dataset={report.dataset_name}")
    print(f"[phase9] items={report.num_items} passed={report.num_passed} failed={report.num_failed}")
    print(f"[phase9] json={json_path}")
    print(f"[phase9] md={md_path}")
    return 0 if report.num_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
