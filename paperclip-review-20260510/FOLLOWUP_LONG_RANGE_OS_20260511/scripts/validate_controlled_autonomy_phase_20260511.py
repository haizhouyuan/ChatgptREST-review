#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


FORBIDDEN_TEXT = [
    "investment advice",
    "target price recommendation",
    "trade signal",
    "automatic trading",
    "broker action",
    "production watchlist",
    "local llm production route",
    "authority without governance",
]


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_controlled_autonomy_phase_20260511.py <phase8-root>", file=sys.stderr)
        return 2

    root = Path(sys.argv[1])
    errors: list[dict[str, str]] = []
    required_files = [
        "autonomy_policy.md",
        "autonomy_trial_runs.jsonl",
        "human_interrupt_log.jsonl",
        "final_readiness_audit.md",
    ]
    for rel in required_files:
        if not (root / rel).exists():
            errors.append({"code": "missing_required_file", "path": str(root / rel)})

    policy = root / "autonomy_policy.md"
    if policy.exists():
        text = policy.read_text(encoding="utf-8").lower()
        for level in ["l0_manual_controller", "l1_supervised_company_runs", "l2_scheduler_with_stop_gates", "l3_governed_autonomous_research", "l4_production_autonomy"]:
            if level not in text:
                errors.append({"code": "policy_missing_autonomy_level", "level": level})
        if "l4_production_autonomy: not in scope" not in text:
            errors.append({"code": "policy_l4_not_explicitly_out_of_scope"})

    trials_path = root / "autonomy_trial_runs.jsonl"
    if trials_path.exists():
        try:
            trials = read_jsonl(trials_path)
        except Exception as exc:  # noqa: BLE001
            trials = []
            errors.append({"code": "invalid_trial_jsonl", "error": repr(exc)})
        l1 = [row for row in trials if row.get("autonomy_level") == "L1_supervised_company_runs" and row.get("status") == "accepted"]
        l2 = [row for row in trials if row.get("autonomy_level") == "L2_scheduler_with_stop_gates" and row.get("status") == "accepted"]
        companies = {row.get("company") for row in l1}
        if len(l1) < 3:
            errors.append({"code": "too_few_l1_trials", "count": str(len(l1))})
        for required in ["Planning Work Assistant", "Finbot Investment Research", "Paperclip Governance Company"]:
            if required not in companies:
                errors.append({"code": "missing_l1_company", "company": required})
        if len(l2) < 1:
            errors.append({"code": "missing_l2_scheduler_trial"})
        for row in trials:
            boundary = row.get("boundary", {})
            for key in [
                "investment_advice",
                "target_price_recommendation",
                "trade_signal",
                "automatic_trading",
                "broker_action",
                "production_watchlist",
                "local_llm_production_route",
                "authority_without_governance",
            ]:
                if boundary.get(key) is not False:
                    errors.append({"code": "trial_boundary_not_false", "trial_id": str(row.get("trial_id")), "key": key})

    final_audit = root / "final_readiness_audit.md"
    if final_audit.exists():
        text = final_audit.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_TEXT:
            if phrase in text and "forbidden" not in text:
                errors.append({"code": "ambiguous_forbidden_phrase", "phrase": phrase})
        for marker in ["phase 0", "phase 1", "phase 2", "phase 3", "phase 4", "phase 5", "phase 6", "phase 7", "phase 8"]:
            if marker not in text:
                errors.append({"code": "final_audit_missing_phase_marker", "marker": marker})
        if "paperclip is not claimed production-ready" not in text:
            errors.append({"code": "missing_non_production_ready_claim"})

    result = {
        "schema": "paperclip.long_range.phase8.controlled_autonomy.validator.v1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }
    out = root / "validator_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
