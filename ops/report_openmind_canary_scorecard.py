#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "openmind_canary_scorecard"
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


def load_canary_cohort(path: str | Path) -> dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError("canary cohort file must be a JSON object")
    return payload


def build_openmind_canary_scorecard(
    *,
    health_summary: Mapping[str, Any],
    regression_summary: Mapping[str, Any],
    cohort: Mapping[str, Any],
    watch_window_started_at: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    watch_start = watch_window_started_at or current_time.isoformat()
    watch_start_dt = datetime.fromisoformat(str(watch_start).replace("Z", "+00:00"))
    watch_window_days = max(1, int(cohort.get("watch_window_days") or 1))
    watch_end_dt = watch_start_dt + timedelta(days=watch_window_days)
    domains = dict(health_summary.get("domains") or {})
    domain_status = {name: str(dict(payload).get("status") or "") for name, payload in domains.items()}
    fail_domains = sorted(name for name, status in domain_status.items() if status == "fail")
    warn_domains = sorted(name for name, status in domain_status.items() if status == "warn")
    allowed_warn_domains = sorted(str(v).strip() for v in list(dict(cohort.get("failure_budget") or {}).get("allowed_warn_domains") or []) if str(v).strip())
    unapproved_warn_domains = sorted(name for name in warn_domains if name not in allowed_warn_domains)
    regression_ok = bool(regression_summary.get("ok"))
    canary_launch_ok = regression_ok and not fail_domains and not unapproved_warn_domains
    elapsed_days = max(0.0, round((current_time - watch_start_dt).total_seconds() / 86400, 3))
    watch_window_complete = current_time >= watch_end_dt
    go_live_ready = canary_launch_ok and watch_window_complete
    if go_live_ready:
        rollout_posture = "go-live ready"
        launch_posture = "canary-ready"
    elif canary_launch_ok:
        rollout_posture = "watch-window active"
        launch_posture = "canary-ready"
    else:
        rollout_posture = "hold"
        launch_posture = "not-ready"
    if go_live_ready:
        decision = "go_live"
        decision_reason = "Regression is green, no fail domains remain, and the watch window has elapsed."
    elif canary_launch_ok:
        decision = "launch_canary_watch"
        decision_reason = "Regression is green and only approved warning domains remain; start or continue the watch window."
    else:
        decision = "hold"
        decision_reason = "Release gates are not satisfied; do not expand beyond the current canary cohort."
    return {
        "generated_at": current_time.isoformat(),
        "cohort": dict(cohort),
        "inputs": {
            "health_generated_at": str(health_summary.get("generated_at") or ""),
            "regression_generated_at": str(regression_summary.get("generated_at") or ""),
        },
        "domain_status": domain_status,
        "gates": {
            "regression_ok": regression_ok,
            "fail_domains": fail_domains,
            "warn_domains": warn_domains,
            "allowed_warn_domains": allowed_warn_domains,
            "unapproved_warn_domains": unapproved_warn_domains,
            "canary_launch_ok": canary_launch_ok,
            "go_live_ready": go_live_ready,
        },
        "posture": {
            "launch_posture": launch_posture,
            "rollout_posture": rollout_posture,
        },
        "watch_window": {
            "started_at": watch_start_dt.isoformat(),
            "ends_at": watch_end_dt.isoformat(),
            "elapsed_days": elapsed_days,
            "required_days": watch_window_days,
            "complete": watch_window_complete,
        },
        "decision": {
            "state": decision,
            "reason": decision_reason,
        },
        "health_summary_path": str(health_summary.get("_source_path") or ""),
        "regression_summary_path": str(regression_summary.get("_source_path") or ""),
        "post_rollout_watch": [
            "Re-run the production regression bundle at the start of the watch window and before any cohort expansion.",
            "Re-run the production health rollup daily during the watch window.",
            "Escalate immediately if any domain moves from warn to fail.",
            "Do not widen beyond the canary cohort until the watch window elapses and go_live_ready becomes true.",
        ],
    }


def write_openmind_canary_scorecard_artifacts(
    scorecard: Mapping[str, Any],
    output_dir: str | Path,
    stamp: str,
) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / f"openmind_canary_scorecard_{stamp}.json"
    summary_path.write_text(json.dumps(dict(scorecard), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_lines = [
        "# OpenMind Canary Scorecard",
        "",
        f"- `decision`: `{scorecard['decision']['state']}`",
        f"- `reason`: {scorecard['decision']['reason']}",
        f"- `launch_posture`: `{scorecard['posture']['launch_posture']}`",
        f"- `rollout_posture`: `{scorecard['posture']['rollout_posture']}`",
        f"- `watch_window_started_at`: `{scorecard['watch_window']['started_at']}`",
        f"- `watch_window_ends_at`: `{scorecard['watch_window']['ends_at']}`",
        f"- `watch_window_complete`: `{scorecard['watch_window']['complete']}`",
        "",
        "## Domain status",
        "",
    ]
    for name, status in dict(scorecard.get("domain_status") or {}).items():
        report_lines.append(f"- `{name}`: `{status}`")
    report_lines.extend(
        [
            "",
            "## Gates",
            "",
            f"- `regression_ok`: `{scorecard['gates']['regression_ok']}`",
            f"- `fail_domains`: `{json.dumps(scorecard['gates']['fail_domains'], ensure_ascii=False)}`",
            f"- `warn_domains`: `{json.dumps(scorecard['gates']['warn_domains'], ensure_ascii=False)}`",
            f"- `allowed_warn_domains`: `{json.dumps(scorecard['gates']['allowed_warn_domains'], ensure_ascii=False)}`",
            f"- `unapproved_warn_domains`: `{json.dumps(scorecard['gates']['unapproved_warn_domains'], ensure_ascii=False)}`",
            "",
        ]
    )
    report_path = out / f"openmind_canary_scorecard_{stamp}.md"
    report_path.write_text("\n".join(report_lines).strip() + "\n", encoding="utf-8")

    decision_path = out / f"openmind_rollout_decision_log_{stamp}.md"
    decision_path.write_text(
        "\n".join(
            [
                "# OpenMind Rollout Decision Log",
                "",
                f"- state: `{scorecard['decision']['state']}`",
                f"- reason: {scorecard['decision']['reason']}",
                f"- health_summary_path: `{scorecard['health_summary_path']}`",
                f"- regression_summary_path: `{scorecard['regression_summary_path']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    checklist_path = out / f"openmind_post_rollout_watch_checklist_{stamp}.md"
    checklist_lines = ["# OpenMind Post-Rollout Watch Checklist", ""]
    checklist_lines.extend(f"- [ ] {item}" for item in list(scorecard.get("post_rollout_watch") or []))
    checklist_path.write_text("\n".join(checklist_lines) + "\n", encoding="utf-8")
    return [summary_path, report_path, decision_path, checklist_path]


def run_openmind_canary_scorecard(
    *,
    output_root: str | Path,
    health_root: str | Path,
    regression_root: str | Path,
    cohort_file: str | Path,
    watch_window_started_at: str | None = None,
) -> dict[str, Any]:
    health_path = _latest_json(health_root, "openmind_production_health")
    regression_path = _latest_json(regression_root, "openmind_production_regression")
    health_summary = _read_json(health_path)
    regression_summary = _read_json(regression_path)
    health_summary["_source_path"] = str(health_path)
    regression_summary["_source_path"] = str(regression_path)
    cohort = load_canary_cohort(cohort_file)
    scorecard = build_openmind_canary_scorecard(
        health_summary=health_summary,
        regression_summary=regression_summary,
        cohort=cohort,
        watch_window_started_at=watch_window_started_at,
    )
    stamp = _stamp()
    out_dir = Path(output_root) / stamp
    written = write_openmind_canary_scorecard_artifacts(scorecard, out_dir, stamp)
    return {
        "ok": bool(scorecard.get("gates", {}).get("canary_launch_ok")),
        "decision": str(scorecard.get("decision", {}).get("state") or ""),
        "artifacts": [str(path) for path in written],
        "output_dir": str(out_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the OpenMind canary scorecard from the latest health and regression artifacts.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--health-root", default=str(DEFAULT_HEALTH_ROOT))
    parser.add_argument("--regression-root", default=str(DEFAULT_REGRESSION_ROOT))
    parser.add_argument("--cohort-file", default=str(DEFAULT_COHORT_FILE))
    parser.add_argument("--watch-window-started-at", default="")
    args = parser.parse_args()

    result = run_openmind_canary_scorecard(
        output_root=args.output_root,
        health_root=args.health_root,
        regression_root=args.regression_root,
        cohort_file=args.cohort_file,
        watch_window_started_at=args.watch_window_started_at.strip() or None,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
