# Paperclip Long-Range Operating System Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Paperclip from a collection of evidence packets and company names into a durable, company-owned operating system that can continuously intake work, assign company agents, produce useful outputs, validate evidence, update current truth, and improve capabilities without false completion.

**Architecture:** Paperclip should run as an output-gated company operating system, not as a time-based heartbeat loop. The controller sets contracts, routes work, and verifies evidence; companies and their agents own domain outputs. Governance owns policy, memory, Skill/MCP, runtime, local model promotion gates, and false-pass prevention; business companies own user-facing work.

**Tech Stack:** Paperclip live API and issue/run/readback records, `/vol1/1000/projects/toyresearch` repo artifacts, `paperclip_company_os`, `paperclip_finbot`, `paperclip_finbot_engineering_company`, Python validators, JSON/JSONL evidence ledgers, Markdown closeouts, public review repo `/tmp/ChatgptREST-review`, HomePC/Ollama research-only benchmark lane.

---

## 0. Current Baseline

Latest authoritative baseline:

- Current truth: `/vol1/1000/projects/toyresearch/docs/paperclip_substantive_batches/2026-05-11_batch5_integration/current_truth.md`
- Final audit: `/vol1/1000/projects/toyresearch/docs/paperclip_substantive_batches/2026-05-11_batch5_integration/final_audit.md`
- Execution matrix: `/vol1/1000/projects/toyresearch/docs/paperclip_substantive_batches/2026-05-11_batch5_integration/company_execution_matrix.json`
- Public follow-up packet: `/tmp/ChatgptREST-review/paperclip-review-20260510/FOLLOWUP_SUBSTANTIVE_BATCHES_20260511`
- Public review branch: `review-20260506-085232`
- Public review commit: `fbecf247a2354c10177d05c710665c40e0acc52a`

Current usable capabilities:

- Finbot has `24` reviewed supervised research-only cases and `12` high-quality research-only cases.
- Planning has a real intake-to-closeout queue with decisions, evidence gaps, agent follow-ups, and candidate-only memory.
- Governance/Skill-MCP has a capability matrix distinguishing `verified_workflow`, `candidate`, `blocked`, and `quarantined`.
- Local LLM Research has benchmark v2 with `60` rows, `60` strict JSON outputs, and a research-only production boundary.

Current boundaries:

- Finbot is not an investment adviser, trading system, target-price system, signal engine, broker integration, automatic trading system, or production watchlist.
- Local LLM remains research-only and cannot become Finbot final judgment, Planning authority, Governance authority, memory authority, or production runtime route.
- MiniMax, DeepSeek, Tavily, and Brave remain quarantined/no-production-use.
- Readwise, Zotero, Alpaca, Daloopa, Quartr, Binance, and HomePC Ollama are not enabled for production use unless a later Governance gate changes their status.
- Memory deltas are candidate-only unless Governance explicitly approves authority promotion.

## 1. Target End State

Paperclip reaches the intended target when all of the following are true:

1. **Company-Owned Execution:** Every important work item enters through `intake -> task contract -> issue -> assigned company/agent -> execution artifact -> validator -> memory_delta/no_write -> Paperclip readback -> closeout -> current truth`.
2. **Governance Works:** Governance can reject false passes, classify Skill/MCP/runtime/local model capabilities, approve or deny promotion, and keep stale blocker text from driving current decisions.
3. **Planning Becomes The Main Assistant:** Planning can repeatedly process the user's real work inputs, convert them into decision queues and agent work, and preserve reusable context without relying on long chat history.
4. **Finbot Produces Useful Research:** Finbot can continuously generate and deepen research-only opportunity packets with source provenance, evidence, contradiction checks, valuation-range research estimates, risk QA, and human review prompts. It still never gives investment advice.
5. **Finbot Engineering Raises Capability:** Finbot Engineering builds and validates read-only source adapters, schemas, validators, decision memo tooling, and alert prototypes before Finbot Research uses them.
6. **Memory Improves Outcomes:** Memory has a governed current-truth, authority, verbatim, rationale, and sandbox structure; fresh-agent replay proves that a new agent can use the memory substrate to produce better results.
7. **Local LLM Is Safely Explored:** HomePC/Ollama can be benchmarked for low-risk private automation classes, but only Governance can promote a class from research-only to candidate automation.
8. **Review Packets Are Honest:** Public review packets include enough evidence for external review without secrets, private session state, raw credentials, large caches, or unsupported production claims.

