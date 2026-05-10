# Paperclip Full-Company Overnight Ops Goal

Date: 2026-05-10
Mode: Codex2 `/goal` instruction file
Repository: `/vol1/1000/projects/toyresearch`

## Objective

Continue Paperclip full-company overnight operations for at least 8 wall-clock
hours and at least 12 effective cycles. Do not create an unrelated small goal,
do not overwrite an existing run, and do not stop at a single package, validator
pass, or live issue pass.

The goal is twofold:

1. Make Finbot operate as an open-ended, research-only alpha discovery engine
   that can surface surprising opportunity leads for human review.
2. Keep all other Paperclip companies productive through a global backlog and
   work-stealing rule, so the run never idles while Finbot is waiting.

This goal must not produce investment advice, buy/sell/hold recommendations,
target-price recommendations, position sizing, broker actions, automatic
trading, production watchlists, or trade signals.

## Freshness Audit First

Before doing work, perform a freshness audit.

Read stable contracts:

- `/vol1/1000/projects/toyresearch/AGENTS.md`
- `/vol1/1000/projects/toyresearch/paperclip_company_os/AGENTS.md`
- `/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company/AGENTS.md`
- `/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company/README.md`

Then discover latest state with `find`, `stat`, and `git log`:

- latest `current_truth`
- latest `blocker_board`
- latest `execution_matrix`
- latest `validation`
- latest `live_readback`
- latest `finbot_open_alpha_discovery`
- latest `finbot_engineering_capability_platform`
- latest `finbot_research_os`
- latest memory, skill-mcp, runtime, local-llm, and Labebe artifacts

Treat these older files as baseline/reference only, not live truth:

- `/vol1/1000/projects/toyresearch/docs/PAPERCLIP_RUNTIME_INVENTORY_20260506.md`
- `/vol1/1000/projects/toyresearch/docs/PAPERCLIP_SKILLS_MCP_RUNTIME_RECONCILED_20260506.md`
- `/vol1/1000/projects/toyresearch/docs/LOCAL_MODEL_HANDOVER_20260506.md`
- `/vol1/maint/docs/个人投研助理方法.md`
- `/vol1/maint/docs/投研助理插件推荐.md`
- `/vol1/maint/docs/agent - 记忆系统评审与优化 1.md`
- `/vol1/maint/docs/agent - 五类agent能力评审.md`

Those baseline files are useful for design context, but they must not override
later 2026-05-09 or 2026-05-10 artifacts.

## Current Run To Continue

The known current Finbot open-alpha run root is:

`/vol1/1000/projects/toyresearch/docs/finbot_open_alpha_discovery_20260510/2026-05-10_8h_open_ended_alpha_discovery`

Check it first. If a process like this is active:

`python3 scripts/run_finbot_open_alpha_discovery_20260510.py --cycles 12 --interval-minutes 44 --min-wall-hours 8`

then use the existing run root and the existing contract start time as the
wall-clock baseline. Monitor it, fill evidence gaps, add live readback, add
`runtime_summary.json`, and continue other company work while the runner waits.

If no active process exists, continue from that run root or create an explicit
continuation run root that references it. Do not start an unrelated duplicate
run.

Known unfinished open-alpha state to verify and repair:

- `20_final_validation.json` may be failed.
- `runtime_summary.json` may be missing.
- cycle count may be below 10 or 12.
- `top_surprising_opportunities` may be below target.
- `15_live_paperclip_readback.json` may be pending.
- `16_cycle_by_cycle_substantive_delta_audit.json` may be empty or stale.

## Global Work-Stealing Rule

Eight hours is a continuous production window, not a waiting period.

If any company is waiting, blocked, polling, between cycles, already ahead of
one metric, or inactive for 15 minutes without substantive delta, immediately
pull the highest-value executable item from the global backlog.

Waiting on Finbot, provider keys, external connectors, long polling, background
runners, or cycle spacing is not a reason to idle.

Keep or create:

- `global_backlog.jsonl`
- `cycle_ledger.jsonl`
- `acceptance_ledger.jsonl`
- `company_execution_matrix`
- `current_truth`
- `blocker_board`
- `anti_idle_audit`
- `work_stealing_audit`

## Effective Cycle Rule

Run at least 12 effective cycles. A cycle should be 20-45 minutes apart when the
run is active, but the cycle only counts if it has substantive delta.

