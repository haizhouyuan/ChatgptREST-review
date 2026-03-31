#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
DEFAULT_DB = REPO_ROOT / "state" / "jobdb.sqlite3"
DEFAULT_OPEN_ISSUE_JSON = REPO_ROOT / "artifacts" / "monitor" / "open_issue_list" / "latest.json"
DEFAULT_OPEN_ISSUE_MD = REPO_ROOT / "artifacts" / "monitor" / "open_issue_list" / "latest.md"
DEFAULT_HISTORY_JSON = REPO_ROOT / "artifacts" / "monitor" / "open_issue_list" / "history_tail.json"
DEFAULT_HISTORY_MD = REPO_ROOT / "artifacts" / "monitor" / "open_issue_list" / "history_tail.md"
DEFAULT_GUARDIAN_REPORT = REPO_ROOT / "artifacts" / "monitor" / "openclaw_guardian" / "latest_report.json"
DEFAULT_BASE_URL = "http://127.0.0.1:18711"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh read-only monitor projections (open issue list + guardian latest report)."
    )
    parser.add_argument("--python-bin", default=str(DEFAULT_PYTHON))
    parser.add_argument("--db-path", default=str(DEFAULT_DB))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--json-out", default=str(DEFAULT_OPEN_ISSUE_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_OPEN_ISSUE_MD))
    parser.add_argument("--history-json-out", default=str(DEFAULT_HISTORY_JSON))
    parser.add_argument("--history-md-out", default=str(DEFAULT_HISTORY_MD))
    parser.add_argument("--guardian-report-out", default=str(DEFAULT_GUARDIAN_REPORT))
    parser.add_argument("--active-limit", type=int, default=200)
    parser.add_argument("--recent-limit", type=int, default=50)
    parser.add_argument("--history-limit", type=int, default=200)
    parser.add_argument("--guardian-lookback-minutes", type=int, default=30)
    parser.add_argument("--guardian-max-rows", type=int, default=200)
    parser.add_argument("--skip-issue-views", action="store_true")
    parser.add_argument("--skip-guardian", action="store_true")
    return parser


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    python_bin = Path(str(args.python_bin)).expanduser()
    if not python_bin.is_absolute():
        python_bin = (REPO_ROOT / python_bin).resolve(strict=False)
    py = str(python_bin)

    runs: list[dict[str, object]] = []
    overall_ok = True

    if not bool(args.skip_issue_views):
        issue_cmd = [
            py,
            str(REPO_ROOT / "ops" / "export_issue_views.py"),
            "--db-path",
            str(Path(str(args.db_path)).expanduser()),
            "--json-out",
            str(Path(str(args.json_out)).expanduser()),
            "--md-out",
            str(Path(str(args.md_out)).expanduser()),
            "--history-json-out",
            str(Path(str(args.history_json_out)).expanduser()),
            "--history-md-out",
            str(Path(str(args.history_md_out)).expanduser()),
            "--active-limit",
            str(int(args.active_limit)),
            "--recent-limit",
            str(int(args.recent_limit)),
            "--history-limit",
            str(int(args.history_limit)),
        ]
        proc = _run(issue_cmd)
        runs.append(
            {
                "name": "issue_views_export",
                "ok": proc.returncode == 0,
                "returncode": int(proc.returncode),
                "command": issue_cmd,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
        overall_ok = overall_ok and proc.returncode == 0

    if not bool(args.skip_guardian):
        guardian_cmd = [
            py,
            str(REPO_ROOT / "ops" / "openclaw_guardian_run.py"),
            "--db-path",
            str(Path(str(args.db_path)).expanduser()),
            "--base-url",
            str(args.base_url),
            "--lookback-minutes",
            str(int(args.guardian_lookback_minutes)),
            "--max-rows",
            str(int(args.guardian_max_rows)),
            "--projection-only",
            "--report-out",
            str(Path(str(args.guardian_report_out)).expanduser()),
        ]
        proc = _run(guardian_cmd)
        runs.append(
            {
                "name": "guardian_projection",
                "ok": proc.returncode == 0,
                "returncode": int(proc.returncode),
                "command": guardian_cmd,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
        overall_ok = overall_ok and proc.returncode == 0

    for run in runs:
        status = "ok" if run["ok"] else "failed"
        print(f"[{status}] {run['name']}")
        if run["stderr"]:
            print(str(run["stderr"]).rstrip())
        if run["stdout"]:
            print(str(run["stdout"]).rstrip())

    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
