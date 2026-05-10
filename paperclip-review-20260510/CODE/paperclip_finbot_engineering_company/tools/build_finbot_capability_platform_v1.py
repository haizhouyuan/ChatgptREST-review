#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO.parent
DOC_ROOT = PROJECT / "docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform"
RESEARCH_ROOT = PROJECT / "docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp"
NOW = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
PASS_STATUS = "FINBOT_ENGINEERING_CAPABILITY_PLATFORM_V1_PASS"
FORBIDDEN_OUTPUTS = [
    "investment_advice",
    "broker_action",
    "production_watchlist",
    "trade_signal",
    "position_size",
    "automatic_trading",
]
GUARDED_CONNECTORS = {
    "Readwise",
    "Zotero",
    "Alpaca watch-only",
    "Daloopa",
    "Quartr",
    "Binance risk context",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def load_alpha_cases() -> list[dict[str, Any]]:
    return read_json(RESEARCH_ROOT / "69_alpha_quality_casebook.json")["cases"]


def source_record(
    source_id: str,
    category: str,
    name: str,
    status: str,
    proof_level: str,
    role: str,
    evidence_path: str,
    allowed: str,
    disallowed: str,
    governance_followup: str | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "category": category,
        "name": name,
        "status": status,
        "proof_level": proof_level,
        "read_only_scope": True,
        "secret_boundary": "no secrets read or emitted; no account mutation",
        "role_for_finbot": role,
        "evidence_path": evidence_path,
        "allowed_downstream_use": allowed,
        "disallowed_downstream_use": disallowed,
        "governance_followup": governance_followup,
    }


def build_readiness_matrix() -> list[dict[str, Any]]:
    rows = [
        source_record("sec_submissions", "US/global primary evidence", "SEC EDGAR submissions", "workflow_verified", "workflow_verified", "primary filing route and filing update detection", "primary_evidence/sec_submissions/* + artifacts/capability_platform_v1/connector_smoke_results.json", "primary evidence lookup, filing update alerts", "advice, trading, broker action"),
        source_record("sec_companyfacts", "US/global primary evidence", "SEC companyfacts", "workflow_verified", "workflow_verified", "primary XBRL financial facts", "primary_evidence/sec_companyfacts/* + artifacts/capability_platform_v1/connector_smoke_results.json", "company fundamentals and evidence binding", "price signal or target-price output"),
        source_record("issuer_ir_pages", "US/global primary evidence", "issuer IR pages", "candidate_to_enable", "not_verified", "company primary releases and presentations", "12_governance_approval_packet.md", "candidate for primary evidence after smoke", "workflow use before read-only smoke", "GOV-FINBOT-CAP-IR"),
        source_record("earnings_releases_filings", "US/global primary evidence", "earnings releases / filings", "workflow_verified", "workflow_verified", "SEC/issuer filing documents already captured for alpha cases", "primary_evidence/sec_filings/*", "primary evidence lookup and filing alert", "earnings surprise trading signal"),
        source_record("form4", "US/global primary evidence", "Form 4", "configured_but_unverified", "surface_route_only", "insider activity context", "02_data_source_readiness_matrix.json", "ownership/catalyst context after smoke", "real-time insider trade signal", "GOV-FINBOT-CAP-FORM4"),
        source_record("13f_context", "US/global primary evidence", "13F as ownership context only", "configured_but_unverified", "surface_route_only", "delayed ownership idea source", "02_data_source_readiness_matrix.json", "ownership context with 45-day lag label", "current-holding claim or follow-trade use", "GOV-FINBOT-CAP-13F"),
        source_record("alpaca_watch_only", "Market data / price context", "Alpaca watch-only", "candidate_to_enable", "not_verified", "US price context if Governance approves read-only workflow", "33_governance_enablement_issue_contracts.json:PAPA-46", "watch-only market context after workflow proof", "orders, account, broker action, trade signal", "PAPA-46"),
        source_record("openbb_candidate", "Market data / price context", "OpenBB if available", "candidate_to_enable", "not_verified", "future data gateway candidate", "02_data_source_readiness_matrix.json", "candidate data access after install/smoke approval", "unverified production data feed", "GOV-FINBOT-CAP-OPENBB"),
        source_record("local_price_fixture", "Market data / price context", "local price CSV fixture fallback", "workflow_verified", "workflow_verified", "offline non-decision market context fixture", "paperclip_finbot_engineering_company/fixtures/capability_platform/local_price_context_fixture.csv", "prototype valuation context and validator tests", "live price readiness claim"),
        source_record("public_exchange_pages", "Market data / price context", "public exchange pages where legal and capturable", "candidate_to_enable", "not_verified", "future public page evidence capture", "03_governed_connector_smoke_protocol.md", "candidate exchange context after legal/read-only review", "automated scraping without governance", "GOV-FINBOT-CAP-EXCHANGE-PAGES"),
        source_record("binance_risk_context", "Market data / price context", "Binance risk context", "candidate_to_enable", "not_verified", "crypto risk and macro liquidity context candidate only", "33_governance_enablement_issue_contracts.json:PAPA-49", "candidate crypto risk context after approval and read-only smoke", "mainline source, trading, broker/account action, trade signal, or workflow_verified claim before proof", "PAPA-49"),
        source_record("daloopa", "Fundamentals / KPI / transcripts", "Daloopa", "candidate_to_enable", "not_verified", "company KPI and fundamentals candidate", "33_governance_enablement_issue_contracts.json:PAPA-47", "candidate KPI after approval and smoke", "claiming current workflow verification", "PAPA-47"),
        source_record("quartr", "Fundamentals / KPI / transcripts", "Quartr", "candidate_to_enable", "not_verified", "IR materials and transcripts candidate", "33_governance_enablement_issue_contracts.json:PAPA-48", "candidate transcript/IR after approval and smoke", "claiming current workflow verification", "PAPA-48"),
        source_record("sec_filings_fundamentals", "Fundamentals / KPI / transcripts", "SEC filings", "workflow_verified", "workflow_verified", "primary company fundamentals and risk factors", "primary_evidence/sec_filings/*", "company fundamentals, evidence, stale-filing alerts", "investment conclusion without review"),
        source_record("company_ir_candidate", "Fundamentals / KPI / transcripts", "company IR", "candidate_to_enable", "not_verified", "primary issuer updates outside SEC", "03_governed_connector_smoke_protocol.md", "candidate after capture protocol", "unverified transcript workflow", "GOV-FINBOT-CAP-IR"),
        source_record("readwise", "Knowledge / source tracking", "Readwise", "candidate_to_enable", "not_verified", "blogger/newsletter source tracking candidate", "33_governance_enablement_issue_contracts.json:PAPA-44", "candidate source discovery after approval", "authority evidence or production ingestion before smoke", "PAPA-44"),
        source_record("zotero", "Knowledge / source tracking", "Zotero", "candidate_to_enable", "not_verified", "research library candidate", "33_governance_enablement_issue_contracts.json:PAPA-45", "candidate document store after approval", "claiming current lane availability", "PAPA-45"),
        source_record("google_drive_local_docs", "Knowledge / source tracking", "Google Drive / local docs", "workflow_verified", "workflow_verified", "local historical docs and current artifact package", "/vol1/maint/docs + docs/finbot_research_os_v1/*", "local evidence and historical-method intake", "assuming Drive remote connector availability"),
        source_record("web_extraction_local_html", "Knowledge / source tracking", "web-content-extractor / governed local HTML extraction", "workflow_verified", "workflow_verified", "read-only content extraction from captured official HTML artifacts", "primary_evidence/sec_filings/* + artifacts/capability_platform_v1/connector_smoke_results.json", "evidence capture/excerpt from approved artifacts", "unapproved scraping or quarantined provider extraction"),
        source_record("chrome_devtools_cdp", "Knowledge / source tracking", "Chrome DevTools / CDP evidence capture", "tool_callable_only", "tool_callable_only", "browser evidence capture candidate; no Finbot workflow proof in this lane", "02_data_source_readiness_matrix.json", "candidate manual evidence capture after Governance protocol", "workflow_verified claim without smoke", "GOV-FINBOT-CAP-CDP"),
        source_record("cninfo", "A-share / China route candidates", "CNINFO", "candidate_to_enable", "not_verified", "A-share official disclosure route", "12_governance_approval_packet.md", "future official A-share evidence", "current workflow claim", "GOV-FINBOT-CAP-CNINFO"),
        source_record("sse", "A-share / China route candidates", "SSE", "candidate_to_enable", "not_verified", "SSE official disclosure route", "12_governance_approval_packet.md", "future official A-share evidence", "current workflow claim", "GOV-FINBOT-CAP-SSE"),
        source_record("szse", "A-share / China route candidates", "SZSE", "candidate_to_enable", "not_verified", "SZSE official disclosure route", "12_governance_approval_packet.md", "future official A-share evidence", "current workflow claim", "GOV-FINBOT-CAP-SZSE"),
        source_record("bse", "A-share / China route candidates", "BSE", "candidate_to_enable", "not_verified", "BSE official disclosure route", "12_governance_approval_packet.md", "future official A-share evidence", "current workflow claim", "GOV-FINBOT-CAP-BSE"),
        source_record("akshare", "A-share / China route candidates", "AKShare", "candidate_to_enable", "not_verified", "A-share data interface candidate", "12_governance_approval_packet.md", "future DataContract-backed A-share research", "production data without PIT/field contract", "GOV-FINBOT-CAP-AKSHARE"),
        source_record("tushare", "A-share / China route candidates", "Tushare", "candidate_to_enable", "not_verified", "permissioned A-share data candidate", "12_governance_approval_packet.md", "future DataContract-backed A-share research", "credential use without approval", "GOV-FINBOT-CAP-TUSHARE"),
        source_record("baostock", "A-share / China route candidates", "Baostock", "candidate_to_enable", "not_verified", "A-share historical data candidate", "12_governance_approval_packet.md", "future backtest research after PIT review", "validated signal before proof", "GOV-FINBOT-CAP-BAOSTOCK"),
        source_record("eastmoney_tonghuashun", "A-share / China route candidates", "Eastmoney / Tonghuashun downgraded secondary routes", "candidate_to_enable", "not_verified", "downgraded secondary context only", "12_governance_approval_packet.md", "secondary context with primary corroboration", "authority evidence or automated scrape without legal review", "GOV-FINBOT-CAP-SECONDARY-CN"),
        source_record("tradingagents_reference", "Research and validation frameworks", "TradingAgents / TradingAgents-CN", "candidate_to_enable", "method_reference_only", "multi-role debate/escalation reference", "05_schema_extension_design.md", "method reference only", "runtime authority or advice engine"),
        source_record("fincept_reference", "Research and validation frameworks", "Fincept", "candidate_to_enable", "method_reference_only", "terminal/workbench reference", "05_schema_extension_design.md", "UX/workbench reference only", "decision authority"),
        source_record("qlib_vectorbt_backtrader_lean", "Research and validation frameworks", "Qlib / vectorbt / Backtrader / Lean", "candidate_to_enable", "not_verified", "future validation/backtest candidates", "12_governance_approval_packet.md", "future signal research with PIT fixtures", "approved signal without backtest proof"),
        source_record("langgraph_agno_pydanticai", "Research and validation frameworks", "LangGraph / Agno / PydanticAI", "candidate_to_enable", "method_reference_only", "orchestration/schema candidates", "05_schema_extension_design.md", "future controlled workflow design", "runtime mutation without approval"),
        source_record("minimax_deepseek_tavily_brave", "Provider quarantine", "MiniMax / DeepSeek / Tavily / Brave", "quarantined_or_no_production_use", "no_production_use", "provider quarantine register", "32_tool_routing_policy_operational.md", "none in this phase", "any production/research execution path"),
    ]
    return rows


def build_skill_contracts() -> list[dict[str, Any]]:
    base_forbidden = FORBIDDEN_OUTPUTS + ["buy_sell_hold_recommendation", "target_price_as_advice"]
    skill_names = [
        "source_discovery_skill",
        "source_quality_scoring_skill",
        "content_ingestion_skill",
        "primary_evidence_lookup_skill",
        "claim_extraction_skill",
        "evidence_binding_skill",
        "entity_resolution_skill",
        "valuation_range_research_skill",
        "catalyst_invalidation_tracking_skill",
        "risk_qa_skill",
        "decision_memo_drafting_skill",
        "alert_monitoring_skill",
    ]
    contracts = []
    for name in skill_names:
        contracts.append({
            "skill_id": name,
            "purpose": f"Engineering contract for Finbot {name.replace('_', ' ')}; not installed as a native/global skill.",
            "input_schema": {
                "type": "object",
                "required": ["run_id", "case_or_source_id", "allowed_sources", "evidence_policy"],
                "properties": {
                    "run_id": {"type": "string"},
                    "case_or_source_id": {"type": "string"},
                    "allowed_sources": {"type": "array", "items": {"type": "string"}},
                    "evidence_policy": {"enum": ["primary_required", "hypothesis_only", "local_fixture_only"]},
                },
            },
            "output_schema": {
                "type": "object",
                "required": ["status", "evidence_ids", "next_action"],
                "properties": {
                    "status": {"enum": ["pass", "blocked", "candidate_to_enable", "needs_human_review"]},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "next_action": {"type": "string"},
                },
            },
            "required_evidence": ["source_id", "authority_level", "local_path_or_url", "sha256_or_stable_id", "available_at"],
            "validator": "tools/validate_finbot_capability_platform.py",
            "forbidden_actions": base_forbidden,
            "example_fixture": f"fixtures/capability_platform/{name}.fixture.json",
        })
    return contracts


def build_contract_files(matrix: list[dict[str, Any]], skills: list[dict[str, Any]]) -> None:
    contracts = REPO / "contracts"
    schemas = {
        "finbot_capability_platform_v1.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Finbot Capability Platform v1 Package",
            "type": "object",
            "required": ["status", "data_sources", "skill_contracts", "forbidden_outputs"],
            "properties": {
                "status": {"const": PASS_STATUS},
                "data_sources": {"type": "array"},
                "skill_contracts": {"type": "array"},
                "forbidden_outputs": {"type": "array", "items": {"type": "string"}},
            },
        },
        "finbot_data_source_readiness_v1.json": {"schema": "finbot.data_source_readiness.v1", "generated_at": NOW, "sources": matrix},
        "finbot_agent_skill_contracts_v1.json": {"schema": "finbot.agent_skill_contracts.v1", "generated_at": NOW, "skills": skills},
        "finbot_valuation_range_contract_v1.json": {
            "schema": "finbot.valuation_range_contract.v1",
            "required_fields": ["range_type", "method", "assumptions", "bear", "base", "bull", "evidence_ids", "invalidation", "no_advice_label"],
            "range_type": "research_estimate_range",
            "forbidden_fields": ["target_price", "recommendation", "buy_sell_hold", "position_size"],
        },
        "finbot_alert_contract_v1.json": {
            "schema": "finbot.alert_contract.v1",
            "allowed_alert_scope": "human_review_alert",
            "forbidden_alert_types": ["trade_signal", "buy_signal", "sell_signal", "production_watchlist"],
            "required_fields": ["alert_id", "case_id", "alert_scope", "alert_type", "trigger_reason", "evidence_ids", "human_review_question"],
        },
        "finbot_decision_memo_contract_v1.json": {
            "schema": "finbot.decision_memo_contract.v1",
            "allowed_decision_status": ["continue_research", "park", "reject", "needs_user_review"],
            "forbidden_status": ["buy", "sell", "hold", "add", "trim"],
            "required_fields": ["case_id", "thesis", "source_alpha_rationale", "primary_evidence", "counter_evidence", "open_questions", "decision_status"],
        },
    }
    for filename, payload in schemas.items():
        write_json(contracts / filename, payload)


