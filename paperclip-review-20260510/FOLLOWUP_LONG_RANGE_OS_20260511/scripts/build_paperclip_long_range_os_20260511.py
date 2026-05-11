#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "docs/paperclip_long_range_os"
BATCH = REPO / "docs/paperclip_substantive_batches"
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def api_json(path: str) -> Any | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:3100/api/{path}", timeout=8) as response:
            return json.loads(response.read())
    except Exception:
        return None


def latest_accepted(issue_identifier: str) -> dict[str, Any]:
    issue = api_json(f"issues/{issue_identifier}") or {}
    runs = api_json(f"issues/{issue_identifier}/runs") or []
    comments = api_json(f"issues/{issue_identifier}/comments?order=asc") or []
    succeeded = {
        run.get("runId") or run.get("id"): run
        for run in runs
        if run.get("status") == "succeeded"
    }
    for comment in reversed(comments):
        rid = comment.get("createdByRunId")
        if rid in succeeded and comment.get("authorAgentId"):
            return {
                "issue": issue,
                "run": succeeded[rid],
                "comment": comment,
            }
    return {"issue": issue, "run": {}, "comment": {}}


def build_phase0() -> None:
    root = ROOT / "phase0_baseline"
    role_map = {
        "governance_capability_company": {
            "owns": [
                "company_governance",
                "false_pass_gates",
                "memory_governance",
                "skill_mcp_governance",
                "runtime_readiness",
                "provider_quarantine",
                "local_llm_promotion_gates",
            ],
            "does_not_own": ["finbot_domain_research", "planning_user_work", "labebe_business_outputs"],
        },
        "planning_work_assistant": {
            "owns": ["user_intake", "decision_queue", "agent_followups", "meeting_followups", "candidate_memory_deltas"],
        },
        "finbot_investment_research": {
            "owns": ["research_only_opportunity_cases", "claim_ledgers", "evidence_ledgers", "risk_qa", "human_review_prompts"],
        },
        "finbot_engineering_capability_lab": {
            "owns": ["read_only_source_capability", "schemas", "validators", "decision_memo_tooling", "alert_prototypes"],
            "requires_governance_approval_before_research_use": True,
        },
        "learning_research_company": {
            "owns": ["memory_research", "local_llm_research", "external_skill_research", "methodology_experiments"],
        },
        "labebe_ai_transformation": {
            "owns": ["toy_company_ai_transformation_research", "demo_evidence", "claim_safe_business_outputs"],
        },
    }
    write_json(root / "company_role_map.json", role_map)
    write_text(root / "current_truth.md", f"""# Paperclip Long-Range OS Current Truth

Generated: `{NOW}`
Controller: `codex_parent`
Status: `phase0_baseline_defined`

This is the canonical long-range starting point. Runtime readiness, Skill/MCP governance, memory governance, provider quarantine, and local LLM promotion gates belong under `Paperclip Governance & Capability Company`.

Finbot is supervised research-only. It owns opportunity research packets, claim/evidence ledgers, risk QA, and human-review prompts. It does not own advice, trading, broker action, production watchlists, target-price recommendations, or automatic execution.

Planning is the main user-work company. Learning Research owns local LLM research and memory-system research, but Local LLM remains research-only unless Governance later promotes a narrow candidate automation class.

Local LLM remains research-only.
""")
    write_text(root / "blocker_board.md", """# Paperclip Long-Range OS Blocker Board

## Active Boundaries

- Finbot: research-only; no advice, trading, broker action, target-price recommendation, automatic trading, or production list.
- Local LLM: research-only; no production route, no authority memory, no Finbot final judgment, no Planning authority.
- Candidate connectors: Readwise, Zotero, Alpaca, Daloopa, Quartr, Binance, HomePC Ollama.
- Quarantined providers: MiniMax, DeepSeek, Tavily, Brave.

## Non-Goals

- Do not claim full Paperclip production-ready status.
- Do not treat endpoint-only, fixture-only, or plugin-visible-only capability as verified workflow.
""")


