# Finbot Supervised Research Ops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a supervised Finbot research loop that can start from Fu Zong and several high-value bloggers, produce many research targets and opportunity cases with evidence, and keep all outputs under human review rather than investment advice.

**Architecture:** Finbot must run as a research operating system, not as a trading or advice bot. The loop is: source intake -> claim extraction -> official corroboration -> research case register -> risk QA -> supervised review window -> memory delta candidate -> closeout/status sync. Governance, Memory, and Skill/MCP companies run in parallel to keep policy, runtime, source tiers, and memory rules aligned while Finbot is monitored.

**Tech Stack:** Paperclip API/server, existing Paperclip companies/issues/agents, `paperclip_finbot`, `paperclip_finbot_engineering_company`, JSONL/Markdown evidence ledgers, existing SEC/CNINFO-capable connector paths, existing Superpowers planning/execution skills, ChatgptREST/Pro only as open-ended advisor after local evidence exists.

---

## Non-Negotiable Boundaries

- No broker integration, trading execution, automatic portfolio action, buy/sell recommendation, or investment-readiness claim.
- Do not call the output a production Finbot investment system. The target state is `supervised_research_ops_ready`.
- Fu Zong and bloggers are source/discovery inputs, not authority. Their claims remain D-tier until corroborated by official filings, exchange disclosures, company reports, transcripts, or validated datasets.
- Pro is not an audit gate and not an approval authority in this phase. Pro is an open-ended advisor only; another Codex or the controller decides what to adopt.
- Do not resume the previously paused Finbot Orchestrator until a launcher denylist and no-advice gate are verified.
- Existing key-rotation blockers can stay out of scope for this phase, but any affected keyed providers must remain marked `no_production_use`.
- HomePC/Ollama/local models remain research-only. They must not be used for Finbot, Planning, Governance, Memory authority promotion, Skill/MCP optimization, or Paperclip system-building until Local LLM Research produces a repo-stable evidence pack and Governance approves quality/fallback/privacy gates.

## Target Absolute Paths

Primary plan:

- `/vol1/1000/projects/toyresearch/docs/superpowers/plans/2026-05-07-finbot-supervised-research-ops-master-plan.md`

Execution run root to create:

- `/vol1/1000/projects/toyresearch/paperclip_finbot/company_runs/2026-05-07_finbot_supervised_research_ops/`

Monitoring root to create:

- `/vol1/1000/projects/toyresearch/docs/finbot_research_ops_monitor_20260507/`

Local LLM research evidence root to create:

- `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/`

Important existing inputs:

- `/vol1/maint/docs/个人投研助理方法.md`
- `/vol1/maint/docs/投研助理插件推荐.md`
- `/vol1/1000/projects/toyresearch/docs/LOCAL_MODEL_HANDOVER_20260506.md`
- `/vol1/1000/projects/toyresearch/docs/LOCAL_MODEL_RESEARCH_INVENTORY.md`
- `/vol1/1000/projects/toyresearch/docs/local_llm_non_use_gate_20260507/local_llm_non_use_audit_20260507.md`
- `/vol1/1000/projects/toyresearch/docs/local_llm_non_use_gate_20260507/paperclip_readback_LOC4.json`
- `/vol1/1000/projects/toyresearch/paperclip_finbot/`
- `/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company/`
- `/vol1/1000/projects/toyresearch/docs/paperclip_finbot_fuzong_evidence_handoff_20260507.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_only_agent_killswitch_20260507/no_resume_until_denylist_gate_20260507.md`
- `/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company/runs/2026-05-07_finbot_v2_1_repair_execution/day8_fuzong_source_catalog/fuzong_source_catalog_closeout.md`
- `/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company/runs/2026-05-07_finbot_v2_1_repair_execution/day10_primary_source_evidence_graph/day10_closeout.md`

## Required Output File Structure

Create these files under `/vol1/1000/projects/toyresearch/paperclip_finbot/company_runs/2026-05-07_finbot_supervised_research_ops/`:

- `00_controller_contract.md`: scope, stop gates, runtime boundaries, and exact success criteria.
- `01_status_baseline/paperclip_finbot_live_status.json`: live company/project/issue/agent state snapshot.
- `01_status_baseline/status_baseline_closeout.md`: what is live truth versus old docs.
- `02_launcher_safety/launcher_denylist_contract.json`: forbidden runtime/actions/phrases/states.
- `02_launcher_safety/launcher_safety_closeout.md`: proof that old unsafe orchestrator is not resumed or is safely replaced.
- `03_source_intake/fuzong_source_catalog.jsonl`: Fu Zong materials with raw/source status.
- `03_source_intake/blogger_source_catalog.jsonl`: additional blogger/source account catalog.
- `03_source_intake/source_intake_closeout.md`: coverage numbers and gaps.
- `04_claims/claim_ledger.jsonl`: extracted claims with source spans and source tier.
- `04_claims/entity_map.json`: normalized company/ticker/topic/entity map.
- `04_claims/claim_extraction_closeout.md`: extraction coverage, rejected claims, and blockers.
- `05_official_evidence/official_evidence_graph.json`: official-source corroboration graph.
- `05_official_evidence/connector_blockers.json`: connector failures, skipped routes, and retry rules.
- `05_official_evidence/official_evidence_closeout.md`: what was corroborated versus parked.
- `06_research_cases/research_case_register.jsonl`: many supervised research cases, not advice.
- `06_research_cases/research_case_closeout.md`: distribution by sector, market, evidence level, and review status.
- `07_review_windows/review_window_register.jsonl`: human-supervised monitoring windows.
- `07_review_windows/review_window_closeout.md`: no-advice validation and manual review queue status.
- `08_risk_qa/risk_qa_ledger.jsonl`: adversarial questions, missing evidence, contradiction checks.
- `08_risk_qa/risk_qa_closeout.md`: blocked/parked/pass-to-supervised-review counts.
- `09_memory/memory_delta_candidates.jsonl`: memory candidates only, no authority promotion.
- `09_memory/memory_preflight_closeout.md`: memory write policy result and future promotion conditions.
- `10_governance_parallel/governance_closeout.md`: Governance/Memory/Skill-MCP work completed while Finbot ran.
- `11_pro_advisory/OPEN_QUESTIONS_FOR_PRO.md`: open-ended Pro prompt.
- `11_pro_advisory/pro_advice_digest.md`: Pro advice summarized as optional input, not gate.
- `12_final_closeout/finbot_supervised_research_ops_closeout.md`: final readiness statement and residual gaps.
- `12_final_closeout/evidence_manifest.json`: machine-checkable manifest of all above artifacts.

Create these monitoring files under `/vol1/1000/projects/toyresearch/docs/finbot_research_ops_monitor_20260507/`:

- `monitor_log.jsonl`: every controller/watchdog observation.
- `latest_session_watchdog_status.md`: latest status of session `019dfbfd-1722-7a93-b40a-0c1f7e8e2605`.
- `latest_session_watchdog_status.json`: same status in JSON.

Create these Local LLM Research evidence files under `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/`:

- `00_research_company_contract.md`: owner, scope, stop gates, issue references, and no-use boundary.
- `01_loc3_loc4_paperclip_readback.json`: LOC-3/LOC-4 issues, comments, agent, and status readback.
- `02_k1_live_probe_report.md`: HomePC/Ollama/ComfyUI/TRELLIS capability verification with source paths.
- `03_k2_digest_extraction_benchmark.md`: real digest/extraction benchmark design, inputs, model outputs, scoring, and result.
- `04_k3_quality_fallback_privacy_decision.md`: quality/fallback/privacy decision with pass/block evidence.
- `05_k4_future_automation_policy.md`: allowed_later / forbidden_now / promotion gates policy.
- `06_k5_non_use_audit.md`: non-use audit that cites LOC-4 and current route quarantine.
- `07_governance_decision.md`: Governance decision on whether any automation class is allowed later.
- `08_memory_delta_candidates.jsonl`: candidate memory entries only; no authority promotion.
- `09_closeout.md`: honest closeout: `local_llm_research_pack_ready` or exact blocker.
- `evidence_manifest.json`: machine-checkable manifest with hashes for this evidence pack.

