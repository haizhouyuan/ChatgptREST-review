#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO.parent
DEFAULT_DOCS = PROJECT / "docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform"
PASS_STATUS = "FINBOT_ENGINEERING_CAPABILITY_PLATFORM_V1_PASS"
ALLOWED_READINESS = {
    "workflow_verified",
    "tool_callable_only",
    "endpoint_alive_only",
    "configured_but_unverified",
    "candidate_to_enable",
    "blocked",
    "quarantined_or_no_production_use",
}
GUARDED_CONNECTORS = {"Readwise", "Zotero", "Alpaca watch-only", "Daloopa", "Quartr", "Binance risk context"}
ALLOWED_DECISIONS = {"continue_research", "park", "reject", "needs_user_review"}
FORBIDDEN_FIELDS = {
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
REQUIRED_DOCS = [
    "00_execution_contract.md",
    "01_current_state_audit.md",
    "02_data_source_readiness_matrix.md",
    "02_data_source_readiness_matrix.json",
    "03_governed_connector_smoke_protocol.md",
    "03_connector_smoke_results.json",
    "04_skill_contracts_for_finbot_agents.md",
    "05_schema_extension_design.md",
    "06_validator_design.md",
    "07_runner_design.md",
    "08_valuation_range_research_prototype.md",
    "08_valuation_range_research_prototype.json",
    "09_alert_monitoring_prototype.md",
    "09_alert_monitoring_prototype.json",
    "10_decision_memo_prototype.md",
    "10_decision_memo_prototype.json",
    "11_engineering_to_research_handoff.md",
    "12_governance_approval_packet.md",
    "13_live_paperclip_readback.json",
    "14_final_validation.json",
    "15_closeout.md",
]
REQUIRED_CONTRACTS = [
    "contracts/finbot_capability_platform_v1.schema.json",
    "contracts/finbot_data_source_readiness_v1.json",
    "contracts/finbot_agent_skill_contracts_v1.json",
    "contracts/finbot_valuation_range_contract_v1.json",
    "contracts/finbot_alert_contract_v1.json",
    "contracts/finbot_decision_memo_contract_v1.json",
]
REQUIRED_TOOLS = [
    "tools/finbot_capability_smoke_runner.py",
    "tools/finbot_valuation_range_prototype.py",
    "tools/finbot_alert_prototype.py",
    "tools/finbot_decision_memo_prototype.py",
    "tools/finbot_capability_live_issue_runner.py",
    "tools/validate_finbot_capability_platform.py",
]
MINIMUM_SOURCES = {
    "SEC EDGAR submissions",
    "SEC companyfacts",
    "issuer IR pages",
    "earnings releases / filings",
    "Form 4",
    "13F as ownership context only",
    "Alpaca watch-only",
    "OpenBB if available",
    "local price CSV fixture fallback",
    "Binance risk context",
    "Daloopa",
    "Quartr",
    "Readwise",
    "Zotero",
    "Google Drive / local docs",
    "web-content-extractor / governed local HTML extraction",
    "Chrome DevTools / CDP evidence capture",
    "CNINFO",
    "SSE",
    "SZSE",
    "BSE",
    "AKShare",
    "Tushare",
    "Baostock",
    "Eastmoney / Tonghuashun downgraded secondary routes",
    "TradingAgents / TradingAgents-CN",
    "Fincept",
    "Qlib / vectorbt / Backtrader / Lean",
    "LangGraph / Agno / PydanticAI",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from walk(item, f"{path}[{idx}]")
    else:
        yield path, value


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    live_pending = False
    for path, value in walk(payload):
        key = path.split(".")[-1].split("[")[0]
        key_lower = key.lower()
        if key_lower in FORBIDDEN_FIELDS:
            errors.append(f"{path}: forbidden field {key_lower}")
        if key_lower == "decision_status" and str(value).lower() in FORBIDDEN_DECISIONS:
            errors.append(f"{path}: forbidden decision status {value}")
        if key_lower == "alert_scope" and str(value) != "human_review_alert":
            errors.append(f"{path}: alert_scope must be human_review_alert")
        if key_lower == "alert_type" and str(value).lower() in {"buy_signal", "sell_signal", "trade_signal"}:
            errors.append(f"{path}: forbidden alert type {value}")
        if key_lower == "range_type" and str(value) != "research_estimate_range":
            errors.append(f"{path}: valuation range must be research_estimate_range")
    return errors


def validate_matrix(matrix: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    sources = matrix.get("sources", [])
    names = {row.get("name") for row in sources}
    missing = sorted(MINIMUM_SOURCES - names)
    if missing:
        errors.append(f"missing required data sources: {missing}")
    workflow_verified = {row.get("name") for row in sources if row.get("status") == "workflow_verified"}
    for needed in ["SEC EDGAR submissions", "SEC companyfacts", "Google Drive / local docs", "web-content-extractor / governed local HTML extraction"]:
        if needed not in workflow_verified:
            errors.append(f"{needed} must remain workflow_verified with evidence")
    for row in sources:
        name = row.get("name")
        status = row.get("status")
        proof = row.get("proof_level")
        if status not in ALLOWED_READINESS:
            errors.append(f"{name}: invalid readiness status {status}")
        if status == "workflow_verified" and proof != "workflow_verified":
            errors.append(f"{name}: workflow_verified requires workflow proof, got {proof}")
        if status == "workflow_verified" and proof in {"endpoint_alive_only", "tool_callable_only", "surface_route_only"}:
            errors.append(f"{name}: endpoint/tool/surface proof counted as workflow verification")
        if name in GUARDED_CONNECTORS and status == "workflow_verified":
            errors.append(f"{name}: guarded connector cannot be workflow_verified in this phase")
    return errors


def validate_smoke(smoke: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if smoke.get("status") != "pass":
        errors.append("connector smoke status is not pass")
    by_source = {}
    for result in smoke.get("results", []):
        by_source.setdefault(result.get("source_id"), []).append(result)
    for source in ["sec_companyfacts", "sec_submissions", "google_drive_local_docs", "web_extraction_local_html", "local_price_fixture"]:
        if not any(row.get("status") == "pass" and row.get("proof_level") == "workflow_verified" for row in by_source.get(source, [])):
            errors.append(f"{source}: missing workflow smoke pass")
    for connector in GUARDED_CONNECTORS:
        if not any(row.get("status") == "blocked_candidate" for row in by_source.get(connector, [])):
            errors.append(f"{connector}: missing blocked candidate smoke record")
    return errors


def validate_valuation(payload: dict[str, Any]) -> list[str]:
    errors = validate_payload(payload)
    for entry in payload.get("entries", []):
        if entry.get("range_type") != "research_estimate_range":
            errors.append(f"{entry.get('case_id')}: valuation range_type is not research_estimate_range")
        for field in ["method", "assumptions", "bear", "base", "bull", "evidence_ids", "invalidation", "no_advice_label"]:
            if not entry.get(field):
                errors.append(f"{entry.get('case_id')}: missing valuation field {field}")
        if "target price" not in str(entry.get("no_advice_label", "")).lower():
            errors.append(f"{entry.get('case_id')}: no_advice_label must explicitly reject target-price use")
    return errors


def validate_alerts(payload: dict[str, Any]) -> list[str]:
    errors = validate_payload(payload)
    for alert in payload.get("alerts", []):
        if alert.get("alert_scope") != "human_review_alert":
            errors.append(f"{alert.get('alert_id')}: alert is not human_review_alert")
        if not alert.get("human_review_question") or not alert.get("evidence_ids"):
            errors.append(f"{alert.get('alert_id')}: missing evidence or human review question")
    return errors


def validate_memos(payload: dict[str, Any]) -> list[str]:
    errors = validate_payload(payload)
    for memo in payload.get("memos", []):
        status = memo.get("decision_status")
        if status not in ALLOWED_DECISIONS:
            errors.append(f"{memo.get('memo_id')}: invalid decision_status {status}")
        for field in ["thesis", "source_alpha_rationale", "primary_evidence", "counter_evidence", "open_questions"]:
            if not memo.get(field):
                errors.append(f"{memo.get('memo_id')}: missing memo field {field}")
    return errors


def validate_negative_fixtures() -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    results = []
    for path in sorted((REPO / "fixtures/capability_platform/negative").glob("*.json")):
        payload = read_json(path)
        fixture_errors: list[str] = []
        if "sources" in payload:
            fixture_errors.extend(validate_matrix({"sources": payload["sources"]}))
        fixture_errors.extend(validate_payload(payload))
        passed = bool(fixture_errors)
        if not passed:
            errors.append(f"negative fixture did not fail: {path.name}")
        results.append({
            "fixture": path.name,
            "expected_error": payload.get("expected_error"),
            "failed_as_expected": passed,
            "errors": fixture_errors,
        })
    return errors, results


def validate_live_readback(path: Path, allow_pending_live: bool) -> list[str]:
    live = read_json(path)
    if allow_pending_live and live.get("status") == "PENDING_LIVE_READBACK":
        return []
    errors: list[str] = []
    if live.get("status") != "PASS_LIVE_READBACK":
        errors.append("live readback is not PASS_LIVE_READBACK")
    roles = {row.get("role") for row in live.get("issues", [])}
    for required in ["engineering_implementation", "governance_boundary", "finbot_research_handoff"]:
        if required not in roles:
            errors.append(f"missing live issue role {required}")
    identifiers = [row.get("identifier") for row in live.get("issues", [])]
    issue_ids = [row.get("issueId") for row in live.get("issues", [])]
    comment_ids = [(row.get("acceptedComment") or {}).get("id") for row in live.get("issues", [])]
    run_ids = [(row.get("acceptedRun") or {}).get("id") for row in live.get("issues", [])]
    if len([x for x in identifiers if x]) != len(set(x for x in identifiers if x)):
        errors.append("live readback reuses the same issue identifier across roles")
    if len([x for x in issue_ids if x]) != len(set(x for x in issue_ids if x)):
        errors.append("live readback reuses the same issue id across roles")
    if len([x for x in comment_ids if x]) != len(set(x for x in comment_ids if x)):
        errors.append("live readback reuses the same accepted comment across roles")
    if len([x for x in run_ids if x]) != len(set(x for x in run_ids if x)):
        errors.append("live readback reuses the same accepted run across roles")
    for issue in live.get("issues", []):
        ident = issue.get("identifier")
        role = issue.get("role")
        run = issue.get("acceptedRun") or {}
        comment = issue.get("acceptedComment") or {}
        if issue.get("issueStatus") != "done":
            errors.append(f"{ident}: issue status is not done")
        if role == "governance_boundary" and not str(ident).startswith("PAPA-"):
            errors.append(f"{ident}: governance boundary role must be a Governance issue")
        if role in {"engineering_implementation", "finbot_research_handoff"} and not str(ident).startswith("FIN-"):
            errors.append(f"{ident}: {role} role must be carried by a Finbot Research issue when no Engineering company exists")
        if run.get("status") != "succeeded":
            errors.append(f"{ident}: accepted run not succeeded")
        if comment.get("createdByRunId") != run.get("id"):
            errors.append(f"{ident}: comment not bound to accepted run")
        body = str(comment.get("bodyHead", ""))
        if PASS_STATUS not in body:
            errors.append(f"{ident}: accepted comment missing pass token")
        if "capability platform" not in body.lower():
            errors.append(f"{ident}: accepted comment missing capability platform scope")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-root", default=str(DEFAULT_DOCS))
    parser.add_argument("--allow-pending-live", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    docs_root = Path(args.docs_root)
    errors: list[str] = []

    for name in REQUIRED_DOCS:
        target = docs_root / name
        if not target.exists() and not (args.output and target.resolve() == Path(args.output).resolve()):
            errors.append(f"missing deliverable {name}")
    for name in REQUIRED_CONTRACTS + REQUIRED_TOOLS:
        if not (REPO / name).exists():
            errors.append(f"missing implementation artifact {name}")

    readme = (REPO / "README.md").read_text(encoding="utf-8")
    if "capability_lab_v1" not in readme:
        errors.append("README does not declare capability_lab_v1")
    if "no broker" not in readme.lower() or "no production watchlist" not in readme.lower():
        errors.append("README does not preserve no-broker/no-watchlist boundaries")

    matrix = read_json(docs_root / "02_data_source_readiness_matrix.json") if (docs_root / "02_data_source_readiness_matrix.json").exists() else {}
    smoke = read_json(docs_root / "03_connector_smoke_results.json") if (docs_root / "03_connector_smoke_results.json").exists() else {}
    valuation = read_json(docs_root / "08_valuation_range_research_prototype.json") if (docs_root / "08_valuation_range_research_prototype.json").exists() else {}
    alerts = read_json(docs_root / "09_alert_monitoring_prototype.json") if (docs_root / "09_alert_monitoring_prototype.json").exists() else {}
    memos = read_json(docs_root / "10_decision_memo_prototype.json") if (docs_root / "10_decision_memo_prototype.json").exists() else {}

    errors.extend(validate_matrix(matrix))
    errors.extend(validate_smoke(smoke))
    errors.extend(validate_valuation(valuation))
    errors.extend(validate_alerts(alerts))
    errors.extend(validate_memos(memos))
    negative_errors, negative_results = validate_negative_fixtures()
    errors.extend(negative_errors)
    live_path = docs_root / "13_live_paperclip_readback.json"
    live_pending = False
    if args.allow_pending_live and live_path.exists() and read_json(live_path).get("status") == "PENDING_LIVE_READBACK":
        live_pending = True
    errors.extend(validate_live_readback(live_path, args.allow_pending_live))

    status = PASS_STATUS if not errors and not live_pending else ("PRE_LIVE_PASS_PENDING_LIVE" if not errors else "failed")
    result = {
        "schema": "finbot_engineering.final_validation.v1",
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "status": status,
        "passed": not errors and not live_pending,
        "complete_allowed": not errors and not live_pending,
        "pre_live_pass": not errors and live_pending,
        "errors": errors,
        "metrics": {
            "sources": len(matrix.get("sources", [])),
            "workflow_verified_sources": sum(1 for row in matrix.get("sources", []) if row.get("status") == "workflow_verified"),
            "skill_contracts": len(read_json(REPO / "contracts/finbot_agent_skill_contracts_v1.json").get("skills", [])) if (REPO / "contracts/finbot_agent_skill_contracts_v1.json").exists() else 0,
            "valuation_entries": len(valuation.get("entries", [])),
            "alerts": len(alerts.get("alerts", [])),
            "decision_memos": len(memos.get("memos", [])),
            "negative_fixtures": len(negative_results),
        },
        "negative_fixture_results": negative_results,
    }
    output = Path(args.output) if args.output else docs_root / "14_final_validation.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
