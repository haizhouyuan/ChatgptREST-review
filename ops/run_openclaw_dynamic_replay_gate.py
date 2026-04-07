#!/usr/bin/env python3
"""Run the OpenClaw dynamic replay gate and write a versioned artifact."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.eval.openclaw_dynamic_replay_gate import (
    run_openclaw_dynamic_replay_gate,
    write_openclaw_dynamic_replay_report,
)


DEFAULT_OUTPUT_DIR = Path(
    "/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase20_openclaw_dynamic_replay_gate_20260322"
)


def _next_report_basename(out_dir: Path) -> str:
    version = 1
    while (out_dir / f"report_v{version}.json").exists() or (out_dir / f"report_v{version}.md").exists():
        version += 1
    return f"report_v{version}"


def main() -> int:
    out_dir_override = str(os.environ.get("CHATGPTREST_EVAL_OUT_DIR") or "").strip()
    out_dir = Path(out_dir_override) if out_dir_override else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    report = run_openclaw_dynamic_replay_gate()
    basename = _next_report_basename(out_dir)
    json_path, md_path = write_openclaw_dynamic_replay_report(report, out_dir=out_dir, basename=basename)
    gate_ok = report.num_failed == 0
    manifest = {
        "ok": gate_ok,
        "base_url": report.base_url,
        "plugin_source": report.plugin_source,
        "num_checks": report.num_checks,
        "num_passed": report.num_passed,
        "num_failed": report.num_failed,
        "json_report": str(json_path),
        "markdown_report": str(md_path),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json_path)
    print(md_path)
    return 0 if gate_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