## 2. Organizational Model

### 2.1 Recommended Company Structure

| Company | Role | Keep / Merge Decision |
| --- | --- | --- |
| `Paperclip Governance & Capability Company` | Owns company governance, false-pass gates, memory governance, Skill/MCP governance, runtime readiness, provider quarantine, local model promotion gates. | Merge the old Controller/Runtime company responsibilities here as agents, not as a separate peer business company. |
| `Planning Work Assistant` | Main user-work company for frequent real inputs, strategy, HR, meeting/audio follow-up, and decision queues. | Keep and strengthen. |
| `Finbot Investment Research` | Produces supervised research-only opportunity cases, evidence ledgers, risk QA, and human-review prompts. | Keep as research company, not trading/advice company. |
| `Finbot Engineering Capability Lab` | Builds Finbot data-source, schema, validator, memo, alert, and source adapter capability. | Keep as engineering lab governed by Governance and consumed by Finbot Research. |
| `Learning Research Company` | Runs research agendas for memory systems, local model evaluation, external skill ecosystems, and methodology experiments. | Keep as horizontal research, not production owner. |
| `Labebe AI Transformation` | Toy/company transformation lane and business demo work. | Keep lower priority until core OS, Planning, Finbot, and Governance are stable. |

### 2.2 Runtime Is Not A Separate Business Company

Runtime should not be a standalone company competing with Governance or business companies. Runtime should be:

- an **agent/lane inside Governance & Capability** for readiness, fallback, provider quarantine, and preflight;
- a **code module/lab** when implementation work is required;
- a **policy-gated dependency** for other companies.

This avoids the earlier failure mode where runtime complexity became the main project and displaced the actual product goal.

## 3. Roadmap Overview

This roadmap uses output gates, not elapsed time. Time estimates are sequencing aids only.

| Phase | Goal | Completion Gate |
| --- | --- | --- |
| Phase 0 | Freeze current truth and org model. | One canonical current-truth file and one company role map pass validation. |
| Phase 1 | Build company-owned operating kernel v1. | At least Planning, Finbot, Governance, and Finbot Engineering run company-owned issues with readback. |
| Phase 2 | Upgrade Finbot from case quantity to research quality flywheel. | Finbot produces recurring high-quality research packets, rejected register, risk QA, and human review queue. |
| Phase 3 | Upgrade Planning into the user's primary work assistant. | Planning completes repeated real intakes and proves fresh-agent replay with memory candidate use. |
| Phase 4 | Make Governance/Skill-MCP/Runtime actually useful. | Governance can enable or block capabilities with workflow proof and false-pass regression. |
| Phase 5 | Build memory substrate v1. | Fresh-agent blind tests prove current truth and memory deltas improve handoff quality. |
| Phase 6 | Advance Local LLM Research safely. | Local model benchmark classes get scored and remain research-only unless Governance approves candidate automation. |
| Phase 7 | Produce operator dashboard and public review cadence. | A new operator or reviewer can inspect status, evidence, blockers, and next queue without reading chat history. |
| Phase 8 | Ramp controlled autonomy. | Paperclip runs repeated supervised cycles without controller-authored domain artifacts or false completion. |

## 4. Global Definition Of Done

Every phase and work item must produce:

- task contract;
- assigned company and agent;
- allowed read/write scope;
- runtime/capability boundary;
- evidence artifact path;
- validator or manual acceptance checklist;
- memory delta or no-write reason;
- Paperclip issue/run/comment/readback evidence when live execution is in scope;
- closeout;
- current truth and execution matrix update;
- focused commit.

Do not accept:

- package completeness as product completion;
- validator pass that does not cover the actual prompt;
- controller-authored domain artifacts as company-owned execution;
- elapsed time as proof of work;
- Pro/ChatGPT answer as approval;
- endpoint-only connector status as verified workflow;
- local model benchmark pass as production routing approval;
- Finbot research output as investment advice.

## 5. Phase 0: Canonical Baseline And Role Map

**Purpose:** Remove ambiguity before more work starts.

**Files:**

- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase0_baseline/current_truth.md`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase0_baseline/company_role_map.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase0_baseline/blocker_board.md`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase0_baseline/validator_result.json`
- Create: `/vol1/1000/projects/toyresearch/scripts/validate_paperclip_long_range_phase0_20260511.py`

**Steps:**

- [ ] Read `/vol1/1000/projects/toyresearch/docs/paperclip_substantive_batches/2026-05-11_batch5_integration/current_truth.md`.
- [ ] Read `/vol1/1000/projects/toyresearch/docs/paperclip_substantive_batches/2026-05-11_batch5_integration/company_execution_matrix.json`.
- [ ] Write `company_role_map.json` with exactly these top-level keys:

```json
{
  "governance_capability_company": {
    "owns": ["company_governance", "false_pass_gates", "memory_governance", "skill_mcp_governance", "runtime_readiness", "provider_quarantine", "local_llm_promotion_gates"],
    "does_not_own": ["finbot_domain_research", "planning_user_work", "labebe_business_outputs"]
  },
  "planning_work_assistant": {
    "owns": ["user_intake", "decision_queue", "agent_followups", "meeting_followups", "candidate_memory_deltas"]
  },
  "finbot_investment_research": {
    "owns": ["research_only_opportunity_cases", "claim_ledgers", "evidence_ledgers", "risk_qa", "human_review_prompts"]
  },
  "finbot_engineering_capability_lab": {
    "owns": ["read_only_source_capability", "schemas", "validators", "decision_memo_tooling", "alert_prototypes"],
    "requires_governance_approval_before_research_use": true
  },
  "learning_research_company": {
    "owns": ["memory_research", "local_llm_research", "external_skill_research", "methodology_experiments"]
  },
  "labebe_ai_transformation": {
    "owns": ["toy_company_ai_transformation_research", "demo_evidence", "claim_safe_business_outputs"]
  }
}
```

- [ ] Write `current_truth.md` that states this is the canonical long-range starting point.
- [ ] Write `blocker_board.md` with active blockers, quarantines, candidate-only capabilities, and explicit non-goals.
- [ ] Implement `validate_paperclip_long_range_phase0_20260511.py` to fail if:
  - Governance does not own runtime readiness;
  - Finbot has any advice/trading ownership;
  - local LLM is not marked research-only;
  - candidate connectors are called verified without workflow evidence.
- [ ] Run:

```bash
python3 scripts/validate_paperclip_long_range_phase0_20260511.py
```

Expected: JSON status `pass`.

- [ ] Commit:

```bash
git add docs/paperclip_long_range_os/phase0_baseline scripts/validate_paperclip_long_range_phase0_20260511.py
git commit -m "paperclip: define long range company role map"
```

**Phase Gate:** Phase 0 is complete only when the validator passes and the role map is committed.

## 6. Phase 1: Company-Owned Operating Kernel V1

**Purpose:** Prove Paperclip can run real company-owned work without the controller doing domain work.

**Files:**

- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase1_operating_kernel/task_contracts.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase1_operating_kernel/live_issue_readback.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase1_operating_kernel/company_owned_evidence_matrix.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase1_operating_kernel/closeout.md`
- Create: `/vol1/1000/projects/toyresearch/scripts/validate_paperclip_company_owned_kernel_20260511.py`

**Required company-owned issues:**

- Planning: one real user-intake issue.
- Finbot Research: one research-only case deepening issue.
- Governance: one false-pass or capability approval issue.
- Finbot Engineering: one read-only capability/tooling issue.

**Steps:**

- [ ] Create one issue contract per company in `task_contracts.json`.
- [ ] Each contract must include `company`, `agent`, `objective`, `inputs`, `allowed_writes`, `forbidden_outputs`, `validator`, and `closeout_required`.
- [ ] Execute each issue through Paperclip live path when available.
- [ ] Capture issue status, assigned agent, succeeded run id, agent-authored comment, evidence path, validator path, memory no-write or candidate delta, and closeout path in `live_issue_readback.json`.
- [ ] Write `company_owned_evidence_matrix.json` with one row per issue and fields:

```json
{
  "issue_id": "",
  "company": "",
  "agent": "",
  "status": "",
  "succeeded_run_id": "",
  "agent_authored_comment_id": "",
  "artifact_path": "",
  "validator_path": "",
  "memory_delta_or_no_write": "",
  "closeout_path": "",
  "controller_authored_domain_output": false
}
```

- [ ] Implement validator to fail if any row has missing run evidence, missing artifact, missing closeout, missing validator, or `controller_authored_domain_output=true`.
- [ ] Run:

```bash
python3 scripts/validate_paperclip_company_owned_kernel_20260511.py docs/paperclip_long_range_os/phase1_operating_kernel
```

Expected: JSON status `pass`.

- [ ] Commit:

```bash
git add docs/paperclip_long_range_os/phase1_operating_kernel scripts/validate_paperclip_company_owned_kernel_20260511.py
git commit -m "paperclip: prove company owned operating kernel"
```

**Phase Gate:** At least four company-owned issues pass with live readback or a documented no-run blocker that Governance accepts.

## 7. Phase 2: Finbot Research Quality Flywheel

**Purpose:** Move Finbot from a one-time casebook to a repeatable supervised research system that can surface high-quality opportunities and identify why they may be wrong.

**Files:**

- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase2_finbot_flywheel/source_registry.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase2_finbot_flywheel/case_deep_dive_register.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase2_finbot_flywheel/risk_reversal_ledger.jsonl`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase2_finbot_flywheel/human_review_queue.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase2_finbot_flywheel/closeout.md`
- Create: `/vol1/1000/projects/toyresearch/scripts/validate_finbot_research_flywheel_20260511.py`

**Research object model:**

Each deep-dive case must include:

```json
{
  "case_id": "",
  "company_or_theme": "",
  "source_thesis": "",
  "primary_evidence": [],
  "secondary_evidence": [],
  "variant_perception": "",
  "why_it_may_work": "",
  "why_it_may_fail": "",
  "risk_reversal_or_kill_condition": "",
  "research_estimate_range_non_advice": "",
  "next_evidence_action": "",
  "human_review_question": "",
  "status": "research_only_continue"
}
```

**Steps:**

- [ ] Select the strongest `3` cases from `/vol1/1000/projects/toyresearch/docs/paperclip_substantive_batches/2026-05-11_batch1_finbot_quality/opportunity_casebook.json`.
- [ ] For each case, add at least `3` primary or authority evidence entries.
- [ ] For each case, write a contradiction section that can lower confidence.
- [ ] For each case, produce a research estimate range labeled `non_advice`.
- [ ] For each case, write a concrete human review question that asks for a next research action, not a buy/sell decision.
- [ ] Add every weak or generic case to `risk_reversal_ledger.jsonl` or a parked section.
- [ ] Implement validator to fail on advice language, missing primary evidence, missing contradiction, missing human review question, or missing non-advice range.
- [ ] Run:

```bash
python3 scripts/validate_finbot_research_flywheel_20260511.py docs/paperclip_long_range_os/phase2_finbot_flywheel
```

Expected: JSON status `pass`.

- [ ] Commit:

```bash
git add docs/paperclip_long_range_os/phase2_finbot_flywheel scripts/validate_finbot_research_flywheel_20260511.py
git commit -m "finbot: start research quality flywheel"
```

**Phase Gate:** Finbot has at least `3` deep-dive research-only packets that are meaningfully stronger than the Batch 1 casebook and still contain no advice.

## 8. Phase 3: Planning Work Assistant As Main User Loop

**Purpose:** Make Planning the primary company for frequent user inputs and follow-up management.

**Files:**

- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase3_planning_main_loop/intake_register.jsonl`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase3_planning_main_loop/decision_queue.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase3_planning_main_loop/agent_followup_queue.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase3_planning_main_loop/memory_delta_candidates.jsonl`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase3_planning_main_loop/fresh_agent_replay.md`
- Create: `/vol1/1000/projects/toyresearch/scripts/validate_planning_main_loop_20260511.py`

**Steps:**

- [ ] Process `3` real user-intake examples:
  - Paperclip roadmap correction.
  - Finbot research follow-up.
  - Governance/capability enablement follow-up.
- [ ] For each intake, produce:
  - user decision needed;
  - evidence gap;
  - next agent action;
  - stop condition;
  - candidate memory delta.
- [ ] Run a fresh-agent replay: a new agent should read only current truth, decision queue, agent follow-up queue, and memory candidates, then explain the next action without chat history.
- [ ] Implement validator to fail if any intake lacks user decision, evidence gap, agent action, stop condition, or candidate memory.
- [ ] Run:

```bash
python3 scripts/validate_planning_main_loop_20260511.py docs/paperclip_long_range_os/phase3_planning_main_loop
```

Expected: JSON status `pass`.

- [ ] Commit:

```bash
git add docs/paperclip_long_range_os/phase3_planning_main_loop scripts/validate_planning_main_loop_20260511.py
git commit -m "planning: establish main intake loop"
```

**Phase Gate:** Planning can process repeated real inputs and leave enough state for a fresh agent to continue without the original chat.

## 9. Phase 4: Governance, Skill-MCP, Runtime, And Capability Enablement

**Purpose:** Make Governance useful as a capability control plane, not just a policy document.

**Files:**

- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase4_governance_capability/capability_registry.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase4_governance_capability/enablement_decisions.jsonl`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase4_governance_capability/false_pass_regression_result.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase4_governance_capability/runtime_fallback_preflight.md`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase4_governance_capability/closeout.md`
- Create: `/vol1/1000/projects/toyresearch/scripts/validate_governance_capability_phase_20260511.py`