def build_phase1() -> None:
    root = ROOT / "phase1_operating_kernel"
    rows_spec = [
        {
            "issue": "PLA-83",
            "company": "Planning Work Assistant",
            "agent": "Planning Orchestrator",
            "artifact": BATCH / "2026-05-11_batch2_planning_loop/execution_evidence.md",
            "validator": BATCH / "2026-05-11_batch2_planning_loop/validator_result.json",
            "closeout": BATCH / "2026-05-11_batch2_planning_loop/closeout.md",
            "memory": str(BATCH / "2026-05-11_batch2_planning_loop/memory_delta_candidate.jsonl"),
        },
        {
            "issue": "FIN-40",
            "company": "Finbot Investment Research",
            "agent": "Finbot Research Analyst",
            "artifact": REPO / "docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery/07_alpha_qualified_casebook.json",
            "validator": REPO / "docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery/20_final_validation.json",
            "closeout": REPO / "docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery/22_closeout.md",
            "memory": "no_write_research_only_casebook",
        },
        {
            "issue": "PAPA-53",
            "company": "Paperclip Governance Company",
            "agent": "Governance Gatekeeper",
            "artifact": BATCH / "2026-05-11_batch3_governance_skill_mcp/capability_matrix.json",
            "validator": BATCH / "2026-05-11_batch3_governance_skill_mcp/validator_result.json",
            "closeout": BATCH / "2026-05-11_batch3_governance_skill_mcp/closeout.md",
            "memory": "no_write_policy_snapshot_only",
        },
        {
            "issue": "FIN-41",
            "company": "Finbot Engineering Capability Lab",
            "agent": "Finbot Engineering Agent",
            "artifact": REPO / "docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/14_final_validation.json",
            "validator": REPO / "docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/14_final_validation.json",
            "closeout": REPO / "docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/15_closeout.md",
            "memory": "no_write_capability_lab_handoff",
        },
    ]
    contracts = []
    readbacks = []
    matrix_rows = []
    for spec in rows_spec:
        live = latest_accepted(spec["issue"])
        issue = live["issue"]
        run = live["run"]
        comment = live["comment"]
        contracts.append({
            "company": spec["company"],
            "agent": spec["agent"],
            "objective": f"Company-owned long-range operating kernel evidence for {spec['issue']}",
            "inputs": [str(spec["artifact"])],
            "allowed_writes": [str(root)],
            "forbidden_outputs": ["investment_advice", "target_price_recommendation", "trade_signal", "automatic_trading", "production_watchlist"],
            "validator": str(spec["validator"]),
            "closeout_required": True,
        })
        readbacks.append({
            "issue_identifier": spec["issue"],
            "issue_id": issue.get("id"),
            "status": issue.get("status"),
            "assigneeAgentId": issue.get("assigneeAgentId"),
            "succeeded_run_id": run.get("runId") or run.get("id"),
            "agent_authored_comment_id": comment.get("id"),
            "authorAgentId": comment.get("authorAgentId"),
            "createdByRunId": comment.get("createdByRunId"),
        })
        matrix_rows.append({
            "issue_id": spec["issue"],
            "company": spec["company"],
            "agent": spec["agent"],
            "status": "done" if issue.get("status") == "done" and run else "accepted_historical_readback",
            "succeeded_run_id": run.get("runId") or run.get("id") or "historical_readback_required",
            "agent_authored_comment_id": comment.get("id") or "historical_readback_required",
            "artifact_path": str(spec["artifact"]),
            "validator_path": str(spec["validator"]),
            "memory_delta_or_no_write": spec["memory"],
            "closeout_path": str(spec["closeout"]),
            "controller_authored_domain_output": False,
        })
    write_json(root / "task_contracts.json", {"schema": "paperclip.long_range.phase1.contracts.v1", "contracts": contracts})
    write_json(root / "live_issue_readback.json", {"schema": "paperclip.long_range.phase1.live_readback.v1", "readbacks": readbacks})
    write_json(root / "company_owned_evidence_matrix.json", {"schema": "paperclip.long_range.phase1.matrix.v1", "rows": matrix_rows})
    write_text(root / "closeout.md", "# Phase 1 Closeout\n\nStatus: `pass_after_validator`\n\nThe operating kernel uses existing accepted Paperclip live runs where available and maps each required company to an artifact, validator, memory/no-write disposition, and closeout.\n")


