# Finbot Engineering Capability Platform v1 Plan

Date: 2026-05-09
Status: execution plan for codex2
Plan path: `/vol1/1000/projects/toyresearch/docs/superpowers/plans/2026-05-09-finbot-engineering-capability-platform-v1-plan.md`

## 0. Purpose

Build the missing Finbot engineering substrate so `Finbot Investment Research` can keep producing high-quality research without ad hoc scripts.

This is not another opportunity-case run. This plan promotes `paperclip_finbot_engineering_company` from a dry-run build harness into a governed capability lab that explores, validates, and packages read-only data sources, skills, schemas, validators, runners, valuation ranges, alerting, and decision-memo tooling for Finbot agents.

The operating rule is:

`Engineering builds and proves capability -> Governance approves boundary -> Finbot Research uses capability -> Planning turns results into follow-up.`

## 1. Current Facts To Treat As Input

### 1.1 Finbot Research state

Current root:

`/vol1/1000/projects/toyresearch/docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp/`

Current latest relevant commits:

- `70c380e9c finbot: add alpha quality research gate`
- `215497de3 finbot: enforce sustained research hard gate`
- `722079a80 finbot: repair research os v1 acceptance gates`
- `4d7321748 finbot: integrate research os v1 capability and supervised mvp`

Current accepted capability:

- `79_alpha_final_validator_result.json` reports `FINBOT_ALPHA_QUALITY_OUTPUT_PASS`.
- Six research-only alpha cases exist: `YELP`, `SERV`, `NKE`, `CRM`, `TXN`, `MU`.
- These cases have primary evidence bindings and no-advice/no-trading guards.

Current limitations:

- This is still a research-line alpha checkpoint, not an investment decision system.
- No valuation range layer exists.
- No watch-only market data workflow is active.
- No decision memo layer exists.
- No alert/monitoring layer exists.
- No A-share data workflow is active.
- Readwise, Zotero, Alpaca, Daloopa, Quartr, and Binance are still `candidate_to_enable`, not workflow-verified.

### 1.2 Finbot Engineering state

Engineering repo:

`/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company`

Current state from `README.md` and `AGENTS.md`:

- State is `dry_run_only`.
- It is a build harness, not the real Finbot company.
- It currently forbids real market data refresh, broker/trading APIs, production watchlist jobs, cron/daemon registration, MCP activation, skill install/edit, and writes outside the repo root.
- Existing useful assets include:
  - issue contracts `FINBOT-ENG-000` through `FINBOT-ENG-005`
  - write-scope policy
  - issue closeout validator
  - collection/evidence validators
  - primary source evidence graph tests
  - previous full orchestration, repair, v2, and v2.1 run artifacts
  - Kimi Code controlled smoke result

Required shift:

- Keep broker/trading and production mutation forbidden.
- Allow read-only capability exploration under explicit contracts, artifacts, validators, and Governance approval.
- Keep writes scoped to `paperclip_finbot_engineering_company/` for engineering implementation, plus the specific plan/evidence docs under `docs/finbot_engineering_capability_platform_v1/`.

### 1.3 Governance state

Existing candidate connector issues:

- `PAPA-44`: Readwise read-only enablement
- `PAPA-45`: Zotero read-only enablement
- `PAPA-46`: Alpaca watch-only enablement
- `PAPA-47`: Daloopa read-only enablement
- `PAPA-48`: Quartr read-only enablement
- `PAPA-49`: Binance risk-context enablement

Provider quarantine remains:

- MiniMax
- DeepSeek
- Tavily
- Brave

These providers must stay `quarantined_or_no_production_use` unless the user explicitly reopens them.

## 2. Scope

### 2.1 In scope

Finbot Engineering must build or validate:

1. Data source readiness matrix.
2. Read-only connector smoke protocols.
3. Finbot agent skill contracts.
4. Ledger schema extensions for valuation, alerts, decision memos, and source refresh.
5. Hard validators that reject false readiness.
6. A repeatable engineering runner for capability smokes and sample pipelines.
7. A minimal valuation range research prototype.
8. A minimal alert/monitoring prototype.
9. A decision memo draft prototype.
10. Live Paperclip issues proving Engineering, Governance, and Finbot Research handoff.

### 2.2 Out of scope

Finbot Engineering must not:

- output investment advice;
- output target prices as advice;
- place trades;
- call broker order APIs;
- create production watchlists;
- produce trade signals;
- mutate native MCP/skill/runtime configs without explicit Governance approval;
- promote memory authority;
- use quarantined providers;
- let SEC-only or price-only data become an investment conclusion.

Valuation ranges are allowed only as `research_estimate_range`, with evidence, method, assumptions, and invalidation rules. They are not target prices.

## 3. Required Read Set

Codex2 must read these before editing:

- `/vol1/1000/projects/toyresearch/AGENTS.md`
- `/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company/AGENTS.md`
- `/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company/README.md`
- `/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company/RUNLOG.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp/32_tool_routing_policy_operational.md`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp/33_governance_enablement_issue_contracts.json`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp/69_alpha_quality_casebook.json`
- `/vol1/1000/projects/toyresearch/docs/finbot_research_os_v1/2026-05-09_integrated_history_capability_and_mvp/79_alpha_final_validator_result.json`
- `/vol1/maint/docs/个人投研助理方法.md`
- `/vol1/maint/docs/投研助理插件推荐.md`
- `/vol1/maint/docs/agent - 个人投研助理批判.md`
- `/vol1/maint/docs/profinbot批判.md`
- `/vol1/maint/docs/个人 AI 投资助理生态深度研究报告.md`

## 4. Execution Root And Deliverables

Create this root:

`/vol1/1000/projects/toyresearch/docs/finbot_engineering_capability_platform_v1/2026-05-09_capability_platform/`

Required deliverables:

1. `00_execution_contract.md`
2. `01_current_state_audit.md`
3. `02_data_source_readiness_matrix.md`
4. `02_data_source_readiness_matrix.json`
5. `03_governed_connector_smoke_protocol.md`
6. `04_skill_contracts_for_finbot_agents.md`
7. `05_schema_extension_design.md`
8. `06_validator_design.md`
9. `07_runner_design.md`
10. `08_valuation_range_research_prototype.md`
11. `08_valuation_range_research_prototype.json`
12. `09_alert_monitoring_prototype.md`
13. `09_alert_monitoring_prototype.json`
14. `10_decision_memo_prototype.md`
15. `10_decision_memo_prototype.json`
16. `11_engineering_to_research_handoff.md`
17. `12_governance_approval_packet.md`
18. `13_live_paperclip_readback.json`
19. `14_final_validation.json`
20. `15_closeout.md`

Implementation artifacts should live under:

`/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company/`

Suggested implementation paths:

- `contracts/finbot_capability_platform_v1.schema.json`
- `contracts/finbot_data_source_readiness_v1.json`
- `contracts/finbot_agent_skill_contracts_v1.json`
- `contracts/finbot_valuation_range_contract_v1.json`
- `contracts/finbot_alert_contract_v1.json`
- `contracts/finbot_decision_memo_contract_v1.json`
- `tools/finbot_capability_smoke_runner.py`
- `tools/finbot_valuation_range_prototype.py`
- `tools/finbot_alert_prototype.py`
- `tools/finbot_decision_memo_prototype.py`
- `tools/validate_finbot_capability_platform.py`
- `tests/test_finbot_capability_platform.py`

Do not overwrite existing historical runs.

## 5. Data Source Readiness Requirements

Classify each source as exactly one of:

- `workflow_verified`
- `tool_callable_only`
- `endpoint_alive_only`
- `configured_but_unverified`
- `candidate_to_enable`
- `blocked`
- `quarantined_or_no_production_use`

Minimum sources to classify:

### US / global primary evidence

- SEC EDGAR submissions
- SEC companyfacts
- issuer IR pages
- earnings releases / filings
- Form 4
- 13F as ownership context only

### Market data / price context

- Alpaca watch-only
- OpenBB if available
- local price CSV fixture fallback
- public exchange pages where legal and capturable

### Fundamentals / KPI / transcripts

- Daloopa
- Quartr
- SEC filings
- company IR

### Knowledge / source tracking

- Readwise
- Zotero
- Google Drive / local docs
- web-content-extractor
- Chrome DevTools / CDP evidence capture

### A-share / China route candidates

- CNINFO
- SSE
- SZSE
- BSE
- AKShare
- Tushare
- Baostock
- Eastmoney / Tonghuashun only as downgraded secondary routes

### Research and validation frameworks

- TradingAgents / TradingAgents-CN as method reference
- Fincept as terminal/workbench reference
- OpenBB as data access candidate
- Qlib / vectorbt / Backtrader / Lean as validation/backtest candidates
- LangGraph / Agno / PydanticAI as orchestration/schema candidates

## 6. Connector Smoke Rules

Do not treat config presence as readiness.

Each connector must have:

- read-only scope statement;
- secret boundary statement;
- command/tool used;
- stdout/stderr or result summary;
- artifact path;
- rollback/disable note;
- allowed downstream use;
- disallowed downstream use.

For this phase:

- SEC/local docs/web extraction can be used directly if already workflow-verified.
- Alpaca/Daloopa/Quartr/Readwise/Zotero/Binance must remain blocked unless codex2 can prove current-lane read-only workflow verification without exposing secrets or enabling trading.
- If a connector cannot be enabled safely, create a Governance follow-up contract instead of faking success.

## 7. Finbot Agent Skill Contracts

Create concrete skill contracts for Finbot Research agents. Each skill contract must include purpose, input schema, output schema, required evidence, validator, forbidden actions, and example fixture.

Minimum skills:

1. `source_discovery_skill`
2. `source_quality_scoring_skill`
3. `content_ingestion_skill`
4. `primary_evidence_lookup_skill`
5. `claim_extraction_skill`
6. `evidence_binding_skill`
7. `entity_resolution_skill`
8. `valuation_range_research_skill`
9. `catalyst_invalidation_tracking_skill`
10. `risk_qa_skill`
11. `decision_memo_drafting_skill`
12. `alert_monitoring_skill`