---

## Phase 1: Reset The Truth And Prevent False Progress

- [ ] Read `AGENTS.md` in `/vol1/1000/projects/toyresearch` and `paperclip_finbot_engineering_company/AGENTS.md`.
- [ ] Read the files listed in "Important existing inputs".
- [ ] Query live Paperclip state for `Finbot Investment Research`, its projects, issues, agents, and active runs.
- [ ] Write `/vol1/1000/projects/toyresearch/paperclip_finbot/company_runs/2026-05-07_finbot_supervised_research_ops/01_status_baseline/paperclip_finbot_live_status.json`.
- [ ] Write `/vol1/1000/projects/toyresearch/paperclip_finbot/company_runs/2026-05-07_finbot_supervised_research_ops/01_status_baseline/status_baseline_closeout.md` with four sections:
  - `Live Truth`
  - `Historical Assets`
  - `Blocked Or Unsafe Components`
  - `Usable Components For This Run`
- [ ] Explicitly state that `FIN-13` remaining blocked does not block this new supervised research ops run, as long as no advice/trading/readiness claim is made.
- [ ] Verify no active Finbot run is already executing unsafely. If any active run exists, pause it or mark it for human review before continuing.

Acceptance:

- `paperclip_finbot_live_status.json` exists and includes company id, project ids, issue ids, agent ids, and active run count.
- `status_baseline_closeout.md` clearly separates live state from stale docs.
- No old Finbot run is treated as proof that the new loop works.

---

## Phase 2: Add Launcher Safety And No-Advice Guardrails

- [ ] Inspect the current Finbot launcher/orchestrator path in `/vol1/1000/projects/toyresearch/paperclip_finbot/`.
- [ ] Inspect the research-only killswitch evidence under `/vol1/1000/projects/toyresearch/docs/finbot_research_only_agent_killswitch_20260507/`.
- [ ] Create `02_launcher_safety/launcher_denylist_contract.json` with these required fields:

```json
{
  "version": "2026-05-07",
  "mode": "supervised_research_only",
  "forbidden_actions": [
    "broker_integration",
    "trade_execution",
    "portfolio_rebalance",
    "buy_sell_recommendation",
    "investment_readiness_claim",
    "production_watchlist_signal"
  ],
  "forbidden_output_terms_zh": [
    "买入",
    "卖出",
    "建仓",
    "清仓",
    "目标价",
    "确定性机会",
    "投资建议"
  ],
  "allowed_output_objects": [
    "SourceRecord",
    "ClaimRecord",
    "EvidenceRecord",
    "ResearchCase",
    "ReviewWindow",
    "RiskQuestion",
    "MemoryDeltaCandidate"
  ],
  "old_orchestrator_resume_policy": "deny_until_launcher_gate_passes",
  "pro_policy": "advisor_only_not_gate"
}
```

- [ ] If the old orchestrator can be safely wrapped, add or configure a preflight that loads `launcher_denylist_contract.json` before any Finbot job.
- [ ] If the old orchestrator cannot be safely wrapped quickly, do not resume it. Create a fresh restricted run contract in `00_controller_contract.md` and execute via bounded scripts/manual Paperclip issue updates.
- [ ] Write `02_launcher_safety/launcher_safety_closeout.md` containing exact evidence paths and commands used.

Acceptance:

- Old paused Finbot Orchestrator is not resumed without proof.
- A no-advice gate exists before any research cases are generated.
- Any failure here stops the run before source intake.

---

## Phase 3: Build Fu Zong Plus Blogger Source Intake

- [ ] Use Fu Zong as the first source family. Start from existing Day8 Fu Zong catalog and `/vol1/1000/projects/toyresearch/docs/paperclip_finbot_fuzong_evidence_handoff_20260507.md`.
- [ ] Expand the Fu Zong catalog until each item has one of these exact source states:
  - `transcript_ready`
  - `ocr_visual_only`
  - `metadata_only`
  - `source_url_unverified`
  - `fetch_blocked`
