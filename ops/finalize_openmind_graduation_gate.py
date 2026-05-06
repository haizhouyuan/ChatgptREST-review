#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "openmind_graduation_gate"
DEFAULT_LEDGER_ROOT = REPO_ROOT / "artifacts" / "monitor" / "openmind_watch_window_ledger"
DEFAULT_SCORECARD_ROOT = REPO_ROOT / "artifacts" / "monitor" / "openmind_canary_scorecard"
DEFAULT_HEALTH_ROOT = REPO_ROOT / "artifacts" / "monitor" / "openmind_production_health"
DEFAULT_REGRESSION_ROOT = REPO_ROOT / "artifacts" / "monitor" / "openmind_production_regression"
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


def _load_ledger_entries(root: str | Path) -> list[dict[str, Any]]:
    entries = []
    for path in sorted(Path(root).glob("*/openmind_watch_window_ledger_*.json")):
        payload = _read_json(path)
        payload["_source_path"] = str(path)
        entries.append(payload)
    return entries


def build_openmind_graduation_decision(
    *,
    cohort: Mapping[str, Any],
    scorecard: Mapping[str, Any],
    health_summary: Mapping[str, Any],
    regression_summary: Mapping[str, Any],
    ledger_entries: list[Mapping[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    gates = dict(scorecard.get("gates") or {})
    fail_domains = list(gates.get("fail_domains") or [])
    unapproved_warn_domains = list(gates.get("unapproved_warn_domains") or [])
    watch_window = dict(scorecard.get("watch_window") or {})
    ledger_fail_domains = sorted(
        {
            transition["domain"]
            for entry in ledger_entries
            for transition in list(dict(entry.get("transitions") or {}).get("domain_transitions") or [])
            if str(transition.get("to") or "") == "fail"
        }
    )
    ledger_days = sorted(
        {
            int(dict(entry.get("watch_window") or {}).get("day_index") or 0)
            for entry in ledger_entries
            if int(dict(entry.get("watch_window") or {}).get("day_index") or 0) > 0
        }
    )
    watch_complete = bool(watch_window.get("complete"))
    scorecard_decision = str(dict(scorecard.get("decision") or {}).get("state") or "")
    if fail_domains or not bool(regression_summary.get("ok")):
        decision = "rollback"
        reason = "Current fail domains or regression failure make the canary ineligible for expansion."
    elif not watch_complete:
        decision = "hold"
        reason = "The watch window has not yet elapsed; keep the canary in watch-window active posture."
    elif unapproved_warn_domains:
        decision = "hold"
        reason = "Unapproved warning domains remain at graduation time."
    elif scorecard_decision != "go_live":
        decision = "hold"
        reason = "Latest scorecard is not yet in go_live state."
    else:
        decision = "go_live"
        reason = "Watch window is complete and the latest scorecard remains eligible for go-live."
    return {
        "generated_at": current_time.isoformat(),
        "cohort_id": str(cohort.get("cohort_id") or ""),
        "decision": {
            "state": decision,
            "reason": reason,
        },
        "scorecard_decision": scorecard_decision,
        "watch_window": {
            "started_at": str(watch_window.get("started_at") or ""),
            "ends_at": str(watch_window.get("ends_at") or ""),
            "complete": watch_complete,
            "required_days": int(watch_window.get("required_days") or 0),
            "elapsed_days": float(watch_window.get("elapsed_days") or 0.0),
            "ledger_entry_count": len(ledger_entries),
            "ledger_days_seen": ledger_days,
        },
        "gates": {
            "regression_ok": bool(regression_summary.get("ok")),
            "fail_domains": fail_domains,
            "unapproved_warn_domains": unapproved_warn_domains,
            "ledger_fail_domains": ledger_fail_domains,
            "go_live_ready": bool(gates.get("go_live_ready")),
        },
        "inputs": {
            "health_summary_path": str(scorecard.get("health_summary_path") or ""),
            "regression_summary_path": str(scorecard.get("regression_summary_path") or ""),
            "scorecard_path": str(scorecard.get("_source_path") or ""),
            "latest_ledger_path": str(ledger_entries[-1].get("_source_path") or "") if ledger_entries else "",
        },
        "notes": [
            "Graduation is distinct from canary launch; a watch window in progress must yield hold rather than go_live.",
            "A rollback decision only occurs on current fail domains or regression failure, not merely because the watch window is incomplete.",
        ],
    }


def write_openmind_graduation_artifacts(
    summary: Mapping[str, Any],
    output_dir: str | Path,
    stamp: str,
) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / f"openmind_graduation_gate_{stamp}.json"
    summary_path.write_text(json.dumps(dict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_lines = [
        "# OpenMind Graduation Gate",
        "",
        f"- `decision`: `{summary['decision']['state']}`",
        f"- `reason`: {summary['decision']['reason']}",
        f"- `scorecard_decision`: `{summary['scorecard_decision']}`",
        f"- `watch_window_complete`: `{summary['watch_window']['complete']}`",
        f"- `ledger_entry_count`: `{summary['watch_window']['ledger_entry_count']}`",
        f"- `fail_domains`: `{json.dumps(summary['gates']['fail_domains'], ensure_ascii=False)}`",
        f"- `unapproved_warn_domains`: `{json.dumps(summary['gates']['unapproved_warn_domains'], ensure_ascii=False)}`",
        "",
        "## Inputs",
        "",
        f"- `health_summary_path`: `{summary['inputs']['health_summary_path']}`",
        f"- `regression_summary_path`: `{summary['inputs']['regression_summary_path']}`",
        f"- `scorecard_path`: `{summary['inputs']['scorecard_path']}`",
        f"- `latest_ledger_path`: `{summary['inputs']['latest_ledger_path']}`",
        "",
    ]
    report_path = out / f"openmind_graduation_gate_{stamp}.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return [summary_path, report_path]


def run_openmind_graduation_gate(
    *,
    output_root: str | Path,
    ledger_root: str | Path,
    scorecard_root: str | Path,
    health_root: str | Path,
    regression_root: str | Path,
    cohort_file: str | Path,
) -> dict[str, Any]:
    cohort = _read_json(cohort_file)
    scorecard_path = _latest_json(scorecard_root, "openmind_canary_scorecard")
    health_path = _latest_json(health_root, "openmind_production_health")
    regression_path = _latest_json(regression_root, "openmind_production_regression")
    ledger_entries = _load_ledger_entries(ledger_root)
    scorecard = _read_json(scorecard_path)
    scorecard["_source_path"] = str(scorecard_path)
    summary = build_openmind_graduation_decision(
        cohort=cohort,
        scorecard=scorecard,
        health_summary=_read_json(health_path),
        regression_summary=_read_json(regression_path),
        ledger_entries=ledger_entries,
    )
    stamp = _stamp()
    out_dir = Path(output_root) / stamp
    written = write_openmind_graduation_artifacts(summary, out_dir, stamp)
    return {
        "ok": str(dict(summary.get("decision") or {}).get("state") or "") != "rollback",
        "decision": str(dict(summary.get("decision") or {}).get("state") or ""),
        "artifacts": [str(path) for path in written],
        "output_dir": str(out_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit the canonical OpenMind graduation decision from the latest watch-window artifacts.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--ledger-root", default=str(DEFAULT_LEDGER_ROOT))
    parser.add_argument("--scorecard-root", default=str(DEFAULT_SCORECARD_ROOT))
    parser.add_argument("--health-root", default=str(DEFAULT_HEALTH_ROOT))
    parser.add_argument("--regression-root", default=str(DEFAULT_REGRESSION_ROOT))
    parser.add_argument("--cohort-file", default=str(DEFAULT_COHORT_FILE))
    args = parser.parse_args()
    result = run_openmind_graduation_gate(
        output_root=args.output_root,
        ledger_root=args.ledger_root,
        scorecard_root=args.scorecard_root,
        health_root=args.health_root,
        regression_root=args.regression_root,
        cohort_file=args.cohort_file,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
