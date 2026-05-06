#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "release_validation"
DEFAULT_SOAK_SECONDS = int(os.environ.get("CHATGPTREST_SOAK_SECONDS", "300") or "300")


def _run_command(cmd: list[str], *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_soak_validation(
    *,
    output_dir: str | Path,
    python_bin: str = sys.executable,
    duration_seconds: int = DEFAULT_SOAK_SECONDS,
) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    monitor_path = out / "monitor.jsonl"
    summary_path = out / "summary.md"

    monitor_cmd = [
        python_bin,
        str(REPO_ROOT / "ops" / "monitor_chatgptrest.py"),
        "--duration-seconds",
        str(max(1, int(duration_seconds))),
        "--out",
        str(monitor_path),
    ]
    monitor_proc = _run_command(monitor_cmd)
    _write_text(out / "monitor.stdout.txt", monitor_proc.stdout or "")
    _write_text(out / "monitor.stderr.txt", monitor_proc.stderr or "")

    summarize_cmd = [
        python_bin,
        str(REPO_ROOT / "ops" / "summarize_monitor_log.py"),
        "--in",
        str(monitor_path),
        "--out",
        str(summary_path),
    ]
    summarize_proc = _run_command(summarize_cmd)
    _write_text(out / "summarize.stdout.txt", summarize_proc.stdout or "")
    _write_text(out / "summarize.stderr.txt", summarize_proc.stderr or "")

    result = {
        "ok": monitor_proc.returncode == 0 and summarize_proc.returncode == 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(out),
        "duration_seconds": int(duration_seconds),
        "monitor": {
            "command": monitor_cmd,
            "returncode": int(monitor_proc.returncode),
            "log_path": str(monitor_path),
            "stdout_path": str(out / "monitor.stdout.txt"),
            "stderr_path": str(out / "monitor.stderr.txt"),
        },
        "summarize": {
            "command": summarize_cmd,
            "returncode": int(summarize_proc.returncode),
            "summary_path": str(summary_path),
            "stdout_path": str(out / "summarize.stdout.txt"),
            "stderr_path": str(out / "summarize.stderr.txt"),
        },
    }
    _write_text(out / "summary.json", json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a bounded soak validation bundle without launching an interactive shell."
    )
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--duration-seconds", type=int, default=DEFAULT_SOAK_SECONDS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = (
        Path(args.output_dir)
        if str(args.output_dir).strip()
        else DEFAULT_OUTPUT_ROOT / "convergence_soak"
    )
    summary = run_soak_validation(
        output_dir=output_dir,
        python_bin=args.python_bin,
        duration_seconds=args.duration_seconds,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
