#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO / "docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery"
PASS_STATUS = "PAPERCLIP_OVERNIGHT_ALL_COMPANY_OPS_PASS"
TZ = timezone(timedelta(hours=8))
FORBIDDEN_KEYS = {
    "target_price",
    "price_target",
    "recommendation",
    "broker_action",
    "order_action",
    "production_watchlist",
    "trade_signal",
    "position_size",
    "allocation",
}
FORBIDDEN_DECISIONS = {"buy", "sell", "hold", "add", "trim", "reduce", "exit"}
ALLOWED_DECISIONS = {"continue_research", "park", "reject", "needs_user_review"}


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for k, v in value.items():
            yield path, k, v
            yield from walk(v, f"{path}.{k}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from walk(item, f"{path}[{idx}]")


def validate_payload(payload: Any) -> list[str]:
    errors = []
    for path, key, value in walk(payload):
        if key in FORBIDDEN_KEYS:
            errors.append(f"{path}.{key}: forbidden key")
        if key == "decision_status" and str(value).lower() in FORBIDDEN_DECISIONS:
            errors.append(f"{path}.{key}: forbidden decision status {value}")
        if key == "decision_status" and str(value) not in ALLOWED_DECISIONS:
            errors.append(f"{path}.{key}: decision status outside allowed set {value}")
        if key == "range_type" and value != "research_estimate_range":
            errors.append(f"{path}.{key}: valuation range must be research_estimate_range")
        if key == "alert_scope" and value != "human_review_alert":
            errors.append(f"{path}.{key}: alert scope must be human_review_alert")
    return errors


def validate_counts(root: Path, errors: list[str]) -> dict[str, Any]:
    runtime = read_json(root / "runtime_summary.json")
    counts = runtime.get("counts") or {}
    if runtime.get("wall_clock_hours", 0) < 8:
        errors.append(f"wall_clock_hours below 8: {runtime.get('wall_clock_hours')}")
    if counts.get("cycles", 0) < 10:
        errors.append(f"effective cycles below 10: {counts.get('cycles')}")
    thresholds = {
        "sources": 120,
        "themes": 50,
        "opportunity_candidates": 180,
        "alpha_qualified_cases": 40,
        "full_decision_memos": 18,
        "top_surprising_opportunities": 20,
    }
    for key, threshold in thresholds.items():
        if counts.get(key, 0) < threshold:
            errors.append(f"{key} below threshold: {counts.get(key)} < {threshold}")
    return runtime


def validate_cycles(root: Path, errors: list[str]) -> list[dict[str, Any]]:
    all_cycles = read_json(root / "16_cycle_by_cycle_substantive_delta_audit.json")
    cycles = [c for c in all_cycles if c.get("counted_effective") is not False]
    if len(cycles) < 10:
        errors.append("effective cycle audit has fewer than 10 cycles")
    for idx, cycle in enumerate(all_cycles, start=1):
        if cycle.get("counted_effective") is False:
            continue
        if cycle.get("sleep_only"):
            errors.append(f"{cycle.get('cycle_id')}: sleep_only cycle")
        if cycle.get("new_sources", 0) <= 0:
            errors.append(f"{cycle.get('cycle_id')}: no new sources")
        if cycle.get("new_themes", 0) <= 0:
            errors.append(f"{cycle.get('cycle_id')}: no new themes")
        if cycle.get("new_candidates", 0) <= 0:
            errors.append(f"{cycle.get('cycle_id')}: no new opportunity candidates")
        if cycle.get("primary_evidence_rows", 0) <= 0:
            errors.append(f"{cycle.get('cycle_id')}: no primary evidence rows")
        substantive = cycle.get("substantive_delta") or []
        if len(substantive) < 5:
            errors.append(f"{cycle.get('cycle_id')}: insufficient substantive delta categories")
        if idx > 1:
            try:
                previous = datetime.fromisoformat(all_cycles[idx - 2]["started_at"])
                current = datetime.fromisoformat(cycle["started_at"])
                gap_minutes = (current - previous).total_seconds() / 60
                if gap_minutes < 30 or gap_minutes > 45:
                    errors.append(f"{cycle.get('cycle_id')}: cycle start gap outside 30-45 minutes: {gap_minutes:.2f}")
            except (KeyError, ValueError, TypeError) as exc:
                errors.append(f"{cycle.get('cycle_id')}: cannot parse cycle interval: {exc}")
    return cycles


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_global_cycles(root: Path, errors: list[str]) -> list[dict[str, Any]]:
    all_cycles = load_jsonl(root / "cycle_ledger.jsonl")
    cycles = [c for c in all_cycles if c.get("counted_effective") is not False]
    if len(cycles) < 12:
        errors.append(f"global effective cycle ledger below 12: {len(cycles)}")
    for idx, cycle in enumerate(cycles, start=1):
        if cycle.get("sleep_only"):
            errors.append(f"{cycle.get('cycle_id')}: global sleep_only cycle")
        if not cycle.get("substantive_delta"):
            errors.append(f"{cycle.get('cycle_id')}: missing global substantive_delta")
        if idx > 1:
            try:
                previous = datetime.fromisoformat(cycles[idx - 2]["generated_at"])
                current = datetime.fromisoformat(cycle["generated_at"])
                gap_minutes = (current - previous).total_seconds() / 60
                if gap_minutes < 20 or gap_minutes > 45:
                    errors.append(f"{cycle.get('cycle_id')}: global cycle gap outside 20-45 minutes: {gap_minutes:.2f}")
            except (KeyError, ValueError, TypeError) as exc:
                errors.append(f"{cycle.get('cycle_id')}: cannot parse global cycle interval: {exc}")
    return cycles


def validate_top_cases(root: Path, errors: list[str]) -> list[dict[str, Any]]:
    top = read_json(root / "06_top_surprising_opportunities.json")
    if len(top) < 20:
        errors.append("top surprising opportunities below 20")
    required = [
        "variant_thesis",
        "source_alpha_rationale",
        "primary_evidence_ids",
        "counter_evidence",
        "research_estimate_range",
        "catalyst_watch_window",
        "human_review_question",
    ]
    for case in top:
        cid = case.get("case_id")
        for field in required:
            if not case.get(field):
                errors.append(f"{cid}: missing {field}")
        ev = case.get("primary_evidence_ids") or []
        if not ev:
            errors.append(f"{cid}: top case has no primary evidence")
        if len(case.get("counter_evidence") or []) < 1:
            errors.append(f"{cid}: missing counter evidence")
        rng = case.get("research_estimate_range") or {}
        if rng.get("range_type") != "research_estimate_range":
            errors.append(f"{cid}: valuation range is not research_estimate_range")
        errors.extend(validate_payload(case))
    return top


def validate_live(root: Path, errors: list[str], allow_pending_live: bool) -> dict[str, Any]:
    live = read_json(root / "15_live_paperclip_readback.json")
    if allow_pending_live and live.get("status") == "PENDING_LIVE_READBACK":
        return live
    if live.get("status") != "PASS_LIVE_READBACK":
        errors.append("live readback is not PASS_LIVE_READBACK")
    roles = {i.get("role") for i in live.get("issues", [])}
    required_roles = [
        "finbot_research",
        "finbot_engineering",
        "planning",
        "governance",
        "memory",
        "skill_mcp",
        "runtime",
        "learning_research",
        "local_llm",
        "labebe",
    ]
    carrier_gaps = {i.get("role") for i in live.get("carrierGaps", [])}
    for role in required_roles:
        if role not in roles and role not in carrier_gaps:
            errors.append(f"missing live role {role}")
    ids = [i.get("identifier") for i in live.get("issues", []) if i.get("identifier")]
    if len(ids) != len(set(ids)):
        errors.append("live readback reuses issue identifier across roles")
    for issue in live.get("issues", []):
        ident = issue.get("identifier")
        run = issue.get("acceptedRun") or {}
        comment = issue.get("acceptedComment") or {}
        if issue.get("issueStatus") != "done":
            errors.append(f"{ident}: issue status is not done")
        if run.get("status") != "succeeded":
            errors.append(f"{ident}: accepted run not succeeded")
        if comment.get("createdByRunId") != run.get("id"):
            errors.append(f"{ident}: accepted comment not bound to accepted run")
        body = str(comment.get("bodyHead") or "")
        if PASS_STATUS not in body:
            errors.append(f"{ident}: accepted comment missing pass token")
        if "overnight" not in body.lower() and "open-ended alpha discovery" not in body.lower() and "open ended alpha discovery" not in body.lower():
            errors.append(f"{ident}: accepted comment missing overnight/open-ended alpha discovery scope")
    return live


def validate_negative_fixtures(errors: list[str]) -> list[dict[str, Any]]:
    fixtures = [
        {"name": "advice_output", "payload": {"decision_status": "buy", "recommendation": "buy"}},
        {"name": "target_price_as_advice", "payload": {"range_type": "target_price", "target_price": 42}},
        {"name": "broker_action", "payload": {"decision_status": "continue_research", "broker_action": "place_order"}},
        {"name": "production_watchlist", "payload": {"alert_scope": "production_watchlist", "trade_signal": "entry"}},
    ]
    results = []
    for fixture in fixtures:
        fixture_errors = validate_payload(fixture["payload"])
        if not fixture_errors:
            errors.append(f"negative fixture did not fail: {fixture['name']}")
        results.append({"fixture": fixture["name"], "failed_as_expected": bool(fixture_errors), "errors": fixture_errors})
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--allow-pending-live", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    root = Path(args.root)
    errors: list[str] = []
    required_files = [
        "00_goal_contract.md",
        "01_history_asset_coverage.json",
        "01b_history_asset_content_hits.json",
        "01_source_registry.yaml",
        "02_source_cards.tsv",
        "03_source_alpha_map.json",
        "04_theme_map.json",
        "05_opportunity_board.json",
        "06_top_surprising_opportunities.json",
        "07_alpha_qualified_casebook.json",
        "08_full_decision_memo_pack.json",
        "08_parked_noise_rejected_register.json",
        "09_evidence_ledger.json",
        "09_claim_ledger.json",
        "10_valuation_range_pack.json",
        "11_risk_reversal_qa_pack.json",
        "12_human_review_queue.json",
        "13_next_7_day_research_campaign.json",
        "14_governance_false_pass_audit.json",
        "15_live_paperclip_readback.json",
        "16_cycle_by_cycle_substantive_delta_audit.json",
        "17_current_truth.json",
        "18_blocker_board.json",
        "19_execution_matrix.json",
        "runtime_summary.json",
    ]
    for name in required_files:
        if not (root / name).exists():
            errors.append(f"missing required artifact {name}")
    runtime = validate_counts(root, errors) if (root / "runtime_summary.json").exists() else {}
    if (root / "01_history_asset_coverage.json").exists():
        coverage = read_json(root / "01_history_asset_coverage.json")
        if coverage.get("found_count", 0) < 100:
            errors.append(f"history asset path coverage too low: {coverage.get('found_count')}")
        if coverage.get("pro_or_review_count", 0) < 10:
            errors.append(f"Pro/advisor/critical-review path coverage too low: {coverage.get('pro_or_review_count')}")
    if (root / "01b_history_asset_content_hits.json").exists():
        content_hits = read_json(root / "01b_history_asset_content_hits.json")
        if content_hits.get("hit_count", 0) < 100:
            errors.append(f"history asset content coverage too low: {content_hits.get('hit_count')}")
    cycles = validate_cycles(root, errors) if (root / "16_cycle_by_cycle_substantive_delta_audit.json").exists() else []
    global_cycles = validate_global_cycles(root, errors)
    top = validate_top_cases(root, errors) if (root / "06_top_surprising_opportunities.json").exists() else []
    live = validate_live(root, errors, args.allow_pending_live) if (root / "15_live_paperclip_readback.json").exists() else {}
    if (REPO / "docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/02_data_source_readiness_matrix.json").exists():
        matrix = read_json(REPO / "docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/02_data_source_readiness_matrix.json")
        workflow_verified = [s for s in matrix.get("sources", []) if s.get("status") == "workflow_verified"]
        if len(workflow_verified) < 6:
            errors.append(f"workflow-verified data/source capability below 6: {len(workflow_verified)}")
    if (root / "company_execution_matrix.json").exists():
        matrix = read_json(root / "company_execution_matrix.json")
        companies = matrix.get("companies", [])
        valid_company_statuses = {
            "in_progress",
            "local_complete",
            "done",
            "live_accepted",
            "carrier_gap_recorded",
        }
        touched = {c.get("company") for c in companies if c.get("status") in valid_company_statuses}
        if len(touched) < 10:
            errors.append(f"company execution matrix below 10 company lines: {len(touched)}")
    else:
        errors.append("missing company_execution_matrix.json")
    for name in ["05_opportunity_board.json", "07_alpha_qualified_casebook.json", "08_full_decision_memo_pack.json", "10_valuation_range_pack.json", "12_human_review_queue.json"]:
        if (root / name).exists():
            errors.extend(validate_payload(read_json(root / name)))
    negative = validate_negative_fixtures(errors)
    status = PASS_STATUS if not errors and not args.allow_pending_live else (
        "PRE_LIVE_PASS_PENDING_LIVE" if not errors else "failed"
    )
    result = {
        "schema": "finbot.open_alpha.final_validation.v1",
        "generated_at": now_iso(),
        "status": status,
        "passed": status == PASS_STATUS,
        "complete_allowed": status == PASS_STATUS,
        "errors": errors,
        "runtime": runtime,
        "cycle_count": len(cycles),
        "global_cycle_count": len(global_cycles),
        "top_case_count": len(top),
        "live_status": live.get("status"),
        "negative_fixture_results": negative,
    }
    output = Path(args.output) if args.output else root / "20_final_validation.json"
    write_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
