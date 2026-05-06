#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from chatgptrest.eval.openclawbot_meeting_intake_smoke import (
    run_openclawbot_meeting_intake_smoke,
    write_openclawbot_meeting_intake_smoke_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Step 0 OpenClawBot meeting-intake smoke checks.")
    parser.add_argument(
        "--out-dir",
        default="docs/dev_log/artifacts/openclawbot_meeting_intake_smoke_20260403",
        help="Output directory for JSON/Markdown report.",
    )
    parser.add_argument(
        "--basename",
        default="report_v1",
        help="Report basename without extension.",
    )
    args = parser.parse_args()

    report = run_openclawbot_meeting_intake_smoke()
    json_path, md_path = write_openclawbot_meeting_intake_smoke_report(
        report,
        out_dir=Path(args.out_dir),
        basename=args.basename,
    )
    print(json_path)
    print(md_path)
    return 0 if report.num_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
