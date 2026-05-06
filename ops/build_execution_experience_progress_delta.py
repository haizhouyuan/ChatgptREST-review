#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


_ACTION_SEVERITY = {
    "park": 0,
    "route_followups": 1,
    "continue_review": 2,
    "collect_missing_reviews": 3,
    "fix_review_outputs": 4,
}


def _load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Expected JSON object at {path}")


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0
        if text.lstrip("-").isdigit():
            return int(text)
    return None


def _delta_map(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, int]:
    keys = sorted(set(previous) | set(current))
    result: dict[str, int] = {}
    for key in keys:
        previous_value = _coerce_int(previous.get(key, 0))
        current_value = _coerce_int(current.get(key, 0))
        if previous_value is None and current_value is None:
            continue
        result[key] = int(current_value or 0) - int(previous_value or 0)
    return result


def _progress_signal(
    *,
    previous_action: str,
    current_action: str,
    totals_delta: dict[str, int],
    validation_delta: dict[str, int],
    previous_flags: dict[str, Any],
    current_flags: dict[str, Any],
) -> str:
    improved = 0
    regressed = 0

    if totals_delta.get("reviewed_candidates", 0) > 0:
        improved += 1
    elif totals_delta.get("reviewed_candidates", 0) < 0:
        regressed += 1

    if totals_delta.get("backlog_candidates", 0) < 0:
        improved += 1
    elif totals_delta.get("backlog_candidates", 0) > 0:
        regressed += 1

    if validation_delta.get("total_validation_issues", 0) < 0:
        improved += 1
    elif validation_delta.get("total_validation_issues", 0) > 0:
        regressed += 1

    previous_severity = _ACTION_SEVERITY.get(previous_action, 99)
    current_severity = _ACTION_SEVERITY.get(current_action, 99)
    if current_severity < previous_severity:
        improved += 1
    elif current_severity > previous_severity:
        regressed += 1

    if bool(previous_flags.get("invalid_review_outputs")) and not bool(current_flags.get("invalid_review_outputs")):
        improved += 1
    elif not bool(previous_flags.get("invalid_review_outputs")) and bool(current_flags.get("invalid_review_outputs")):
        regressed += 1

    if bool(previous_flags.get("backlog_open")) and not bool(current_flags.get("backlog_open")):
        improved += 1
    elif not bool(previous_flags.get("backlog_open")) and bool(current_flags.get("backlog_open")):
        regressed += 1

    if improved and not regressed:
        return "improved"
    if regressed and not improved:
        return "regressed"
    if improved or regressed:
        return "mixed"
    return "unchanged"


def build_delta(
    *,
    output_path: str | Path,
    previous_governance_snapshot: dict[str, Any],
    current_governance_snapshot: dict[str, Any],
    previous_controller_action_plan: dict[str, Any],
    current_controller_action_plan: dict[str, Any],
) -> dict[str, Any]:
    previous_totals = dict(previous_governance_snapshot.get("totals") or {})
    current_totals = dict(current_governance_snapshot.get("totals") or {})
    previous_review = dict(previous_governance_snapshot.get("review_state") or {})
    current_review = dict(current_governance_snapshot.get("review_state") or {})
    previous_validation = dict(previous_governance_snapshot.get("validation_state") or {})
    current_validation = dict(current_governance_snapshot.get("validation_state") or {})
    previous_queue = dict(previous_governance_snapshot.get("queue_state") or {})
    current_queue = dict(current_governance_snapshot.get("queue_state") or {})
    previous_flags = dict(previous_governance_snapshot.get("attention_flags") or {})
    current_flags = dict(current_governance_snapshot.get("attention_flags") or {})

    previous_action = str(previous_controller_action_plan.get("recommended_action") or "")
    current_action = str(current_controller_action_plan.get("recommended_action") or "")

    totals_delta = _delta_map(previous_totals, current_totals)
    review_delta = _delta_map(previous_review, current_review)
    validation_delta = _delta_map(previous_validation, current_validation)
    queue_delta = {
        "by_state": _delta_map(
            dict(previous_queue.get("by_state") or {}),
            dict(current_queue.get("by_state") or {}),
        ),
        "by_action": _delta_map(
            dict(previous_queue.get("by_action") or {}),
            dict(current_queue.get("by_action") or {}),
        ),
        "followup_by_branch": _delta_map(
            dict(previous_queue.get("followup_by_branch") or {}),
            dict(current_queue.get("followup_by_branch") or {}),
        ),
    }

    changed_flags = {
        key: {
            "previous": bool(previous_flags.get(key)),
            "current": bool(current_flags.get(key)),
        }
        for key in sorted(set(previous_flags) | set(current_flags))
        if bool(previous_flags.get(key)) != bool(current_flags.get(key))
    }

    delta = {
        "ok": True,
        "inputs": {
            "previous_governance_snapshot_path": str(previous_governance_snapshot.get("output_path") or ""),
            "current_governance_snapshot_path": str(current_governance_snapshot.get("output_path") or ""),
            "previous_controller_action_plan_path": str(previous_controller_action_plan.get("output_path") or ""),
            "current_controller_action_plan_path": str(current_controller_action_plan.get("output_path") or ""),
        },
        "previous": {
            "recommended_action": previous_action,
            "reason": str(previous_controller_action_plan.get("reason") or ""),
            "totals": previous_totals,
            "validation_state": previous_validation,
            "attention_flags": previous_flags,
        },
        "current": {
            "recommended_action": current_action,
            "reason": str(current_controller_action_plan.get("reason") or ""),
            "totals": current_totals,
            "validation_state": current_validation,
            "attention_flags": current_flags,
        },
        "delta": {
            "totals": totals_delta,
            "review_state": review_delta,
            "validation_state": validation_delta,
            "queue_state": queue_delta,
            "attention_flag_changes": changed_flags,
        },
        "status": {
            "recommended_action_changed": previous_action != current_action,
            "reason_changed": str(previous_controller_action_plan.get("reason") or "")
            != str(current_controller_action_plan.get("reason") or ""),
            "progress_signal": _progress_signal(
                previous_action=previous_action,
                current_action=current_action,
                totals_delta=totals_delta,
                validation_delta=validation_delta,
                previous_flags=previous_flags,
                current_flags=current_flags,
            ),
            "action_severity_delta": _ACTION_SEVERITY.get(current_action, 99) - _ACTION_SEVERITY.get(previous_action, 99),
        },
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(delta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    delta["output_path"] = str(out)
    return delta


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a cross-cycle progress delta for execution experience review governance.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--previous-governance-snapshot", required=True)
    parser.add_argument("--current-governance-snapshot", required=True)
    parser.add_argument("--previous-controller-action-plan", required=True)
    parser.add_argument("--current-controller-action-plan", required=True)
    args = parser.parse_args()

    previous_governance_snapshot = _load_json(args.previous_governance_snapshot)
    previous_governance_snapshot["output_path"] = args.previous_governance_snapshot
    current_governance_snapshot = _load_json(args.current_governance_snapshot)
    current_governance_snapshot["output_path"] = args.current_governance_snapshot
    previous_controller_action_plan = _load_json(args.previous_controller_action_plan)
    previous_controller_action_plan["output_path"] = args.previous_controller_action_plan
    current_controller_action_plan = _load_json(args.current_controller_action_plan)
    current_controller_action_plan["output_path"] = args.current_controller_action_plan

    result = build_delta(
        output_path=args.output,
        previous_governance_snapshot=previous_governance_snapshot,
        current_governance_snapshot=current_governance_snapshot,
        previous_controller_action_plan=previous_controller_action_plan,
        current_controller_action_plan=current_controller_action_plan,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