**Capability classes:**

- `verified_workflow`
- `candidate`
- `blocked`
- `quarantined`
- `research_only`

**Steps:**

- [ ] Re-evaluate Readwise, Zotero, Alpaca, Daloopa, Quartr, Binance, HomePC Ollama, SEC EDGAR, SEC companyfacts, local evidence tree, and runtime adapters.
- [ ] Promote only capabilities with read-only workflow proof, evidence path, validator result, and rollback/no-use boundary.
- [ ] Keep endpoint-only, configured-only, app-visible-only, and fixture-only capabilities below `verified_workflow`.
- [ ] Run false-pass regression covering:
  - endpoint-only as verified;
  - fixture-only as live;
  - controller-only artifact as company-owned;
  - Finbot advice disguised as memo;
  - target-price-as-advice;
  - production watchlist leakage;
  - local model production route;
  - quarantined provider enablement.
- [ ] Write runtime fallback/preflight result without mutating native runtime config unless Governance has a bounded config-change record.
- [ ] Implement validator that rejects any unapproved production capability status.
- [ ] Run:

```bash
python3 scripts/validate_governance_capability_phase_20260511.py docs/paperclip_long_range_os/phase4_governance_capability
```

Expected: JSON status `pass`.

- [ ] Commit:

```bash
git add docs/paperclip_long_range_os/phase4_governance_capability scripts/validate_governance_capability_phase_20260511.py
git commit -m "governance: establish capability enablement control plane"
```

**Phase Gate:** Governance can explain why each capability is usable, candidate, blocked, quarantined, or research-only, and the validator enforces that explanation.

## 10. Phase 5: Memory Substrate V1

**Purpose:** Make memory useful for Planning and company handoff without promoting unreviewed model output into authority.

**Files:**

- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase5_memory_substrate/memory_layer_contract.md`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase5_memory_substrate/current_truth_ledger.jsonl`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase5_memory_substrate/authority_ledger.jsonl`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase5_memory_substrate/verbatim_registry.jsonl`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase5_memory_substrate/fresh_agent_blind_test.md`
- Create: `/vol1/1000/projects/toyresearch/scripts/validate_memory_substrate_v1_20260511.py`

**Layer rules:**

- `current_truth`: latest operational state with date and evidence path.
- `authority`: promoted rules only, with Governance approval.
- `verbatim`: exact user wording and source excerpts.
- `rationale`: decision reasoning that can be superseded.
- `sandbox`: experiments, model suggestions, and candidate memory.

**Steps:**

- [ ] Write the layer contract with allowed writers and promotion gates.
- [ ] Convert the latest Paperclip current truth into `current_truth_ledger.jsonl`.
- [ ] Add only already-approved rules to `authority_ledger.jsonl`.
- [ ] Add exact user wording that affects policy or retrieval to `verbatim_registry.jsonl`.
- [ ] Run a fresh-agent blind test using only the memory substrate and current truth.
- [ ] Implement validator that fails if sandbox/candidate entries appear in authority without approval.
- [ ] Run:

```bash
python3 scripts/validate_memory_substrate_v1_20260511.py docs/paperclip_long_range_os/phase5_memory_substrate
```

Expected: JSON status `pass`.

- [ ] Commit:

```bash
git add docs/paperclip_long_range_os/phase5_memory_substrate scripts/validate_memory_substrate_v1_20260511.py
git commit -m "memory: define paperclip substrate v1"
```

**Phase Gate:** A fresh agent can continue Planning and Governance tasks from memory/current truth without reading the full chat, and no unapproved memory is promoted.

## 11. Phase 6: Learning Research And Local LLM Advancement

**Purpose:** Keep learning, memory research, and local model work moving without contaminating production paths.

**Files:**

- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase6_learning_local_llm/research_agenda.md`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase6_learning_local_llm/local_llm_benchmark_v3_rows.jsonl`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase6_learning_local_llm/local_llm_scorer_result.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase6_learning_local_llm/memory_system_comparison.md`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase6_learning_local_llm/governance_decision.md`
- Create: `/vol1/1000/projects/toyresearch/scripts/validate_learning_local_llm_phase_20260511.py`

**Steps:**

- [ ] Re-read local model inputs:
  - `/vol1/1000/projects/toyresearch/docs/LOCAL_MODEL_HANDOVER_20260506.md`
  - `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/`
  - `/vol1/1000/projects/toyresearch/docs/paperclip_substantive_batches/2026-05-11_batch4_local_llm_v2/`
- [ ] Re-read memory research inputs:
  - `/vol1/maint/docs/agent - 记忆系统评审与优化 1.md`
  - `/vol1/maint/docs/agent - 五类agent能力评审.md`
- [ ] Run Local LLM benchmark v3 only if HomePC is reachable and no model download is required.
- [ ] Benchmark task classes:
  - Planning decision extraction;
  - Finbot evidence extraction;
  - Governance false-pass classification;
  - Memory delta classification.
- [ ] Keep outputs research-only and copied/sanitized.
- [ ] Compare Graphiti, MemPalace, LLM Wiki, GBrain, Supermemory, and current ledger approach as design candidates.
- [ ] Governance decision must be one of:
  - `research_only_continue`;
  - `candidate_low_risk_digest_only`;
  - `blocked_quality_or_privacy`;
  - `blocked_homepc_unreachable`.
- [ ] Implement validator that fails if local model output is used as authority, production route, Finbot final judgment, or Planning authority.
- [ ] Run:

```bash
python3 scripts/validate_learning_local_llm_phase_20260511.py docs/paperclip_long_range_os/phase6_learning_local_llm
```

Expected: JSON status `pass`.

- [ ] Commit:

```bash
git add docs/paperclip_long_range_os/phase6_learning_local_llm scripts/validate_learning_local_llm_phase_20260511.py
git commit -m "learning: advance local llm and memory research"
```

**Phase Gate:** Learning Research produces usable research outputs, but Governance still controls every promotion.

## 12. Phase 7: Operator Dashboard And Public Review Cadence

**Purpose:** Make status understandable to the user, another Codex, and external reviewers.

**Files:**

- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase7_operator_review/operator_dashboard.md`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase7_operator_review/review_packet_manifest.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase7_operator_review/public_packet_safety_result.json`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase7_operator_review/next_execution_queue.tsv`
- Create: `/vol1/1000/projects/toyresearch/scripts/validate_operator_review_phase_20260511.py`

**Steps:**

- [ ] Build an operator dashboard with:
  - current status;
  - active companies;
  - last successful issue per company;
  - current blockers;
  - candidate capabilities;
  - next queue;
  - forbidden claims.
- [ ] Build a review packet manifest that includes only safe, relevant artifacts.
- [ ] Copy the safe packet into `/tmp/ChatgptREST-review/paperclip-review-20260510/`.
- [ ] Run secret scan, large file check, forbidden path check, and `sha256sum -c`.
- [ ] Commit and push the public review branch only after safety passes.
- [ ] Implement validator that fails if the dashboard claims production readiness or if review packet safety checks fail.
- [ ] Run:

```bash
python3 scripts/validate_operator_review_phase_20260511.py docs/paperclip_long_range_os/phase7_operator_review
```

Expected: JSON status `pass`.

- [ ] Commit:

```bash
git add docs/paperclip_long_range_os/phase7_operator_review scripts/validate_operator_review_phase_20260511.py
git commit -m "paperclip: publish operator review cadence"
```

**Phase Gate:** A reviewer can inspect current state and next queue without reading the chat or unsafe local state.

## 13. Phase 8: Controlled Autonomy Ramp

**Purpose:** Increase autonomous execution only after company-owned loops, Governance gates, memory substrate, and review cadence are stable.

**Files:**

- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase8_controlled_autonomy/autonomy_policy.md`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase8_controlled_autonomy/autonomy_trial_runs.jsonl`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase8_controlled_autonomy/human_interrupt_log.jsonl`
- Create: `/vol1/1000/projects/toyresearch/docs/paperclip_long_range_os/phase8_controlled_autonomy/final_readiness_audit.md`
- Create: `/vol1/1000/projects/toyresearch/scripts/validate_controlled_autonomy_phase_20260511.py`

**Autonomy levels:**

- `L0_manual_controller`: Codex parent manually assigns and verifies.
- `L1_supervised_company_runs`: companies run bounded tasks; controller verifies.
- `L2_scheduler_with_stop_gates`: scheduler can start approved low-risk tasks; stop gates block risky output.
- `L3_governed_autonomous_research`: approved companies can run research loops with periodic human review.
- `L4_production_autonomy`: not in scope until all earlier phases have repeated evidence.

**Steps:**

- [ ] Write `autonomy_policy.md` with allowed actions for each level.
- [ ] Run at least `3` L1 supervised company runs across Planning, Finbot, and Governance.
- [ ] Run at least `1` L2 scheduler trial on a low-risk Planning or Governance task.
- [ ] Record every interruption or blocked output in `human_interrupt_log.jsonl`.
- [ ] Implement validator that fails if Finbot crosses research-only boundaries, local LLM becomes production route, or any company claims authority without Governance approval.
- [ ] Run:

```bash
python3 scripts/validate_controlled_autonomy_phase_20260511.py docs/paperclip_long_range_os/phase8_controlled_autonomy
```

Expected: JSON status `pass`.

- [ ] Commit:

```bash
git add docs/paperclip_long_range_os/phase8_controlled_autonomy scripts/validate_controlled_autonomy_phase_20260511.py
git commit -m "paperclip: define controlled autonomy ramp"
```

**Phase Gate:** Paperclip can run repeated low-risk company-owned cycles without controller-authored domain outputs, false passes, or boundary violations.

## 14. Recommended Execution Strategy

Do not execute the whole roadmap as one giant opaque goal. Use a long-lived program with phase gates:

1. Run Phase 0 and Phase 1 together because they establish the operating model.
2. Run Phase 2 and Phase 3 in parallel if subagents are available because Finbot and Planning work mostly independently.
3. Run Phase 4 before enabling any new Skill/MCP/runtime/local model capability.
4. Run Phase 5 before claiming durable Planning or cross-company memory.
5. Run Phase 6 as research-only; do not let it block Finbot or Planning unless its outputs are being considered for promotion.
6. Run Phase 7 after every two major phases so public review artifacts stay current.
7. Run Phase 8 only after Phase 1 through Phase 5 have passing evidence.

## 15. Recommended `/goal` Contract For The Next CLI Session

Use this only after confirming the CLI goal store is clean:

```text
/goal 在 /vol1/1000/projects/toyresearch 中执行 docs/superpowers/plans/2026-05-11-paperclip-long-range-operating-system-roadmap.md 的 Phase 0 和 Phase 1：先冻结 long-range current truth 和 company role map，再证明 Planning、Finbot Research、Governance、Finbot Engineering 至少各一个 company-owned issue 真实闭环；每项必须有 task contract、assigned company/agent、artifact、validator、memory_delta 或 no_write、Paperclip readback、closeout、current truth/execution matrix 更新和 focused commit；禁止用 controller-authored domain artifacts、elapsed time、package pass、Pro answer 或 endpoint-only status 当完成；Finbot 禁止投资建议/目标价建议/交易信号/自动交易/production watchlist，本地模型 research-only，quarantined providers 不启用；只有 Phase 0/1 validators 全部通过且 final audit 映射每项要求到证据，才能 complete。
```

## 16. Self-Review

Spec coverage:

- Long-line program instead of Batch 6: covered by Phases 0 through 8.
- Systematic company model: covered by Section 2.
- Stage goals: covered by Section 3 and each phase gate.
- Decomposed execution steps: covered by Sections 5 through 13.
- Finbot, Planning, Governance, Skill/MCP, Runtime, Memory, Local LLM: covered by Phases 2 through 6.
- Avoid false pass and time-based proof: covered by Sections 4, 14, and phase validators.

Placeholder scan:

- No placeholder markers or deferred task names are used.

Boundary scan:

- Finbot remains research-only.
- Local LLM remains research-only.
- Quarantined providers remain no-production-use.
- Runtime is placed under Governance capability control rather than a competing business company.