def build_fixtures(skills: list[dict[str, Any]]) -> None:
    fixture_root = REPO / "fixtures/capability_platform"
    fixture_root.mkdir(parents=True, exist_ok=True)
    price_path = fixture_root / "local_price_context_fixture.csv"
    with price_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "date", "close", "currency", "fixture_only"])
        writer.writeheader()
        for ticker, close in [("YELP", 39.25), ("NKE", 90.1), ("TXN", 178.4), ("MU", 126.8)]:
            writer.writerow({"ticker": ticker, "date": "2026-05-08", "close": close, "currency": "USD", "fixture_only": "true"})
    for skill in skills:
        write_json(fixture_root / f"{skill['skill_id']}.fixture.json", {
            "run_id": "fixture-capability-platform-v1",
            "case_or_source_id": "alpha-yelp-20260509",
            "allowed_sources": ["sec_companyfacts", "local_docs"],
            "evidence_policy": "primary_required",
            "expected_output_status": "pass",
        })
    negative = fixture_root / "negative"
    write_json(negative / "endpoint_only_false_readiness.json", {
        "fixture_id": "endpoint_only_false_readiness",
        "expected_error": "ENDPOINT_ONLY_NOT_WORKFLOW_VERIFIED",
        "sources": [{"name": "Alpaca watch-only", "status": "workflow_verified", "proof_level": "endpoint_alive_only"}],
    })
    write_json(negative / "guarded_connector_fake_enabled.json", {
        "fixture_id": "guarded_connector_fake_enabled",
        "expected_error": "GUARDED_CONNECTOR_FALSE_READY",
        "sources": [{"name": "Daloopa", "status": "workflow_verified", "proof_level": "workflow_verified", "workflow_proof_id": ""}],
    })
    write_json(negative / "advice_output.json", {
        "fixture_id": "advice_output",
        "expected_error": "FORBIDDEN_ADVICE_OUTPUT",
        "decision_memo": {"case_id": "alpha-yelp-20260509", "decision_status": "buy", "recommendation": "buy"},
    })
    write_json(negative / "target_price_as_advice.json", {
        "fixture_id": "target_price_as_advice",
        "expected_error": "TARGET_PRICE_AS_ADVICE",
        "valuation": {"case_id": "alpha-yelp-20260509", "target_price": 55, "recommendation": "target price"},
    })
    write_json(negative / "production_watchlist.json", {
        "fixture_id": "production_watchlist",
        "expected_error": "PRODUCTION_WATCHLIST_FORBIDDEN",
        "alert": {"case_id": "alpha-yelp-20260509", "alert_scope": "production_watchlist", "alert_type": "buy_signal"},
    })
    write_json(negative / "broker_action.json", {
        "fixture_id": "broker_action",
        "expected_error": "BROKER_ACTION_FORBIDDEN",
        "decision_memo": {"case_id": "alpha-yelp-20260509", "decision_status": "needs_user_review", "broker_action": "submit_order"},
    })