- [ ] Add at least five additional high-value blogger/source accounts as `D-tier discovery sources`. Initial suggested candidates:
  - `Clouded Judgement / Jamin Ball` for SaaS and cloud market structure.
  - `The Bear Cave / Edwin Dorsey` for short risk and fraud-risk discovery.
  - `TSOH Investment Research / Alex Morris` for long-form quality-company analysis.
  - `Base Hit Investing / John Huber` for business-quality and valuation framing.
  - `Doomberg` for energy, macro, commodity, and policy-risk themes.
- [ ] If better sources are found in existing Readwise/Zotero/clippings/history, replace the suggestions but preserve the source-tier rules.
- [ ] Write `03_source_intake/fuzong_source_catalog.jsonl`. Each row must include:

```json
{
  "source_id": "fuzong-0001",
  "source_family": "fuzong",
  "title": "",
  "url_or_local_path": "",
  "published_at": "",
  "captured_at": "",
  "raw_state": "metadata_only",
  "market_scope": ["A股", "美股", "港股"],
  "mentioned_entities": [],
  "source_tier": "D",
  "claim_ready": false,
  "blocker": ""
}
```

- [ ] Write `03_source_intake/blogger_source_catalog.jsonl` using the same schema.
- [ ] Write `03_source_intake/source_intake_closeout.md` with counts:
  - Fu Zong total records.
  - Fu Zong `transcript_ready` records.
  - Blogger total records.
  - Claim-ready records.
  - Fetch-blocked records.

Acceptance:

- At least 30 total source records across Fu Zong and bloggers, unless existing material availability makes that impossible; if impossible, the blocker must identify exact missing source access.
- At least 10 records must be claim-ready or the run must stop as `source_insufficient`.
- No source-only record can become a research case without a claim and corroboration attempt.

---

## Phase 4: Extract Claims And Normalize Entities

- [ ] Extract claims only from claim-ready source records.
- [ ] Every claim must have a source span or a precise local evidence reference.
- [ ] Write `04_claims/claim_ledger.jsonl`. Each row must include:

```json
{
  "claim_id": "claim-0001",
  "source_id": "",
  "source_family": "",
  "claim_text": "",
  "claim_type": "business_quality|growth|margin|valuation|risk|fraud_risk|policy|industry_structure|capital_allocation",
  "mentioned_entities": [],
  "market_scope": [],
  "source_span": "",
  "source_tier": "D",
  "needs_official_corroboration": true,
  "status": "needs_evidence"
}
```

- [ ] Normalize company/ticker/entity names into `04_claims/entity_map.json`.
- [ ] Deduplicate claims that are the same thesis in different wording.
- [ ] Reject claims without traceable source evidence and record rejection counts in `04_claims/claim_extraction_closeout.md`.

Acceptance:

- At least 20 claims are extracted, or the run stops with `claim_insufficient`.
- Every claim has traceable evidence.
- No claim is promoted beyond `needs_evidence` before official corroboration.

---

## Phase 5: Corroborate With Official Evidence

- [ ] Use existing validated connector routes first: SEC and CNINFO.
- [ ] Treat unavailable routes such as OpenBB/SSE/SZSE/HKEX/DART as connector blockers unless they can be verified quickly without unsafe credentials or key-rotation blockers.
- [ ] For each entity, attempt at least one official evidence lookup when the market scope has a known route.
- [ ] Write `05_official_evidence/official_evidence_graph.json` with:
  - entities
  - source claims
  - official evidence references
  - corroboration status
  - contradictions
  - missing-evidence blockers
- [ ] Write `05_official_evidence/connector_blockers.json`.
- [ ] Write `05_official_evidence/official_evidence_closeout.md` with counts:
  - claims corroborated
  - claims contradicted
  - claims parked for missing evidence
  - connector blockers

Acceptance:

- At least 10 claims receive official corroboration or official contradiction.
- Any claim without official evidence remains `parked` or `needs_evidence`.
- Evidence graph contains enough references for a fresh reviewer to verify why each case is allowed or blocked.

---

## Phase 6: Generate Research Cases And Review Windows