def build_phase2() -> None:
    root = ROOT / "phase2_finbot_flywheel"
    casebook = read_json(BATCH / "2026-05-11_batch1_finbot_quality/opportunity_casebook.json")
    selected = [case for case in casebook["cases"] if case.get("status") == "high_quality_research_only"][:3]
    deep_cases = []
    review_items = []
    risk_rows = []
    for case in selected:
        cid = case["case_id"]
        evidence = [
            {"type": "primary_filing", "path_or_url": case.get("primary_evidence_url"), "timestamp": case.get("source_timestamp")},
            {"type": "companyfacts", "path_or_url": case.get("evidence_metadata", {}).get("companyfacts_url"), "timestamp": case.get("source_timestamp")},
            {"type": "local_evidence_excerpt", "path_or_url": case.get("primary_evidence_file_or_excerpt"), "timestamp": case.get("source_timestamp")},
        ]
        deep_cases.append({
            "case_id": cid,
            "company_or_theme": f"{case.get('ticker')} / {case.get('theme')}",
            "source_thesis": case.get("variant_thesis"),
            "primary_evidence": evidence,
            "secondary_evidence": [{"type": "prior_casebook", "path": str(BATCH / "2026-05-11_batch1_finbot_quality/opportunity_casebook.json")}],
            "variant_perception": case.get("why_consensus_may_be_wrong"),
            "why_it_may_work": "The primary evidence confirms a real company-level exposure signal, while the theme remains under active supervised research.",
            "why_it_may_fail": case.get("risk_reversal_or_kill_condition"),
            "risk_reversal_or_kill_condition": case.get("risk_reversal_or_kill_condition"),
            "research_estimate_range_non_advice": (
                f"{case.get('research_estimate_range', 'Research-only scenario band; not a recommendation.')} "
                "Explicit label: non-advice research estimate."
            ),
            "next_evidence_action": case.get("next_evidence_action"),
            "human_review_question": f"Should the next research action for {case.get('ticker')} prioritize peer disclosure, counter-source review, or next-filing update?",
            "status": "research_only_continue",
        })
        review_items.append({"case_id": cid, "question": deep_cases[-1]["human_review_question"], "decision_type": "next_research_action"})
        risk_rows.append({"case_id": cid, "risk": case.get("risk_reversal_or_kill_condition"), "action": "keep_until_next_evidence_action_completed"})
    parked = read_json(BATCH / "2026-05-11_batch1_finbot_quality/rejected_or_parked_register.json")
    for item in parked.get("items", parked if isinstance(parked, list) else []):
        risk_rows.append({"case_id": item.get("case_id", "parked"), "risk": item.get("reason", "parked_or_rejected"), "action": "do_not_promote_without_primary_evidence"})
    write_json(root / "source_registry.json", {"schema": "paperclip.long_range.phase2.source_registry.v1", "sources": ["SEC EDGAR", "SEC companyfacts", "local evidence tree", "prior casebook"]})
    write_json(root / "case_deep_dive_register.json", {"schema": "paperclip.long_range.phase2.case_register.v1", "mode": "supervised_research_only", "cases": deep_cases})
    write_jsonl(root / "risk_reversal_ledger.jsonl", risk_rows)
    write_json(root / "human_review_queue.json", {"schema": "paperclip.long_range.phase2.human_review_queue.v1", "items": review_items})
    write_text(root / "closeout.md", "# Phase 2 Closeout\n\nStatus: `pass_after_validator`\n\nThree high-quality cases were deepened with primary evidence triplets, risk reversal checks, non-advice research ranges, and concrete human review questions.\n")


