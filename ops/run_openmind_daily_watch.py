#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "openmind_daily_watch"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _decision_state(payload: dict[str, Any]) -> str:
    decision = payload.get("decision")
    if isinstance(decision, dict):
        return str(decision.get("state") or "")
    if decision is None:
        return ""
    return str(decision)


def _run_json_command(*, label: str, cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    payload: dict[str, Any] = {}
    if stdout:
        try:
            raw = json.loads(stdout)
            if isinstance(raw, dict):
                payload = raw
            else:
                payload = {"raw_stdout": raw}
        except Exception:
            payload = {"raw_stdout": stdout}
    result = {
        "label": label,
        "cmd": cmd,
        "returncode": int(proc.returncode),
        "stdout": stdout,
        "stderr": stderr,
        "payload": payload,
        "ok": int(proc.returncode) == 0,
    }
    if proc.returncode != 0:
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result


def run_daily_watch(*, output_root: Path) -> dict[str, Any]:
    stamp = _stamp()
    out_dir = output_root / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    commands = [
        (
            "regression",
            [str(VENV_PYTHON), "ops/run_openmind_production_regression.py", "--output-dir", "artifacts/monitor/openmind_production_regression"],
        ),
        (
            "health",
            [str(VENV_PYTHON), "ops/report_openmind_production_health.py", "--output-root", "artifacts/monitor/openmind_production_health"],
        ),
        (
            "scorecard",
            [str(VENV_PYTHON), "ops/report_openmind_canary_scorecard.py", "--output-root", "artifacts/monitor/openmind_canary_scorecard"],
        ),
        (
            "ledger",
            [str(VENV_PYTHON), "ops/report_openmind_watch_window_ledger.py", "--output-root", "artifacts/monitor/openmind_watch_window_ledger"],
        ),
        (
            "gate",
            [str(VENV_PYTHON), "ops/finalize_openmind_graduation_gate.py", "--output-root", "artifacts/monitor/openmind_graduation_gate"],
        ),
    ]

    runs: list[dict[str, Any]] = []
    for label, cmd in commands:
        runs.append(_run_json_command(label=label, cmd=cmd))

    scorecard = dict(runs[2].get("payload") or {})
    gate = dict(runs[4].get("payload") or {})
    summary = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(out_dir),
        "decision": {
            "scorecard": _decision_state(scorecard),
            "gate": _decision_state(gate),
        },
        "runs": [
            {
                "label": item["label"],
                "returncode": item["returncode"],
                "payload": item["payload"],
            }
            for item in runs
        ],
        "artifacts": {
            "summary_json": str(out_dir / "summary.json"),
            "report_md": str(out_dir / "report.md"),
        },
    }
    _write_json(out_dir / "summary.json", summary)
    (out_dir / "report.md").write_text(
        "\n".join(
            [
                "# OpenMind Daily Watch",
                "",
                f"- `scorecard_decision`: `{summary['decision']['scorecard']}`",
                f"- `graduation_gate`: `{summary['decision']['gate']}`",
                "",
                "## Runs",
                *[
                    f"- `{item['label']}`: rc=`{item['returncode']}`"
                    for item in runs
                ],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full OpenMind daily watch bundle.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()
    result = run_daily_watch(output_root=Path(args.output_root))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