- [ ] Convert corroborated or partially corroborated claims into `ResearchCase` objects, not investment signals.
- [ ] Write `06_research_cases/research_case_register.jsonl`. Each row must include:

```json
{
  "case_id": "rc-0001",
  "entity": "",
  "ticker": "",
  "market": "",
  "theme": "",
  "why_interesting": "",
  "claim_ids": [],
  "official_evidence_ids": [],
  "risk_question_ids": [],
  "status": "ready_for_supervised_review",
  "forbidden_advice_check": "pass",
  "human_review_required": true
}
```

- [ ] Write `07_review_windows/review_window_register.jsonl`. Each row must include:

```json
{
  "review_window_id": "rw-0001",
  "case_id": "",
  "monitoring_question": "",
  "evidence_to_watch": [],
  "review_frequency": "weekly|monthly|event_driven",
  "stop_condition": "",
  "human_review_required": true,
  "not_investment_advice": true
}
```

- [ ] Run the no-advice wording gate over both registers.
- [ ] Write `06_research_cases/research_case_closeout.md` and `07_review_windows/review_window_closeout.md`.

Acceptance:

- At least 15 `ResearchCase` records exist, unless earlier phases formally stopped as insufficient evidence.
- At least 10 `ReviewWindow` records exist.
- No case contains buy/sell/target-price/position-sizing language.
- Cases are useful enough for a human to choose which companies deserve deeper research next.

---

## Phase 7: Risk QA And Supervised Closeout

- [ ] For each `ready_for_supervised_review` case, create at least two adversarial risk questions.
- [ ] Write `08_risk_qa/risk_qa_ledger.jsonl`.
- [ ] Block cases with missing primary evidence, contradiction, source-only hype, or forbidden wording.
- [ ] Write `08_risk_qa/risk_qa_closeout.md` with counts by status:
  - `ready_for_supervised_review`
  - `needs_evidence`
  - `parked`
  - `blocked`
- [ ] Write `12_final_closeout/evidence_manifest.json` with all required artifacts and hashes.
- [ ] Write `12_final_closeout/finbot_supervised_research_ops_closeout.md`.

Acceptance:

- A fresh reviewer can start from final closeout and inspect every case through source -> claim -> official evidence -> risk QA -> review window.
- The final status is one of:
  - `supervised_research_ops_ready`
  - `blocked_source_insufficient`
  - `blocked_launcher_safety`
  - `blocked_evidence_connector`
- Do not use `production_ready`, `investment_ready`, or `watchlist_ready`.

---

## Phase 8: Run Governance, Memory, Skill/MCP Improvements In Parallel

While Finbot is monitored, improve other Paperclip companies so the system does not remain controller-only.

- [ ] Governance company produces a Finbot policy closeout in `10_governance_parallel/governance_closeout.md` covering:
  - source-tier policy
  - old-orchestrator resume policy
  - no-advice gate
  - Pro-as-advisor policy
  - human-review-required policy
- [ ] Memory company produces `09_memory/memory_delta_candidates.jsonl` and `09_memory/memory_preflight_closeout.md`.
- [ ] Skill/MCP governance validates current usable versus blocked tools and writes the result into `10_governance_parallel/governance_closeout.md`.
- [ ] Planning company is not required to run a full planning task here, but its memory and status-sync requirements must be checked against the same governance format.
- [ ] Any company agent output must have evidence paths. Chat-only summaries do not pass.

Acceptance:

- Finbot run is not only Codex-generated. It must have Paperclip company/issue/agent status sync evidence, even if Codex remains controller.
- Governance/Memory/Skill-MCP produce artifacts that can be re-used by future company runs.
- No authority memory promotion happens in this phase.

---

## Phase 8A: Stabilize Local LLM Research Company Evidence Pack

This is a parallel required lane. It does not unblock Finbot execution, and it must not introduce local models into Finbot or Paperclip system-building. Its purpose is to turn prior LOC-3/LOC-4 work from Paperclip comments and HomePC-local notes into repo-stable artifacts that future agents can trust.