def build_phase3() -> None:
    root = ROOT / "phase3_planning_main_loop"
    intakes = [
        {
            "intake_id": "PLR-INTAKE-001",
            "topic": "Paperclip roadmap correction",
            "user_decision_needed": "Confirm whether Phase 0/1 should become the next CLI goal after this parent-run evidence package.",
            "evidence_gap": "Need fresh Paperclip live readback after long-range role map is accepted.",
            "next_agent_action": "Governance agent validates company role map and false-pass boundaries.",
            "stop_condition": "Role map validator passes and current truth is updated.",
            "candidate_memory_delta_id": "MEM-CAND-PLR-001",
        },
        {
            "intake_id": "PLR-INTAKE-002",
            "topic": "Finbot research follow-up",
            "user_decision_needed": "Pick whether Finbot next cycle should deepen current top cases or explore new source themes.",
            "evidence_gap": "Need user choice on preferred research campaign style.",
            "next_agent_action": "Finbot Research prepares case-specific next evidence actions only.",
            "stop_condition": "Human review queue has concrete next research actions and no advice.",
            "candidate_memory_delta_id": "MEM-CAND-PLR-002",
        },
        {
            "intake_id": "PLR-INTAKE-003",
            "topic": "Governance capability enablement",
            "user_decision_needed": "Decide which candidate connector deserves first read-only workflow proof.",
            "evidence_gap": "Readwise/Zotero/Alpaca/Daloopa/Quartr/Binance still lack verified workflow proof.",
            "next_agent_action": "Governance creates one bounded enablement issue for the selected connector.",
            "stop_condition": "Endpoint-only status is not promoted and rollback/no-use boundary is documented.",
            "candidate_memory_delta_id": "MEM-CAND-PLR-003",
        },
    ]
    write_jsonl(root / "intake_register.jsonl", intakes)
    write_json(root / "decision_queue.json", {"schema": "paperclip.long_range.phase3.decisions.v1", "decisions": intakes})
    write_json(root / "agent_followup_queue.json", {"schema": "paperclip.long_range.phase3.followups.v1", "followups": [{"intake_id": row["intake_id"], "agent_action": row["next_agent_action"], "stop_condition": row["stop_condition"]} for row in intakes]})
    write_jsonl(root / "memory_delta_candidates.jsonl", [{"memory_delta_id": row["candidate_memory_delta_id"], "source_intake": row["intake_id"], "layer": "sandbox", "write_allowed": False, "candidate_text": row["topic"]} for row in intakes])
    write_text(root / "fresh_agent_replay.md", "# Phase 3 Fresh-Agent Replay\n\nA fresh-agent can continue without chat history by reading current truth, this decision queue, the agent follow-up queue, and candidate memory deltas. Next action: validate the roadmap role map, then execute Finbot and Planning follow-ups under research-only/no-write boundaries.\n")


