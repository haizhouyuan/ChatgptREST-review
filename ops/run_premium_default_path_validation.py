#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.eval.datasets import EvalDataset
from chatgptrest.eval.premium_default_path_validation import (
    run_premium_default_path_validation,
    write_premium_default_path_report,
)


DATASET_PATH = Path("eval_datasets/phase27_premium_default_path_samples_v1.json")
OUT_DIR = Path("docs/dev_log/artifacts/phase27_premium_default_path_validation_20260323")


def _next_report_basename(out_dir: Path) -> str:
    idx = 1
    while (out_dir / f"report_v{idx}.json").exists() or (out_dir / f"report_v{idx}.md").exists():
        idx += 1
    return f"report_v{idx}"


def main() -> int:
    dataset = EvalDataset.from_file(DATASET_PATH)
    report = run_premium_default_path_validation(dataset)
    basename = _next_report_basename(OUT_DIR)
    json_path, md_path = write_premium_default_path_report(report, out_dir=OUT_DIR, basename=basename)
    print(
        json.dumps(
            {
                "ok": report.num_failed == 0,
                "dataset": report.dataset_name,
                "num_items": report.num_items,
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