def build_docs(matrix: list[dict[str, Any]], skills: list[dict[str, Any]]) -> None:
    DOC_ROOT.mkdir(parents=True, exist_ok=True)
    alpha_validator = read_json(RESEARCH_ROOT / "79_alpha_final_validator_result.json")
    alpha_cases = load_alpha_cases()
    matrix_json = {"schema": "finbot_engineering.data_source_readiness_matrix.v1", "generated_at": NOW, "sources": matrix}
    write_json(DOC_ROOT / "02_data_source_readiness_matrix.json", matrix_json)
    write_text(DOC_ROOT / "02_data_source_readiness_matrix.md",
        "# 02 Data Source Readiness Matrix\n\n"
        f"Generated: `{NOW}`\n\n"
        + table(["Source", "Category", "Status", "Proof", "Allowed", "Disallowed"], [
            [r["name"], r["category"], r["status"], r["proof_level"], r["allowed_downstream_use"], r["disallowed_downstream_use"]]
            for r in matrix
        ]) + "\n")
    write_text(DOC_ROOT / "00_execution_contract.md",
        "# 00 Execution Contract\n\n"
        f"Generated: `{NOW}`\n\n"
        "Objective: promote `paperclip_finbot_engineering_company` from `dry_run_only` harness to governed `capability_lab_v1` for Finbot Research agents.\n\n"
        "Allowed write scope: this evidence package and `paperclip_finbot_engineering_company/`.\n\n"
        "Forbidden: trading, broker/API order action, investment advice, production watchlist, trade signal, position sizing, native MCP/skill/runtime config mutation, provider quarantine bypass.\n\n"
        f"Required final status: `{PASS_STATUS}` in `14_final_validation.json`.\n")
    write_text(DOC_ROOT / "01_current_state_audit.md",
        "# 01 Current State Audit\n\n"
        f"Generated: `{NOW}`\n\n"
        "- Finbot Research alpha package: `79_alpha_final_validator_result.json` status `" + alpha_validator.get("status", "missing") + "`.\n"
        "- Alpha cases available for prototypes: `" + ", ".join(case["ticker"] for case in alpha_cases) + "`.\n"
        "- Engineering repo prior state: `dry_run_only`; this package updates it to `capability_lab_v1` while preserving no-production-mutation boundaries.\n"
        "- Existing candidate connector issues PAPA-44..49 remain blocked/candidate unless separately workflow-verified.\n"
        "- Native MCP/skill/runtime configs were not modified.\n")
    write_text(DOC_ROOT / "03_governed_connector_smoke_protocol.md",
        "# 03 Governed Connector Smoke Protocol\n\n"
        "Each connector smoke must record read-only scope, secret boundary, command/tool, result summary, artifact path, rollback/disable note, allowed downstream use, and disallowed use.\n\n"
        "Workflow verification requires a complete read-only path from request to artifact to validator. Endpoint reachability alone is `endpoint_alive_only`, not `workflow_verified`.\n\n"
        "Guarded connectors Readwise, Zotero, Alpaca, Daloopa, Quartr and Binance remain `candidate_to_enable` unless a current-lane read-only smoke is approved by Governance.\n\n"
        "Smoke runner: `python3 tools/finbot_capability_smoke_runner.py --docs-root " + str(DOC_ROOT) + "`.\n")
    write_text(DOC_ROOT / "04_skill_contracts_for_finbot_agents.md",
        "# 04 Skill Contracts For Finbot Agents\n\n"
        "These are engineering contracts only, not installed native/global skills.\n\n"
        + table(["Skill", "Purpose", "Validator", "Example Fixture"], [
            [s["skill_id"], s["purpose"], s["validator"], s["example_fixture"]] for s in skills
        ]) + "\n")
    write_text(DOC_ROOT / "05_schema_extension_design.md",
        "# 05 Schema Extension Design\n\n"
        "## Ledgers\n\n"
        "- `ValuationRangeLedger`: `range_type=research_estimate_range`, method, input data, date, assumptions, bull/base/bear ranges, confidence, invalidation, evidence ids, no-advice label.\n"
        "- `AlertLedger`: human-review alerts only; no production watchlist or trade signal.\n"
        "- `DecisionMemoLedger`: statuses limited to continue_research, park, reject, needs_user_review.\n"
        "- `CatalystLedger`: catalyst type, authority source, expected evidence, deadline, stale policy.\n"
        "- `InvalidationLedger`: thesis, invalidation condition, evidence requirement, review cadence.\n"
        "- `SourceRefreshLedger`: source, last_seen, next_refresh_due, proof level, blocked reason.\n"
        "- `DataSourceReadinessLedger`: status taxonomy, workflow proof id, governance follow-up.\n\n"
        "TradingAgents and Fincept remain method/UI references. Authority sits in evidence, data contracts, validators and Governance gates.\n")
    write_text(DOC_ROOT / "06_validator_design.md",
        "# 06 Validator Design\n\n"
        "Hard validator path: `paperclip_finbot_engineering_company/tools/validate_finbot_capability_platform.py`.\n\n"
        "It fails closed on: false readiness, endpoint-only counted as workflow verification, guarded connector fake enablement, advice/trading outputs, target-price-as-advice, production watchlist, broker action, missing valuation evidence/invalidation, alert trade signals, buy/sell/hold decision memos, and missing live succeeded-run readback.\n\n"
        "Negative fixtures live under `paperclip_finbot_engineering_company/fixtures/capability_platform/negative/`.\n")
    write_text(DOC_ROOT / "07_runner_design.md",
        "# 07 Runner Design\n\n"
        "Runner sequence:\n\n"
        "1. `finbot_capability_smoke_runner.py` verifies SEC/local docs/local HTML extraction/local price fixture and records blocked guarded connectors.\n"
        "2. `finbot_valuation_range_prototype.py` emits research-estimate ranges for selected alpha cases.\n"
        "3. `finbot_alert_prototype.py` emits human-review alerts for selected alpha cases.\n"
        "4. `finbot_decision_memo_prototype.py` emits bounded decision memos.\n"
        "5. `finbot_capability_live_issue_runner.py` creates/updates governed live issue evidence and accepts only succeeded-run-bound comments.\n"
        "6. `validate_finbot_capability_platform.py` runs hard validation and negative fixtures.\n")
    write_text(DOC_ROOT / "11_engineering_to_research_handoff.md",
        "# 11 Engineering To Research Handoff\n\n"
        "Usable by Finbot Research after Governance gate:\n\n"
        "- Data source readiness matrix and smoke results.\n"
        "- 12 agent skill contracts as engineering contracts, not global skills.\n"
        "- Schema extensions for valuation range, alerts, decision memo, catalyst, invalidation, source refresh and data readiness.\n"
        "- Prototype outputs for research-estimate ranges, human-review alerts and bounded decision memos.\n\n"
        "Not usable as investment readiness: no target price, no advice, no broker action, no production watchlist and no trade signal.\n")
    write_text(DOC_ROOT / "12_governance_approval_packet.md",
        "# 12 Governance Approval Packet\n\n"
        "Governance decisions requested:\n\n"
        "- Accept `capability_lab_v1` scope while preserving no trading/no broker/no advice/no production watchlist/no native config mutation.\n"
        "- Keep Readwise/Zotero/Alpaca/Daloopa/Quartr/Binance as candidate/blocked unless current-lane workflow verification is separately approved.\n"
        "- Keep MiniMax/DeepSeek/Tavily/Brave quarantined/no-production-use.\n"
        "- Approve Finbot Research to consume only the validated contract outputs and prototype artifacts as research-only capability inputs.\n\n"
        "Blocked/candidate follow-ups include: PAPA-44 Readwise, PAPA-45 Zotero, PAPA-46 Alpaca watch-only, PAPA-47 Daloopa, PAPA-48 Quartr, PAPA-49 Binance risk context, GOV-FINBOT-CAP-IR, GOV-FINBOT-CAP-OPENBB, GOV-FINBOT-CAP-CNINFO, GOV-FINBOT-CAP-SSE, GOV-FINBOT-CAP-SZSE, GOV-FINBOT-CAP-BSE, GOV-FINBOT-CAP-AKSHARE, GOV-FINBOT-CAP-TUSHARE, GOV-FINBOT-CAP-BAOSTOCK.\n")
    write_json(DOC_ROOT / "13_live_paperclip_readback.json", {
        "schema": "finbot_engineering.live_readback.v1",
        "generated_at": NOW,
        "status": "PENDING_LIVE_READBACK",
        "required_status": PASS_STATUS,
        "issues": [],
    })
    write_json(DOC_ROOT / "14_final_validation.json", {
        "schema": "finbot_engineering.final_validation.v1",
        "generated_at": NOW,
        "status": "PENDING_LIVE_READBACK",
        "complete_allowed": False,
    })
    write_text(DOC_ROOT / "15_closeout.md",
        "# 15 Closeout\n\nStatus: pending live readback and final validator.\n")