Substantive delta examples:

- new source
- new theme
- new primary evidence
- new counter-evidence
- new opportunity
- case upgrade or downgrade
- valuation range update
- risk/reversal QA
- adapter smoke
- validator hardening
- negative fixture
- live issue/comment/status change
- memory_delta
- current truth correction
- skill/MCP readiness check
- runtime fallback check
- Planning retro
- Governance audit
- Labebe evidence

Invalid cycles:

- sleep-only
- pure polling
- waiting for a runner
- rerunning the same validator without changed input
- manifest refresh without content changes
- only writing a plan
- only summarizing old conclusions
- reading without artifact change

Invalid cycles do not count and must be replaced.

## Finbot Research

Operate Finbot as an open-ended, research-only alpha discovery engine. The goal
is to surface many surprising opportunity leads for human review, not to promise
profits or give investment instructions.

Minimum targets:

- source candidates >= 120
- themes or industry-chain directions >= 50
- research-only opportunity candidates >= 180
- alpha-qualified cases >= 40
- full decision memo cases >= 18
- top surprising opportunities >= 20

Each alpha, full memo, or top opportunity must include:

- source-alpha rationale
- variant thesis
- primary evidence or explicit missing-primary-evidence downgrade
- counter-evidence
- valuation range as research estimate, not target price advice
- risk/reversal QA
- catalyst or evidence watch window
- next evidence action
- human review question

Actively downgrade generic, parked, noisy, or low-evidence cases.

## Finbot Engineering

First repair the policy/documentation mismatch:

- Update `/vol1/1000/projects/toyresearch/paperclip_finbot_engineering_company/AGENTS.md`
  so it matches the README `capability_lab_v1` state.
- The AGENTS file should allow read-only contracts, fixtures, validators,
  prototypes, and governed handoff.
- It must still forbid production trading, real config mutation, broker action,
  automatic trading, native MCP/skill/runtime mutation, and writes outside the
  approved scope.

Then improve capability platform v1:

- source registry and source scoring
- evidence extraction and claim ledger
- valuation range prototype
- human-review alerts
- decision memo tooling
- adapter smoke
- hard validators
- negative fixtures

Verify or extend at least these paths:

- SEC / primary filing path
- market or price context path
- blogger / expert / article extraction path
- local history / local document extraction path

Check Readwise, Zotero, Alpaca, Daloopa, Quartr, and Binance. If a read-only
smoke can be done, do it. Otherwise write a blocked enablement issue. Do not
mark candidate, endpoint-only, or fixture-only capability as enabled.

## Planning Work Assistant

Planning must do real operations work, not observer summaries.

Required outputs:

- overnight execution queue
- cross-company priority board
- cycle rhythm log
- quality retro
- next-day handoff
- next 7-day operations queue

Complete at least 3 real Planning tasks:

1. Finbot opportunity research scheduling retro.
2. Governance / Memory / Skill-MCP coordination plan.
3. One real planning input replayed through memory_delta and closeout.

## Governance

Governance must unify company governance, Skill/MCP governance, Memory
governance, and Runtime/fallback governance.

Required decisions:

- Whether Controller & Runtime Company should be downgraded to a Governance
  runtime/fallback agent or infra-lab.
- Company architecture correction.
- Boundary policy.
- Current truth.
- Blocker board.
- Execution matrix.

Validate at least 12 false-pass classes:

- old pass reuse
- controller-only evidence pretending to be agent-owned run
- endpoint-only enabled
- fixture pretending to be live
- candidate connector pretending to be enabled
- advice disguised as memo
- target-price-as-advice
- production watchlist
- broker action
- sleep-only cycle
- missing-primary-evidence pretending to be alpha
- weak runtime smoke pretending to prove capability

## Memory

Memory company or Memory agent must summarize and operationalize prior memory
research.

Compare:

- Graphiti
- Supermemory
- GBrain
- MemPalace
- LLM Wiki
- thought-retriever
- EvidenceLog
- AuthorityLedger

Required outputs:

- one Planning real-case memory replay
- one Finbot case memory_delta
- current truth / authority / verbatim / rationale layering proposal
- explicit list of what must not be promoted to authority

No provider may be promoted to authority without Governance approval.

## Skill/MCP