- [ ] Query live Paperclip state for `Local LLM Research` company `292a1435-520a-405a-9c65-34c35390c843`.
- [ ] Read LOC-3 `MASTER-K Local LLM research-only loop` and LOC-4 `MASTER-K2 Local LLM non-use route quarantine and audit`, including all comments and readbacks.
- [ ] Write `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/00_research_company_contract.md` with:
  - company id and assigned agent id
  - LOC-3 and LOC-4 issue ids
  - no-use boundary
  - exact output files
  - stop conditions
- [ ] Write `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/01_loc3_loc4_paperclip_readback.json` by saving live issue/comment/readback data.
- [ ] Mirror K1 evidence into `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/02_k1_live_probe_report.md`.
  - Include HomePC endpoint `192.168.1.17`.
  - Include Ollama 0.17.5, local endpoint, installed models, tool-calling status, and GPU state.
  - Cite `/vol1/1000/projects/toyresearch/docs/LOCAL_MODEL_HANDOVER_20260506.md`.
- [ ] Replace the weak K2 comment-only conclusion with `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/03_k2_digest_extraction_benchmark.md`.
  - Use copied, non-production sample text only.
  - Benchmark at least one digest task and one structured extraction task.
  - Compare local model output against a cloud/controller baseline or a deterministic expected answer.
  - Record latency, output quality notes, failure modes, and whether the result is usable for future offline/private automation.
  - If HomePC is unreachable or running the model would be unsafe, write `blocked_homepc_unreachable` or `blocked_benchmark_not_run` with exact command/evidence.
- [ ] Replace the weak K3 comment-only conclusion with `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/04_k3_quality_fallback_privacy_decision.md`.
  - State whether quality passed, partially passed, or failed.
  - State cloud fallback route.
  - State privacy/no-network evidence or blocker.
  - State that no production route is enabled.
- [ ] Mirror and refine K4 into `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/05_k4_future_automation_policy.md`.
  - `allowed_later`: private digest/extraction on copied non-production docs, embeddings/chunking, low-risk summarization, offline benchmarks, internal code analysis.
  - `forbidden_now`: Finbot, Planning, Governance, Memory authority promotion, Skill/MCP optimization, production runtime, autonomous execution, external-account actions, financial advice/watchlist/trading, secret handling.
  - `promotion_gates`: 3+ real benchmarks, quality scorer, fallback path, no-network proof, latency/cost comparison, operator approval, rollback/non-use audit.
- [ ] Mirror LOC-4 into `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/06_k5_non_use_audit.md`.
  - Cite `/vol1/1000/projects/toyresearch/docs/local_llm_non_use_gate_20260507/local_llm_non_use_audit_20260507.md`.
  - Cite `/vol1/1000/projects/toyresearch/docs/local_llm_non_use_gate_20260507/local_llm_route_quarantine_validator_20260507.json`.
  - Confirm `ollama_gpu0` is not in active primary/fallback routes.
- [ ] Ask Governance to write `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/07_governance_decision.md`.
  - Current expected decision: `research_only_continue`.
  - Do not approve any production/local-model route unless K2/K3 evidence passes all gates.
- [ ] Write `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/08_memory_delta_candidates.jsonl`.
  - Candidate deltas only.
  - No authority memory promotion.
- [ ] Write `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/evidence_manifest.json` with paths, size, sha256, and source issue ids.
- [ ] Write `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/09_closeout.md`.

Acceptance:

- The Local LLM Research result is not only Paperclip comments or HomePC-local files. It has repo-stable evidence under `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/`.
- K2 and K3 are no longer vague capability statements; they either contain real benchmark/decision evidence or explicit blockers.
- LOC-3 and LOC-4 are reconciled in one readback artifact.
- No local model is used by Finbot, Planning, Governance, Memory authority promotion, Skill/MCP optimization, or Paperclip system-building.
- Final status is one of:
  - `local_llm_research_pack_ready`
  - `blocked_homepc_unreachable`
  - `blocked_benchmark_not_run`
  - `blocked_quality_fallback_privacy_gate`

---

## Phase 9: Ask Pro For Open-Ended Advice Only

