from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FORBIDDEN_FINBOT_TERMS = [
    "buy recommendation",
    "sell recommendation",
    "target price recommendation",
    "trade signal",
    "broker action",
    "automatic trading",
    "production watchlist",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def exists(root: Path, rel: str, errors: list[dict[str, Any]]) -> Path:
    path = root / rel
    if not path.exists():
        errors.append({"code": "missing_required_file", "path": str(path)})
    return path


def write_result(root: Path, schema: str, errors: list[dict[str, Any]]) -> int:
    result = {"schema": schema, "status": "pass" if not errors else "fail", "errors": errors}
    out = root / "validator_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def validate_phase0(root: Path) -> int:
    errors: list[dict[str, Any]] = []
    role_map_path = exists(root, "company_role_map.json", errors)
    exists(root, "current_truth.md", errors)
    exists(root, "blocker_board.md", errors)
    if role_map_path.exists():
        role_map = load_json(role_map_path)
        gov = role_map.get("governance_capability_company", {})
        finbot = role_map.get("finbot_investment_research", {})
        owns = set(gov.get("owns", []))
        if "runtime_readiness" not in owns:
            errors.append({"code": "governance_missing_runtime_readiness"})
        if "skill_mcp_governance" not in owns:
            errors.append({"code": "governance_missing_skill_mcp_governance"})
        finbot_owns = " ".join(finbot.get("owns", [])).lower()
        for term in ["advice", "trading", "broker", "watchlist"]:
            if term in finbot_owns:
                errors.append({"code": "finbot_has_forbidden_ownership", "term": term})
        learning = role_map.get("learning_research_company", {})
        if "local_llm_research" not in learning.get("owns", []):
            errors.append({"code": "learning_missing_local_llm_research"})
    text = "".join(p.read_text(encoding="utf-8") for p in root.glob("*.md")).lower()
    if "local llm remains research-only" not in text and "local llm: research-only" not in text:
        errors.append({"code": "local_llm_research_only_boundary_missing"})
    for connector in ["readwise", "zotero", "alpaca", "daloopa", "quartr", "binance"]:
        if f"{connector}: verified_workflow" in text:
            errors.append({"code": "candidate_connector_marked_verified", "connector": connector})
    return write_result(root, "paperclip.long_range.phase0.validator.v1", errors)


def validate_phase1(root: Path) -> int:
    errors: list[dict[str, Any]] = []
    matrix_path = exists(root, "company_owned_evidence_matrix.json", errors)
    exists(root, "task_contracts.json", errors)
    exists(root, "live_issue_readback.json", errors)
    exists(root, "closeout.md", errors)
    required_companies = {
        "Planning Work Assistant",
        "Finbot Investment Research",
        "Paperclip Governance Company",
        "Finbot Engineering Capability Lab",
    }
    if matrix_path.exists():
        data = load_json(matrix_path)
        rows = data.get("rows", data if isinstance(data, list) else [])
        seen = {row.get("company") for row in rows}
        for company in required_companies - seen:
            errors.append({"code": "missing_company_owned_row", "company": company})
        for row in rows:
            for key in [
                "issue_id",
                "company",
                "agent",
                "status",
                "succeeded_run_id",
                "agent_authored_comment_id",
                "artifact_path",
                "validator_path",
                "memory_delta_or_no_write",
                "closeout_path",
            ]:
                if not row.get(key):
                    errors.append({"code": "matrix_row_missing_field", "issue_id": row.get("issue_id"), "field": key})
            if row.get("controller_authored_domain_output") is not False:
                errors.append({"code": "controller_authored_domain_output_not_false", "issue_id": row.get("issue_id")})
            for path_key in ["artifact_path", "validator_path", "closeout_path"]:
                path = row.get(path_key)
                if path and path.startswith("/vol1/") and not Path(path).exists():
                    errors.append({"code": "matrix_path_missing", "issue_id": row.get("issue_id"), "field": path_key, "path": path})
    return write_result(root, "paperclip.long_range.phase1.validator.v1", errors)


def validate_phase2(root: Path) -> int:
    errors: list[dict[str, Any]] = []
    case_path = exists(root, "case_deep_dive_register.json", errors)
    exists(root, "source_registry.json", errors)
    exists(root, "risk_reversal_ledger.jsonl", errors)
    exists(root, "human_review_queue.json", errors)
    exists(root, "closeout.md", errors)
    if case_path.exists():
        data = load_json(case_path)
        cases = data.get("cases", data if isinstance(data, list) else [])
        if len(cases) < 3:
            errors.append({"code": "too_few_deep_dive_cases", "count": len(cases)})
        for case in cases:
            cid = case.get("case_id")
            if len(case.get("primary_evidence", [])) < 3:
                errors.append({"code": "case_missing_primary_evidence", "case_id": cid})
            if not (case.get("why_it_may_fail") or case.get("risk_reversal_or_kill_condition")):
                errors.append({"code": "case_missing_contradiction_or_risk", "case_id": cid})
            range_text = str(case.get("research_estimate_range_non_advice", "")).lower()
            if "non" not in range_text or "advice" not in range_text:
                errors.append({"code": "case_missing_non_advice_range", "case_id": cid})
            question = str(case.get("human_review_question", "")).lower()
            if not question or any(term in question for term in ["buy", "sell", "hold"]):
                errors.append({"code": "case_missing_safe_human_review_question", "case_id": cid})
            text = json.dumps(case, ensure_ascii=False).lower()
            for term in FORBIDDEN_FINBOT_TERMS:
                if term in text:
                    errors.append({"code": "case_contains_forbidden_term", "case_id": cid, "term": term})
    return write_result(root, "paperclip.long_range.phase2.validator.v1", errors)


def validate_phase3(root: Path) -> int:
    errors: list[dict[str, Any]] = []
    intake_path = exists(root, "intake_register.jsonl", errors)
    decision_path = exists(root, "decision_queue.json", errors)
    followup_path = exists(root, "agent_followup_queue.json", errors)
    memory_path = exists(root, "memory_delta_candidates.jsonl", errors)
    replay_path = exists(root, "fresh_agent_replay.md", errors)
    if intake_path.exists():
        rows = read_jsonl(intake_path)
        if len(rows) < 3:
            errors.append({"code": "too_few_intakes", "count": len(rows)})
        for row in rows:
            for key in ["user_decision_needed", "evidence_gap", "next_agent_action", "stop_condition", "candidate_memory_delta_id"]:
                if not row.get(key):
                    errors.append({"code": "intake_missing_field", "intake_id": row.get("intake_id"), "field": key})
    if decision_path.exists():
        decisions = load_json(decision_path).get("decisions", [])
        if len(decisions) < 3:
            errors.append({"code": "too_few_decisions", "count": len(decisions)})
    if followup_path.exists():
        followups = load_json(followup_path).get("followups", [])
        if len(followups) < 3:
            errors.append({"code": "too_few_followups", "count": len(followups)})
    if memory_path.exists() and len(read_jsonl(memory_path)) < 3:
        errors.append({"code": "too_few_memory_candidates"})
    if replay_path.exists():
        text = replay_path.read_text(encoding="utf-8").lower()
        if "without chat history" not in text:
            errors.append({"code": "fresh_agent_replay_missing_no_chat_history_marker"})
    return write_result(root, "paperclip.long_range.phase3.validator.v1", errors)


def validate_phase4(root: Path) -> int:
    errors: list[dict[str, Any]] = []
    registry_path = exists(root, "capability_registry.json", errors)
    decisions_path = exists(root, "enablement_decisions.jsonl", errors)
    regression_path = exists(root, "false_pass_regression_result.json", errors)
    exists(root, "runtime_fallback_preflight.md", errors)
    exists(root, "closeout.md", errors)
    allowed = {"verified_workflow", "candidate", "blocked", "quarantined", "research_only"}
    if registry_path.exists():
        caps = load_json(registry_path).get("capabilities", [])
        for cap in caps:
            status = cap.get("status")
            name = cap.get("name")
            if status not in allowed:
                errors.append({"code": "invalid_capability_status", "name": name, "status": status})
            proof = cap.get("proof_level", "")
            if status == "verified_workflow" and proof in {"endpoint_only", "fixture_only", "plugin_inventory_only", "tool_namespace_only"}:
                errors.append({"code": "weak_proof_marked_verified", "name": name, "proof_level": proof})
            if name in {"MiniMax", "DeepSeek", "Tavily", "Brave"} and status != "quarantined":
                errors.append({"code": "quarantined_provider_not_quarantined", "name": name, "status": status})
            if name == "HomePC Ollama" and status not in {"research_only", "candidate"}:
                errors.append({"code": "homepc_wrong_status", "status": status})
    if decisions_path.exists():
        for row in read_jsonl(decisions_path):
            if row.get("decision") == "enable_production" and row.get("governance_approval") is not True:
                errors.append({"code": "production_enablement_without_approval", "capability": row.get("capability")})
    if regression_path.exists():
        cases = load_json(regression_path).get("cases", [])
        required = {
            "endpoint_only_as_verified",
            "fixture_only_as_live",
            "controller_only_as_company_owned",
            "advice_disguised_as_memo",
            "target_price_as_advice",
            "production_watchlist_leakage",
            "local_model_production_route",
            "quarantined_provider_enablement",
        }
        seen = {case.get("case_id") for case in cases}
        for missing in required - seen:
            errors.append({"code": "missing_false_pass_case", "case_id": missing})
        for case in cases:
            if case.get("result") != "rejected":
                errors.append({"code": "false_pass_case_not_rejected", "case_id": case.get("case_id")})
    return write_result(root, "paperclip.long_range.phase4.validator.v1", errors)


def validate_phase5(root: Path) -> int:
    errors: list[dict[str, Any]] = []
    exists(root, "memory_layer_contract.md", errors)
    current_path = exists(root, "current_truth_ledger.jsonl", errors)
    authority_path = exists(root, "authority_ledger.jsonl", errors)
    exists(root, "verbatim_registry.jsonl", errors)
    replay_path = exists(root, "fresh_agent_blind_test.md", errors)
    if current_path.exists() and not read_jsonl(current_path):
        errors.append({"code": "current_truth_ledger_empty"})
    if authority_path.exists():
        for row in read_jsonl(authority_path):
            if not row.get("approved_by") or not row.get("evidence_path"):
                errors.append({"code": "authority_entry_missing_approval", "rule_id": row.get("rule_id")})
            if row.get("source_layer") in {"sandbox", "candidate"}:
                errors.append({"code": "candidate_promoted_to_authority", "rule_id": row.get("rule_id")})
    if replay_path.exists():
        text = replay_path.read_text(encoding="utf-8").lower()
        for marker in ["fresh-agent", "current truth", "without full chat"]:
            if marker not in text:
                errors.append({"code": "fresh_agent_blind_test_missing_marker", "marker": marker})
    return write_result(root, "paperclip.long_range.phase5.validator.v1", errors)


def validate_phase6(root: Path) -> int:
    errors: list[dict[str, Any]] = []
    exists(root, "research_agenda.md", errors)
    rows_path = exists(root, "local_llm_benchmark_v3_rows.jsonl", errors)
    scorer_path = exists(root, "local_llm_scorer_result.json", errors)
    exists(root, "memory_system_comparison.md", errors)
    decision_path = exists(root, "governance_decision.md", errors)
    allowed_decisions = {
        "research_only_continue",
        "candidate_low_risk_digest_only",
        "blocked_quality_or_privacy",
        "blocked_homepc_unreachable",
    }
    if rows_path.exists():
        rows = read_jsonl(rows_path)
        if rows and len(rows) < 16:
            errors.append({"code": "too_few_benchmark_rows", "count": len(rows)})
        for row in rows:
            for key in ["authority_memory_allowed", "production_route_allowed", "finbot_final_judgment_allowed", "planning_authority_allowed"]:
                if row.get(key) is not False:
                    errors.append({"code": "benchmark_row_boundary_not_false", "row_id": row.get("row_id"), "key": key})
    if scorer_path.exists():
        scorer = load_json(scorer_path)
        if scorer.get("status") not in {"pass", "blocked_homepc_unreachable"}:
            errors.append({"code": "invalid_scorer_status", "status": scorer.get("status")})
    if decision_path.exists():
        text = decision_path.read_text(encoding="utf-8")
        if not any(decision in text for decision in allowed_decisions):
            errors.append({"code": "missing_allowed_governance_decision"})
        for forbidden in ["production route allowed", "authority memory allowed", "final judgment allowed"]:
            if forbidden in text.lower():
                errors.append({"code": "forbidden_local_llm_promotion_text", "text": forbidden})
    return write_result(root, "paperclip.long_range.phase6.validator.v1", errors)