def update_repo_state_docs() -> None:
    readme = REPO / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = text.replace("Current state: `dry_run_only`.", "Current state: `capability_lab_v1` with dry-run production boundaries still enforced.")
    if "## Capability Lab v1" not in text:
        text += (
            "\n## Capability Lab v1\n\n"
            "This repo may now build and validate read-only Finbot capability contracts, fixture-backed tools, schemas, validators, and governed handoff packets. "
            "It still must not perform broker actions, trading, investment advice, production watchlist jobs, native MCP/skill/runtime config mutation, service registration, or writes outside its approved scope.\n"
        )
    readme.write_text(text, encoding="utf-8")
    runlog = REPO / "RUNLOG.md"
    runlog_text = runlog.read_text(encoding="utf-8")
    if "## 2026-05-09 Capability Lab v1" not in runlog_text:
        runlog_text += (
            "\n## 2026-05-09 Capability Lab v1\n\n"
            "- Promoted engineering scope from pure `dry_run_only` harness to governed `capability_lab_v1`.\n"
            "- Added read-only data source readiness contracts, agent skill contracts, schema extensions, prototype runners and hard validator.\n"
            "- Production mutation boundaries remain in force: no trading, broker action, investment advice, production watchlist, trade signal, position sizing, native config mutation, or quarantined provider use.\n"
        )
    runlog.write_text(runlog_text, encoding="utf-8")


def main() -> int:
    matrix = build_readiness_matrix()
    skills = build_skill_contracts()
    build_contract_files(matrix, skills)
    build_fixtures(skills)
    build_docs(matrix, skills)
    update_repo_state_docs()
    print(json.dumps({"status": "capability_platform_base_written", "docs_root": str(DOC_ROOT), "sources": len(matrix), "skills": len(skills)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