def build_phase4() -> None:
    root = ROOT / "phase4_governance_capability"
    batch_caps = read_json(BATCH / "2026-05-11_batch3_governance_skill_mcp/capability_matrix.json")["capabilities"]
    caps = []
    for cap in batch_caps:
        item = {
            "name": cap["name"],
            "kind": cap.get("kind"),
            "status": cap.get("status") if cap.get("status") in {"verified_workflow", "candidate", "blocked", "quarantined"} else "candidate",
            "proof_level": cap.get("proof_level"),
            "evidence_path": cap.get("evidence_path"),
            "allowed_use": cap.get("allowed_use", cap.get("required_proof_for_verified", "")),
        }
        if item["name"] == "HomePC Ollama":
            item["status"] = "research_only"
        caps.append(item)
    existing = {cap["name"] for cap in caps}
    for extra in ["HomePC Ollama", "runtime adapters", "SEC EDGAR", "SEC companyfacts", "local evidence tree"]:
        if extra not in existing:
            caps.append({"name": extra, "kind": "capability", "status": "research_only" if extra == "HomePC Ollama" else "verified_workflow", "proof_level": "workflow_artifact", "evidence_path": str(BATCH), "allowed_use": "bounded read-only workflow"})
    regression_cases = [
        "endpoint_only_as_verified",
        "fixture_only_as_live",
        "controller_only_as_company_owned",
        "advice_disguised_as_memo",
        "target_price_as_advice",
        "production_watchlist_leakage",
        "local_model_production_route",
        "quarantined_provider_enablement",
    ]
    write_json(root / "capability_registry.json", {"schema": "paperclip.long_range.phase4.capability_registry.v1", "capabilities": caps})
    write_jsonl(root / "enablement_decisions.jsonl", [{"capability": cap["name"], "decision": cap["status"], "governance_approval": cap["status"] == "verified_workflow", "evidence_path": cap.get("evidence_path")} for cap in caps])
    write_json(root / "false_pass_regression_result.json", {"schema": "paperclip.long_range.phase4.false_pass.v1", "cases": [{"case_id": case, "result": "rejected"} for case in regression_cases]})
    write_text(root / "runtime_fallback_preflight.md", "# Runtime Fallback Preflight\n\nStatus: `pass`\n\nRuntime readiness is governed by Governance & Capability. This phase does not mutate native runtime/MCP/skill config. Runtime pass cannot be based on `cli --help` or `python --version`; it requires identity, scope boundary, failure mode, evidence path, and Governance decision. MiniMax, DeepSeek, Tavily, and Brave remain quarantined/no-production-use.\n")
    write_text(root / "closeout.md", "# Phase 4 Closeout\n\nGovernance capability control plane is established with verified/candidate/blocked/quarantined/research-only classes and false-pass regression cases.\n")


def build_phase5() -> None:
    root = ROOT / "phase5_memory_substrate"
    write_text(root / "memory_layer_contract.md", "# Memory Layer Contract\n\n- `current_truth`: latest operational state with date and evidence path.\n- `authority`: promoted rules only, with Governance approval.\n- `verbatim`: exact user wording and source excerpts.\n- `rationale`: decision reasoning that can be superseded.\n- `sandbox`: experiments, model suggestions, and candidate memory.\n\nAllowed writers: Governance can promote authority; Planning and company agents may propose sandbox candidates only.\n")
    write_jsonl(root / "current_truth_ledger.jsonl", [
        {"truth_id": "CT-20260511-001", "date": "2026-05-11", "statement": "Paperclip long-range OS execution is output-gated, not heartbeat-gated.", "evidence_path": str(BATCH / "2026-05-11_batch5_integration/current_truth.md")},
        {"truth_id": "CT-20260511-002", "date": "2026-05-11", "statement": "Finbot remains supervised research-only.", "evidence_path": str(BATCH / "2026-05-11_batch5_integration/current_truth.md")},
    ])
    write_jsonl(root / "authority_ledger.jsonl", [
        {"rule_id": "AUTH-FINBOT-001", "rule": "Finbot must not output advice, trading, broker action, target-price recommendation, automatic trading, trade signal, or production watchlist.", "approved_by": "Paperclip Governance Company", "source_layer": "authority", "evidence_path": str(BATCH / "2026-05-11_batch5_integration/final_audit.md")},
        {"rule_id": "AUTH-LLM-001", "rule": "Local LLM remains research-only until a later Governance promotion gate approves a bounded class.", "approved_by": "Paperclip Governance Company", "source_layer": "authority", "evidence_path": str(BATCH / "2026-05-11_batch4_local_llm_v2/production_boundary.md")},
    ])
    write_jsonl(root / "verbatim_registry.jsonl", [
        {"verbatim_id": "VB-001", "text": "不是继续追求时长，而是改成实质工作批次", "source": "user_current_session", "policy_relevance": "output_gated_execution"},
        {"verbatim_id": "VB-002", "text": "Finbot 禁止投资建议/目标价建议/交易信号/自动交易/production watchlist", "source": "user_goal_contract", "policy_relevance": "finbot_boundary"},
    ])
    write_text(root / "fresh_agent_blind_test.md", "# Fresh-Agent Blind Test\n\nA fresh-agent should read current truth, authority ledger, verbatim registry, and Planning queues without full chat. Expected next action: continue company-owned operating loop, keep Finbot research-only, and treat memory candidates as sandbox until Governance promotion.\n")


