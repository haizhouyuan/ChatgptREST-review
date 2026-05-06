#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "openmind_watch_window_ledger"
DEFAULT_HEALTH_ROOT = REPO_ROOT / "artifacts" / "monitor" / "openmind_production_health"
DEFAULT_REGRESSION_ROOT = REPO_ROOT / "artifacts" / "monitor" / "openmind_production_regression"
DEFAULT_SCORECARD_ROOT = REPO_ROOT / "artifacts" / "monitor" / "openmind_canary_scorecard"
DEFAULT_COHORT_FILE = REPO_ROOT / "ops" / "data" / "openmind_canary_cohort_v1.json"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _latest_json(root: str | Path, prefix: str) -> Path:
    candidates = sorted(Path(root).glob(f"*/{prefix}_*.json"))
    if not candidates:
        raise FileNotFoundError(f"no {prefix}_*.json files under {root}")
    return candidates[-1]


def _latest_ledger_entry(root: str | Path) -> dict[str, Any] | None:
    candidates = sorted(Path(root).glob("*/openmind_watch_window_ledger_*.json"))
    if not candidates:
        return None
    return _read_json(candidates[-1])


def _status_transitions(
    previous_status: Mapping[str, Any],
    current_status: Mapping[str, Any],
) -> list[dict[str, str]]:
    transitions: list[dict[str, str]] = []
    domains = sorted(set(previous_status) | set(current_status))
    for domain in domains:
        before = str(previous_status.get(domain) or "")
        after = str(current_status.get(domain) or "")
        if before != after:
            transitions.append({"domain": domain, "from": before, "to": after})
    return transitions


def _watch_day_index(started_at: str, current_time: datetime) -> int:
    start_dt = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
    delta_days = max(0.0, (current_time - start_dt).total_seconds() / 86400.0)
    return int(delta_days) + 1


