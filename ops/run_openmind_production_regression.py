#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"

PRODUCTION_REGRESSION_BUNDLES: list[dict[str, Any]] = [
    {
        "name": "core_runtime_surface",
        "tests": [
            "tests/test_health_probe.py",
            "tests/test_api_startup_smoke.py",
            "tests/test_agent_control_plane_retirement.py",
        ],
    },
    {
        "name": "public_mcp_surface",
        "tests": [
            "tests/test_agent_mcp.py",
            "tests/test_mcp_server_entrypoints.py",
            "tests/test_cli_improvements.py",
            "tests/test_cli_chatgptrestctl.py",
        ],
    },
    {
        "name": "openclaw_stack_surface",
        "tests": [
            "tests/test_rebuild_openclaw_openmind_stack.py",
            "tests/test_openclaw_cognitive_plugins.py",
            "tests/test_install_openclaw_cognitive_plugins.py",
            "tests/test_verify_openclaw_openmind_stack.py",
        ],
    },
]


def _python_cmd() -> list[str]:
    return [str(VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable))]


def run_production_regression_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    start = time.time()
    cmd = [*_python_cmd(), "-m", "pytest", "-q", *list(bundle.get("tests") or [])]
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "name": str(bundle.get("name") or "").strip(),
        "tests": list(bundle.get("tests") or []),
        "ok": proc.returncode == 0,
        "returncode": int(proc.returncode),
        "duration_seconds": round(time.time() - start, 3),
        "stdout": str(proc.stdout or "").strip(),
        "stderr": str(proc.stderr or "").strip(),
    }


def build_production_regression_summary(
    *,
    bundles: list[dict[str, Any]] | None = None,
    execute: bool = True,
) -> dict[str, Any]:
    selected = list(bundles or PRODUCTION_REGRESSION_BUNDLES)
    results = [run_production_regression_bundle(bundle) for bundle in selected] if execute else []
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "surface_contract": {
            "automation_kernel": True,
            "job_queue": True,
            "observability": True,
            "retired_control_plane": ["/v1/advisor/*", "/v2/advisor/*", "/v3/agent/*"],
        },
        "bundles": results,
        "ok": all(result["ok"] for result in results) if results else True,
    }


def write_production_regression_artifacts(
    summary: dict[str, Any],
    output_dir: str | Path,
    stamp: str,
) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / f"openmind_production_regression_{stamp}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_path = out / f"openmind_production_regression_{stamp}.md"
    lines = [
        "# ChatgptREST Production Regression",
        "",
        f"- `ok`: `{summary['ok']}`",
        "",
        "## Surface contract",
        "",
    ]
    contract = summary.get("surface_contract") or {}
    lines.append(f"- `automation_kernel`: `{contract.get('automation_kernel')}`")
    lines.append(f"- `job_queue`: `{contract.get('job_queue')}`")
    lines.append(f"- `observability`: `{contract.get('observability')}`")
    retired = contract.get("retired_control_plane") or []
    lines.append(f"- `retired_control_plane`: `{', '.join(str(x) for x in retired)}`")
    lines.extend(["", "## Bundles", ""])
    for bundle in summary["bundles"]:
        lines.append(f"- `{bundle['name']}`: `{'ok' if bundle['ok'] else 'failed'}` in `{bundle['duration_seconds']}`s")
    report_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return [summary_path, report_path]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the production-readiness regression bundles.")
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "artifacts" / "monitor" / "openmind_production_regression"),
        help="Directory to write regression artifacts",
    )
    parser.add_argument("--stamp", default="", help="Artifact stamp override")
    parser.add_argument("--dry-run", action="store_true", help="Write bundle plan without executing pytest")
    args = parser.parse_args()

    summary = build_production_regression_summary(execute=not args.dry_run)
    stamp = args.stamp.strip() or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    written = write_production_regression_artifacts(summary, args.output_dir, stamp)
    print(json.dumps({"ok": summary["ok"], "artifacts": [str(path) for path in written]}, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