Skill/MCP agent must verify current skills, MCP servers, plugins, Superpowers,
gstack, skill manager ideas, open-source skill projects, and Paperclip
configured capabilities.

Required outputs:

- keep / deprecate / candidate / install-risk matrix
- enablement backlog
- no unaudited install
- no native runtime/MCP/skill production config mutation

## Runtime

Runtime agent must update capability image and fallback strategy.

Check:

- codex1
- codex2
- claudekimi
- claudeds
- claudeminmax
- Kimi Code ACP
- Pro or Gemini advisory path where available

Rules:

- claudemi and claudegac are out of the effective pool unless live evidence
  proves otherwise.
- MiniMax, DeepSeek, Tavily, and Brave remain quarantined/no-production-use and
  are not active blockers.
- Do not use `cli --help` or `python --version` as capability proof.

## Learning Research

Learning Research Company must turn these into an executable research map:

- memory research
- local model research
- Skill/MCP research
- runtime/coding-plan research
- Finbot framework research

## Local LLM Research

Local model work is research-only.

Use `LOCAL_MODEL_HANDOVER_20260506.md` only as baseline. Run a fresh live probe
if needed. Produce:

- capability matrix
- cost/risk matrix
- future token-saving automation candidate list

Do not connect HomePC Ollama into current Paperclip production building. Do not
download large models. Do not spend proxy traffic.

## Labebe

Labebe AI Transformation / Design Studio must run at least one real toy-company
AI transformation loop.

Required outputs:

- claim-safe evidence
- AI transformation opportunity map
- demo backlog
- design/content/commerce candidate options
- blockers and next actions

## Live Paperclip Evidence

Use Paperclip live issues where possible.

Finbot Research, Finbot Engineering, Planning, Governance, Memory, Skill-MCP,
Runtime, Learning Research, Local LLM, and Labebe must each have at least one
live issue or a clearly declared carrier issue.

Each completed item needs:

- assigneeAgentId or equivalent agent ownership
- succeeded run evidence
- agent-authored comment or createdByRunId
- artifact path that can be read back
- closeout
- status sync

If live company/agent/API support is missing, create a carrier issue and record
the real owner, gap, and future repair. Do not fake agent ownership.

## Final Required Artifacts

Produce or update:

- final evidence manifest
- `runtime_summary.json`
- final current truth
- blocker board
- execution matrix
- global backlog ledger
- cycle-by-cycle substantive_delta audit
- anti-idle / work-stealing audit
- company-by-company closeout
- Finbot source alpha map
- theme map
- opportunity board
- top surprising opportunities
- alpha casebook
- full decision memo pack
- valuation range pack
- alert/watch window pack
- parked/noise/rejected register
- evidence/claim ledger
- Planning overnight closeout
- Governance correction packet
- Memory research and replay packet
- Skill-MCP readiness matrix
- Runtime fallback matrix
- Learning Research roadmap
- Local LLM research-only packet
- Labebe transformation packet
- live Paperclip readback
- hard validator result
- false-pass audit result
- next 7-day operations queue

## Completion Criteria

Only call `update_goal(status=complete)` when all are true:

- wall clock >= 8 hours
- effective cycles >= 12
- Finbot source candidates >= 120
- themes >= 50
- opportunity candidates >= 180
- alpha-qualified cases >= 40
- full memo cases >= 18
- top surprising opportunities >= 20
- workflow-verified data/source capability >= 6
- at least 10 company lines have real progress and closeout
- current truth, blocker board, execution matrix, and global backlog are synced
- negative guardrails all work
- live issue readback passes or carrier gaps are explicit
- no in-scope P0/P1 blocker remains
- every counted cycle has substantive_delta
- no sleep-only cycle is counted

## Forbidden

Do not:

- auto-trade
- call broker action
- give investment advice
- give target-price recommendations
- give position sizing
- create production watchlist
- create trade signal
- fake live evidence
- fake enabled connector
- call a prototype production-ready
- complete because one package exists
- complete because one validator passed
- complete because one live issue is done
- complete because Finbot metrics reached one stage
- complete while another company is waiting
- complete because old documents say something is already done
- stage unrelated dirty files

If final criteria are not all met, continue the next cycle, add evidence, fix
validators, expand sources, upgrade strong cases, downgrade weak cases, repair
company architecture, add memory_delta, check Skill/MCP readiness, check runtime
fallback, or work another company backlog item.