- [ ] Create `11_pro_advisory/OPEN_QUESTIONS_FOR_PRO.md` after local evidence exists.
- [ ] The Pro prompt must be open-ended and advisory. Use this exact stance:

```text
请作为开放式顾问阅读这个 Finbot supervised research ops 运行包。不要做通过/不通过审核，不要给封闭式结论，不要把自己当 gate。

请重点指出：
1. 这个系统离一个真正有用的个人投研研究助手还差什么；
2. 哪些研究对象、source tier、证据链、风险 QA 或 review window 设计最容易误导用户；
3. 如果下一轮只做 3-5 件事，哪些最值得做；
4. 如何在不输出投资建议、不接交易、不制造虚假确定性的前提下，让系统更快地产生高质量研究机会；
5. 你认为 Fu Zong 与其他 blogger/source account 应该怎样分层、交叉验证和淘汰。

最终决策权在另一个 Codex/controller，不在 Pro。请给建议和批判性意见，不要替代本地决策。
```

- [ ] Save the answer or pending job reference under `11_pro_advisory/`.
- [ ] Write `11_pro_advisory/pro_advice_digest.md` separating:
  - `Pro Suggestions`
  - `Local Codex Decision`
  - `Accepted`
  - `Rejected`
  - `Deferred`

Acceptance:

- Pro is not treated as a validator.
- Local Codex/controller explicitly decides what to adopt.

---

## Phase 10: Monitoring Rules For Session `019dfbfd-1722-7a93-b40a-0c1f7e8e2605`

Every 30 minutes, the controller/watchdog should check:

- Is the target Codex session still writing or has it stopped?
- Did it drift into Pro audit/gate mode?
- Did it drift into investment advice, watchlist signals, buy/sell wording, or production readiness claims?
- Did it only write controller docs instead of making Paperclip company/issue/agent artifacts?
- Are required evidence files being created under the run root?
- Is the Local LLM Research evidence pack being mirrored into `/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/` instead of remaining only in Paperclip comments or HomePC-local files?
- Are active runs left dangling?
- Is the final closeout status honest and bounded?

Monitoring artifacts:

- `/vol1/1000/projects/toyresearch/docs/finbot_research_ops_monitor_20260507/monitor_log.jsonl`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_ops_monitor_20260507/latest_session_watchdog_status.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_ops_monitor_20260507/latest_session_watchdog_status.json`

Acceptance:

- If the session is stale for more than 45 minutes, mark `needs_intervention`.
- If drift indicators appear, write a correction prompt into the monitor status file.
- If the Finbot run artifacts are complete but Local LLM/Governance/Memory/Skill-MCP terminal evidence is still missing, mark `total_plan_incomplete_continue_required`.
- Only if all required Finbot artifacts, Local LLM evidence pack, company closeouts, manifests, validator/readbacks, and status sync evidence exist and pass, mark `supervised_research_ops_ready_for_controller_review`.

---

## Exact Prompt To Send To Codex CLI Session `019dfbfd-1722-7a93-b40a-0c1f7e8e2605`

```text
请接手执行这个总计划到终态。注意：这是 master plan，不是单个 phase、单个 blocker、单个 evidence pack，也不是让你停在某个“blocked terminal package”后汇报。

/vol1/1000/projects/toyresearch/docs/superpowers/plans/2026-05-07-finbot-supervised-research-ops-master-plan.md

你的任务是按该计划持续推进，直到所有非 Finbot 之外的配套公司闭环和 Finbot supervised research ops 都达到计划定义的终态，或者遇到无法由本地解决的 hard external blocker。常规子步骤不要等用户确认。

总目标：
1. Finbot 不能被声明为生产级投资建议系统，但必须跑成 supervised research ops：从福总开始，再纳入几个高价值 blogger/source account，形成 source intake -> claim extraction -> official evidence corroboration -> research case register -> risk QA -> supervised review window -> memory delta candidate -> closeout/status sync 的完整闭环。
2. Governance、Memory、Skill/MCP、Local LLM Research 等公司要补齐可验收 evidence、policy、status sync、closeout，不能只写 controller 自己的说明。
3. 你可以处理用户明确授权的旁路任务，例如 runtime_allocator 或 claudeminmax 问题；但旁路任务必须收口为 evidence/commit/closeout，然后立刻回到本 master plan。旁路任务不是停止 master plan 的理由。