def build_openmind_watch_window_ledger_entry(
    *,
    cohort: Mapping[str, Any],
    health_summary: Mapping[str, Any],
    regression_summary: Mapping[str, Any],
    scorecard: Mapping[str, Any],
    previous_entry: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    current_status = dict(scorecard.get("domain_status") or {})
    previous_status = dict((previous_entry or {}).get("domain_status") or {})
    current_decision = str(dict(scorecard.get("decision") or {}).get("state") or "")
    previous_decision = str(dict((previous_entry or {}).get("decision") or {}).get("state") or "")
    watch_window = dict(scorecard.get("watch_window") or {})
    started_at = str(watch_window.get("started_at") or current_time.isoformat())
    day_index = _watch_day_index(started_at, current_time)
    return {
        "generated_at": current_time.isoformat(),
        "cohort_id": str(cohort.get("cohort_id") or ""),
        "watch_window": {
            "started_at": started_at,
            "ends_at": str(watch_window.get("ends_at") or ""),
            "complete": bool(watch_window.get("complete")),
            "required_days": int(watch_window.get("required_days") or 0),
            "elapsed_days": float(watch_window.get("elapsed_days") or 0.0),
            "day_index": day_index,
        },
        "decision": {
            "state": current_decision,
            "reason": str(dict(scorecard.get("decision") or {}).get("reason") or ""),
        },
        "posture": dict(scorecard.get("posture") or {}),
        "domain_status": current_status,
        "transitions": {
            "decision_changed": bool(previous_decision and previous_decision != current_decision),
            "previous_decision": previous_decision,
            "domain_transitions": _status_transitions(previous_status, current_status),
        },
        "inputs": {
            "health_generated_at": str(health_summary.get("generated_at") or ""),
            "regression_generated_at": str(regression_summary.get("generated_at") or ""),
            "scorecard_generated_at": str(scorecard.get("generated_at") or ""),
            "health_summary_path": str(scorecard.get("health_summary_path") or ""),
            "regression_summary_path": str(scorecard.get("regression_summary_path") or ""),
            "scorecard_path": str(scorecard.get("_source_path") or ""),
        },
        "review_checklist": [
            "Confirm regression stays green before widening the cohort.",
            "Confirm no fail domains and no unapproved warn domains appeared since the previous ledger entry.",
            "If promotion remains warn, confirm it is still attributable to bounded backlog rather than blank reasons.",
            "Do not describe the stack as go-live ready until the watch window is complete and the graduation gate artifact says go_live.",
        ],
    }


def write_openmind_watch_window_ledger_artifacts(
    entry: Mapping[str, Any],
    output_dir: str | Path,
    stamp: str,
) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / f"openmind_watch_window_ledger_{stamp}.json"
    summary_path.write_text(json.dumps(dict(entry), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_lines = [
        "# OpenMind Watch Window Ledger",
        "",
        f"- `cohort_id`: `{entry['cohort_id']}`",
        f"- `decision`: `{entry['decision']['state']}`",
        f"- `launch_posture`: `{entry['posture'].get('launch_posture', '')}`",
        f"- `rollout_posture`: `{entry['posture'].get('rollout_posture', '')}`",
        f"- `watch_day_index`: `{entry['watch_window']['day_index']}`",
        f"- `watch_window_complete`: `{entry['watch_window']['complete']}`",
        f"- `health_summary_path`: `{entry['inputs']['health_summary_path']}`",
        f"- `regression_summary_path`: `{entry['inputs']['regression_summary_path']}`",
        f"- `scorecard_path`: `{entry['inputs']['scorecard_path']}`",
        "",
        "## Domain status",
        "",
    ]
    for name, status in dict(entry.get("domain_status") or {}).items():
        report_lines.append(f"- `{name}`: `{status}`")
    report_lines.extend(["", "## Transitions", ""])
    if list(dict(entry.get("transitions") or {}).get("domain_transitions") or []):
        for item in list(dict(entry.get("transitions") or {}).get("domain_transitions") or []):
            report_lines.append(f"- `{item['domain']}`: `{item['from']}` -> `{item['to']}`")
    else:
        report_lines.append("- none")
    report_lines.extend(["", "## Daily review checklist", ""])
    report_lines.extend(f"- [ ] {item}" for item in list(entry.get("review_checklist") or []))
    report_path = out / f"openmind_watch_window_ledger_{stamp}.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return [summary_path, report_path]


def run_openmind_watch_window_ledger(
    *,
    output_root: str | Path,
    health_root: str | Path,
    regression_root: str | Path,
    scorecard_root: str | Path,
    cohort_file: str | Path,
) -> dict[str, Any]:
    health_path = _latest_json(health_root, "openmind_production_health")
    regression_path = _latest_json(regression_root, "openmind_production_regression")
    scorecard_path = _latest_json(scorecard_root, "openmind_canary_scorecard")
    cohort = _read_json(cohort_file)
    health_summary = _read_json(health_path)
    regression_summary = _read_json(regression_path)
    scorecard = _read_json(scorecard_path)
    scorecard["_source_path"] = str(scorecard_path)
    previous_entry = _latest_ledger_entry(output_root)
    stamp = _stamp()
    out_dir = Path(output_root) / stamp
    entry = build_openmind_watch_window_ledger_entry(
        cohort=cohort,
        health_summary=health_summary,
        regression_summary=regression_summary,
        scorecard=scorecard,
        previous_entry=previous_entry,
    )
    written = write_openmind_watch_window_ledger_artifacts(entry, out_dir, stamp)
    return {
        "ok": True,
        "decision": str(dict(entry.get("decision") or {}).get("state") or ""),
        "artifacts": [str(path) for path in written],
        "output_dir": str(out_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Append one OpenMind canary watch-window ledger entry from the latest health/regression/scorecard artifacts.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--health-root", default=str(DEFAULT_HEALTH_ROOT))
    parser.add_argument("--regression-root", default=str(DEFAULT_REGRESSION_ROOT))
    parser.add_argument("--scorecard-root", default=str(DEFAULT_SCORECARD_ROOT))
    parser.add_argument("--cohort-file", default=str(DEFAULT_COHORT_FILE))
    args = parser.parse_args()
    result = run_openmind_watch_window_ledger(
        output_root=args.output_root,
        health_root=args.health_root,
        regression_root=args.regression_root,
        scorecard_root=args.scorecard_root,
        cohort_file=args.cohort_file,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