These are engineering contracts, not installed global skills unless Governance explicitly approves.

## 8. Schema Extensions

Add schema designs for:

- `ValuationRangeLedger`
- `AlertLedger`
- `DecisionMemoLedger`
- `CatalystLedger`
- `InvalidationLedger`
- `SourceRefreshLedger`
- `DataSourceReadinessLedger`

`ValuationRangeLedger` must not create target prices. It must record:

- method;
- input data;
- date;
- assumptions;
- bull/base/bear research estimate range;
- confidence;
- invalidation;
- evidence ids;
- no-advice disclaimer.

## 9. Prototypes

Build three prototypes using existing alpha cases, without making investment advice.

### 9.1 Valuation range research prototype

Use at least two alpha cases, preferably `YELP` and `NKE` or `TXN` and `MU`.

Output must include:

- current evidence base;
- selected method;
- assumptions;
- bull/base/bear research estimate range;
- missing data;
- invalidation conditions;
- why this is not a target price.

If live market data is unavailable, use a clearly marked local fixture and record that live price workflow is still blocked.

### 9.2 Alert monitoring prototype

Use at least three alpha cases.

Output must include:

- evidence refresh alerts;
- filing update alerts;
- catalyst alerts;
- invalidation alerts;
- stale evidence alerts;
- human-review alerts.

No production watchlist or trade signal.

### 9.3 Decision memo prototype

Use at least two alpha cases.

Output must include:

- thesis;
- source-alpha rationale;
- primary evidence;
- counter-evidence;
- valuation research range if available;
- catalysts;
- invalidation;
- open questions;
- decision status: `continue_research`, `park`, `reject`, or `needs_user_review`.

No buy/sell/hold recommendation.

## 10. Live Paperclip Work

Create or update live Paperclip issues:

### Finbot Engineering issue

Purpose: capability platform implementation and validation.

Must have:

- assignee agent;
- succeeded run;
- accepted agent-authored comment;
- evidence path;
- validator result.

If there is no live Finbot Engineering company, use `Finbot Investment Research` only for handoff and clearly mark the Engineering repo as the implementation owner. Do not pretend a live Engineering company exists if it does not.

### Governance issue

Purpose: approve or block capability boundaries.

Must verify:

- connector statuses;
- no trading/broker permissions;
- no target-price/advice outputs;
- no quarantined provider use;
- no native config mutation without explicit approval;
- Engineering remains capability lab.

### Finbot Research handoff issue

Purpose: acknowledge which Engineering outputs can be used by Finbot agents.

Must not claim investment-readiness.

## 11. Validators

Hard validation must fail if:

- any output contains investment advice, broker action, target price as recommendation, production watchlist, trade signal, position sizing, or automatic trading;
- any connector is marked `workflow_verified` without a read-only workflow proof;
- endpoint-only proof is counted as workflow verification;
- Alpaca/Daloopa/Quartr/Readwise/Zotero/Binance are used without current-lane proof or Governance approval;
- valuation range lacks method/assumptions/evidence/invalidation/no-advice label;
- alert prototype creates production signals instead of human-review alerts;
- decision memo contains buy/sell/hold recommendation;
- live issue closeout lacks succeeded run evidence;
- Engineering writes outside allowed scope without explicit plan update and validation.

## 12. Acceptance Criteria

Completion requires all of:

1. Finbot Engineering scope updated from pure `dry_run_only` to governed `capability_lab_v1`, while preserving no-trading/no-production-mutation boundaries.
2. Data source readiness matrix covers all sources listed in section 5.
3. At least SEC/local docs/web extraction remain workflow-verified with evidence.
4. At least one market-data path is either workflow-verified read-only or explicitly blocked with a fallback fixture; no fake enablement.
5. At least one knowledge-source path is either workflow-verified read-only or explicitly blocked with a follow-up contract; no fake enablement.
6. Agent skill contracts exist for all 12 skills.
7. Schema extensions exist for valuation, alerts, decision memo, catalyst, invalidation and source refresh.
8. Valuation range prototype runs on at least two alpha cases and is marked research-only.
9. Alert prototype runs on at least three alpha cases and produces only human-review alerts.
10. Decision memo prototype runs on at least two alpha cases and produces no buy/sell/hold recommendation.
11. Hard validator passes and has negative fixtures proving false readiness/advice outputs fail.
12. Governance live issue succeeds.
13. Finbot Research handoff live issue succeeds.
14. Engineering implementation evidence has stable paths and, if committed, a scoped commit.

Final status label:

`FINBOT_ENGINEERING_CAPABILITY_PLATFORM_V1_PASS`

Do not call `update_goal(status=complete)` unless `14_final_validation.json` has this exact status.

## 13. Recommended Commit

If changes are committed, use:

`finbot-engineering: build capability platform v1`

Keep unrelated dirty files out of the commit.