边界：
- 不做交易、不接券商、不输出买卖建议、不输出目标价、不声明投资可用。
- Pro 只作为开放式顾问，不作为审核 gate。最终由本地 Codex/controller 决策。
- 不要恢复旧 Finbot Orchestrator，除非 launcher denylist 和 no-advice gate 已验证。
- 每个公司/agent/issue 的动作都要有 evidence path，不能只有聊天总结。
- Governance、Memory、Skill/MCP 公司要并行补齐政策和状态台账；Finbot 监督研究闭环是当前业务主线，但不是唯一交付物。
- Local LLM Research 公司也要并行补齐 repo-stable 证据包：/vol1/1000/projects/toyresearch/docs/local_llm_research_execution_20260508/。本地模型仍然 research-only，不得进入 Finbot、Planning、Governance、Memory authority、Skill/MCP 优化或 Paperclip system-building。

必须完成或明确阻断：
1. 建立 run root：/vol1/1000/projects/toyresearch/paperclip_finbot/company_runs/2026-05-07_finbot_supervised_research_ops/
2. 完成 00 到 12 的全部 Finbot 产物文件。
3. 完成 Local LLM Research evidence pack：00_research_company_contract.md 到 09_closeout.md，加 evidence_manifest.json。
4. 至少生成 30 条 source records、20 条 claims、15 条 research cases、10 条 review windows，除非正式记录 source/evidence insufficiency blocker。
5. 写出 Finbot evidence_manifest.json 和 final closeout。
6. Finbot 最后只允许使用这些状态之一：supervised_research_ops_ready、blocked_source_insufficient、blocked_launcher_safety、blocked_evidence_connector。
7. Local LLM 最后只允许使用这些状态之一：local_llm_research_pack_ready、blocked_homepc_unreachable、blocked_benchmark_not_run、blocked_quality_fallback_privacy_gate。
8. Governance、Memory、Skill/MCP 的最终状态必须能在 repo 文档或 Paperclip issue/status readback 中看到 evidence path、validator/result、memory_delta candidate、closeout/status sync。不能只停在“我做了摘要”。
9. 总计划没有完成前，不要输出“done/final/terminal package”式收口。每次阶段性汇报都必须列出“已完成、未完成、下一步继续执行项”，然后继续做下一项。

停止条件只有这些：
- 所有必须产物、manifest、validator/readback、closeout/status sync 都完成，并且状态与计划允许状态一致。
- 或者遇到真正的 hard external blocker，例如必须由用户在 provider/account dashboard 轮换 key、必须人工提供不可替代的输入、远程机器不可达且没有替代验证路径。

如果中途遇到 blocker，不要停止在一句总结；要写 blocker artifact、更新 manifest、给出下一步可执行动作，然后继续处理不依赖该 blocker 的并行公司治理任务。只有当所有剩余工作都依赖同一个 hard external blocker 时，才允许停，并且 final closeout 必须列出剩余阻断项、已完成证据、恢复后第一条命令/动作。
```

---

## Self-Review

Spec coverage:

- Finbot can start supervised research from Fu Zong and bloggers: covered by Phases 3-7.
- Many opportunities/targets without advice: covered by ResearchCase and ReviewWindow outputs.
- Governance and other companies improve while monitored: covered by Phase 8.
- Local LLM Research is added as a parallel required repo-stable evidence pack: covered by Phase 8A.
- Pro is advisor only: covered by Phase 9.
- Another Codex can execute: covered by exact prompt and absolute paths.
- 30-minute monitoring: covered by Phase 10 and companion watchdog script.

Placeholder scan:

- This plan intentionally avoids placeholders. Every required artifact has an absolute path and expected schema or section list.

Residual risk:

- This plan cannot by itself make a currently stopped external Codex session continue. It creates a clear execution contract and a local watchdog. If no agent is attached to the target session, the user or controller must paste the exact prompt into that session.
