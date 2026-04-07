from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.eval.openclawbot_planning_task_plane_live_completion_gate import (
    DEFAULT_BOOTSTRAP_TIMEOUT_SECONDS,
    DEFAULT_REQUESTED_PRESET,
    DEFAULT_TIMEOUT_SECONDS,
    run_openclawbot_planning_task_plane_live_completion_gate,
    write_openclawbot_planning_task_plane_live_completion_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the OpenClawBot planning task plane live completion gate.")
    parser.add_argument("--output-dir", default="", help="Directory for manifest/report artifacts.")
    parser.add_argument("--requested-provider", default="", help="Provider to request for the live gate (e.g. gemini, chatgpt).")
    parser.add_argument("--requested-preset", default="", help="Preset to request for the live gate (defaults to auto).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    out_dir_override = str(os.environ.get("CHATGPTREST_EVAL_OUT_DIR") or "").strip()
    bootstrap_timeout_override = str(os.environ.get("CHATGPTREST_EVAL_BOOTSTRAP_TIMEOUT_SECONDS") or "").strip()
    terminal_timeout_override = str(os.environ.get("CHATGPTREST_EVAL_TERMINAL_TIMEOUT_SECONDS") or "").strip()
    requested_provider_override = str(args.requested_provider or "").strip()
    requested_preset_override = str(args.requested_preset or os.environ.get("CHATGPTREST_EVAL_REQUESTED_PRESET") or "").strip()
    out_dir = (
        Path(str(args.output_dir).strip())
        if str(args.output_dir).strip()
        else Path(out_dir_override)
        if out_dir_override
        else (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "dev_log"
            / "artifacts"
            / "openclawbot_planning_task_plane_live_completion_gate_20260403_v1"
        )
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    run_kwargs = {
        "bootstrap_timeout_seconds": int(bootstrap_timeout_override) if bootstrap_timeout_override else DEFAULT_BOOTSTRAP_TIMEOUT_SECONDS,
        "timeout_seconds": int(terminal_timeout_override) if terminal_timeout_override else DEFAULT_TIMEOUT_SECONDS,
        "requested_preset": requested_preset_override or DEFAULT_REQUESTED_PRESET,
    }
    if requested_provider_override:
        run_kwargs["requested_provider"] = requested_provider_override
    report = run_openclawbot_planning_task_plane_live_completion_gate(
        **run_kwargs,
    )
    json_path, md_path = write_openclawbot_planning_task_plane_live_completion_report(report, out_dir=out_dir)
    gate_ok = report.num_failed == 0 and report.terminal_status == "completed"
    manifest = {
        "ok": gate_ok,
        "base_url": report.base_url,
        "requested_provider": report.requested_provider,
        "requested_preset": report.requested_preset,
        "prompt_case_id": report.prompt_case_id,
        "session_id": report.session_id,
        "task_id": report.task_id,
        "terminal_status": report.terminal_status,
        "num_checks": report.num_checks,
        "num_passed": report.num_passed,
        "num_failed": report.num_failed,
        "json_report": str(json_path),
        "markdown_report": str(md_path),
        "scope_boundary": list(report.scope_boundary),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if gate_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