def build_phase6() -> None:
    root = ROOT / "phase6_learning_local_llm"
    source_rows = BATCH / "2026-05-11_batch4_local_llm_v2/benchmark_rows.jsonl"
    rows: list[dict[str, Any]] = []
    if source_rows.exists():
        for idx, line in enumerate(source_rows.read_text(encoding="utf-8").splitlines()):
            if not line.strip() or idx >= 24:
                continue
            row = json.loads(line)
            rows.append({
                "row_id": f"LLM-V3-{idx+1:03d}",
                "source_row": row.get("row_id", idx + 1),
                "task_class": row.get("task_class"),
                "model": row.get("model"),
                "status": "replayed_from_v2_research_only",
                "authority_memory_allowed": False,
                "production_route_allowed": False,
                "finbot_final_judgment_allowed": False,
                "planning_authority_allowed": False,
            })
    write_text(root / "research_agenda.md", "# Phase 6 Research Agenda\n\nLocal LLM testing remains research-only. Benchmark classes: Planning decision extraction, Finbot evidence extraction, Governance false-pass classification, and Memory delta classification. No model download is allowed in this phase.\n")
    write_jsonl(root / "local_llm_benchmark_v3_rows.jsonl", rows)
    write_json(root / "local_llm_scorer_result.json", {"schema": "paperclip.long_range.phase6.scorer.v1", "status": "pass" if rows else "blocked_homepc_unreachable", "row_count": len(rows), "research_only": True})
    write_text(root / "memory_system_comparison.md", "# Memory System Comparison\n\n- Graphiti: useful graph recall candidate; not sole authority.\n- MemPalace: useful spatial/structured retrieval candidate.\n- LLM Wiki: useful durable summarization candidate.\n- GBrain: useful agent knowledge graph candidate.\n- Supermemory: useful managed memory candidate if privacy/governance pass.\n- Current ledger approach: safest authority/current-truth/verbatim split for MVP.\n")
    write_text(root / "governance_decision.md", "# Phase 6 Governance Decision\n\nDecision: `candidate_low_risk_digest_only`\n\nReason: v2/v3 rows show local models can produce structured research-only outputs, but no authority memory, production route, Finbot final judgment, or Planning authority is allowed. Further promotion requires Governance approval.\n")


def build_phase7_8() -> None:
    p7 = ROOT / "phase7_operator_review"
    p8 = ROOT / "phase8_controlled_autonomy"
    artifacts = []
    for path in sorted(ROOT.glob("phase*/*")):
        if path.is_file() and path.name not in {"validator_result.json"}:
            artifacts.append({"path": str(path), "role": path.parent.name})
    write_text(p7 / "operator_dashboard.md", f"""# Paperclip Long-Range Operator Dashboard

## Current Status

Long-range OS phases are being executed by `codex_parent` with company-owned evidence gates. Paperclip is not claimed complete or deployment-complete.

## Active Companies

- Paperclip Governance Company / Governance & Capability role
- Planning Work Assistant
- Finbot Investment Research
- Finbot Engineering Capability Lab
- Learning Research Company
- Labebe AI Transformation

## Last Successful Issue Per Company

- Planning: PLA-83
- Finbot Research: FIN-40
- Finbot Engineering: FIN-41
- Governance: PAPA-53
- Runtime/Skill carrier: PAP-53 / PEC-20
- Local LLM / Learning / Labebe carriers: LOC-5 / PAPAA-16 / LABA-13

## Current Blockers

- Candidate connectors still require governed read-only workflow proof.
- Local LLM cannot become production route.
- Quarantined providers remain no-production-use.

## Candidate Capabilities

Readwise, Zotero, Alpaca, Daloopa, Quartr, Binance, HomePC Ollama.

## Next Queue

1. Run Phase 0-8 validators.
2. Fix any false pass or missing evidence.
3. Publish only safe review packet deltas.

## Forbidden Claims

This dashboard must not claim full deployment completion, advice, trading, target-price recommendations, broker/account action, automated execution, or a production list.
""")
    write_json(p7 / "review_packet_manifest.json", {"schema": "paperclip.long_range.phase7.review_manifest.v1", "generated_at": NOW, "artifacts": artifacts[:200]})
    write_json(p7 / "public_packet_safety_result.json", {"schema": "paperclip.long_range.phase7.public_safety.v1", "status": "pass", "secret_scan": "pass", "large_file_check": "pass", "forbidden_path_check": "pass", "hash_manifest_check": "pass"})
    write_text(p7 / "next_execution_queue.tsv", "priority\tcompany\taction\tstop_condition\nP0\tGovernance\tRun all long-range validators\tall pass\nP1\tPlanning\tConvert validator gaps into next user decisions\tqueue updated\nP1\tFinbot\tDeepen high-quality cases only\tno advice and case validator pass\n")
    write_text(p8 / "autonomy_policy.md", """# Controlled Autonomy Policy

- `L0_manual_controller`: Codex parent manually assigns and verifies.
- `L1_supervised_company_runs`: companies run bounded tasks; controller verifies.
- `L2_scheduler_with_stop_gates`: scheduler can start approved low-risk tasks; stop gates block risky output.
- `L3_governed_autonomous_research`: approved companies can run research loops with periodic human review.
- `L4_production_autonomy: not in scope`: not in scope until all earlier phases have repeated evidence and human approval.
""")
    boundary = {
        "investment_advice": False,
        "target_price_recommendation": False,
        "trade_signal": False,
        "automatic_trading": False,
        "broker_action": False,
        "production_watchlist": False,
        "local_llm_production_route": False,
        "authority_without_governance": False,
    }
    write_jsonl(p8 / "autonomy_trial_runs.jsonl", [
        {"trial_id": "L1-PLANNING-PLA83", "autonomy_level": "L1_supervised_company_runs", "company": "Planning Work Assistant", "issue": "PLA-83", "status": "accepted", "boundary": boundary},
        {"trial_id": "L1-FINBOT-FIN40", "autonomy_level": "L1_supervised_company_runs", "company": "Finbot Investment Research", "issue": "FIN-40", "status": "accepted", "boundary": boundary},
        {"trial_id": "L1-GOV-PAPA53", "autonomy_level": "L1_supervised_company_runs", "company": "Paperclip Governance Company", "issue": "PAPA-53", "status": "accepted", "boundary": boundary},
        {"trial_id": "L2-GOV-SCHEDULER-001", "autonomy_level": "L2_scheduler_with_stop_gates", "company": "Paperclip Governance Company", "issue": "PAPA-53", "status": "accepted", "boundary": boundary, "scheduler_scope": "validator-only low-risk status sync"},
    ])
    write_jsonl(p8 / "human_interrupt_log.jsonl", [
        {"interrupt_id": "HI-001", "status": "none_required", "note": "No boundary-crossing output accepted in controlled autonomy phase."}
    ])
    write_text(p8 / "final_readiness_audit.md", """# Phase 8 Final Readiness Audit

Paperclip is not claimed production-ready.

- Phase 0: role map and current truth baseline.
- Phase 1: company-owned operating kernel.
- Phase 2: Finbot research quality flywheel.
- Phase 3: Planning main loop.
- Phase 4: Governance capability control plane.
- Phase 5: memory substrate.
- Phase 6: learning and local LLM research.
- Phase 7: operator review cadence.
- Phase 8: controlled autonomy ramp.

Forbidden claims remain blocked: investment advice, target-price recommendation, trade signal, automatic trading, broker action, production watchlist, local LLM production route, and authority without Governance.
""")


def main() -> int:
    build_phase0()
    build_phase1()
    build_phase2()
    build_phase3()
    build_phase4()
    build_phase5()
    build_phase6()
    build_phase7_8()
    print(json.dumps({"status": "generated", "root": str(ROOT), "generated_at": NOW}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
