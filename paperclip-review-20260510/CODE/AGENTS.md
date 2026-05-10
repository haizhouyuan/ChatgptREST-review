# Toyresearch Agent Operating Rules

Last updated: 2026-05-07

This workspace is a mixed research and execution area for Paperclip, PECL,
Labebe, Finbot, runtime governance, local model research and related demos.
Do not assume the historical PECL package is the active task for every request.

## Current Controller Priority

The active direction is to make Paperclip production-usable as a company
operating system, starting from the current Pro-reviewed blocked baseline:

1. Treat `production-usable: blocked` as the current execution queue, not as a
   finish line.
2. Continue converting every in-scope P0/P1 blocker into issue-owned company work
   until all master acceptance criteria pass. Provider key rotation is no longer
   part of the user's active goal; keep affected providers quarantined instead of
   stopping the lane for rotation.
3. Use existing Paperclip companies and runtime/governance assets where useful.
4. Keep implementation inspectable, evidence-backed and fail-closed.
5. Preserve evidence artifacts so another agent can continue without re-deriving state.

If the user's latest instruction conflicts with an older PECL document, follow the
latest user instruction and record the conflict in the new artifact or closeout.

## Current Paperclip Stop Rule

For Paperclip production/company work, the previous Pro-reviewed terminal package
is only a truthful blocked baseline. It is not the user's requested end state.

Current controlling plan:

- `docs/superpowers/plans/2026-05-07-paperclip-unblock-to-passed-master-plan.md`

Do not stop merely because a Pro answer says it is acceptable to stop as a
blocked closeout. That permission applied to the review package, not to the
user's current execution goal.

Allowed final responses for this lane are only:

- `PASSED`: all user-scoped master acceptance criteria pass with artifact paths
  and validator outputs. This may still keep specific providers in no-production-use
  quarantine.
- `HARD_EXTERNAL_BLOCKER`: a real paid/account/legal/download/finance action
  that is explicitly part of the user's current goal requires user authorization,
  and all other executable work is done.
- `STILL_BLOCKED_AFTER_EXECUTION`: every executable path was attempted, and each
  remaining blocker has terminal evidence, owner, next required external input
  and Paperclip readback.

Do not stop for MiniMax / DeepSeek / Tavily / Brave provider key rotation. The
user has clarified that these rotations are not the goal and may not be available.
Record them only as provider quarantine / no-production-use constraints unless
the user explicitly reopens credential rotation as the active task.

The following phrases are not terminal completion unless backed by exact issue
IDs, evidence, validator result, memory closeout and Paperclip readback:

- `registered, not executed`
- `future run needed`
- `done with caveats`
- `partial success`
- `blocked terminal package`

## Current Read Set

For current Paperclip company/MVP/governance work, read these first:

- `docs/superpowers/plans/2026-05-07-paperclip-unblock-to-passed-master-plan.md`
- `docs/PAPERCLIP_PRODUCTION_MASTER_PLAN_20260507.md`
- `docs/paperclip_production_current_truth_20260507.md`
- `docs/paperclip_company_blocker_board_20260507.md`
- `docs/paperclip_company_execution_matrix_20260507.md`
- `docs/2026-05-06_paperclip_mvp_execution_plan.md`
- `docs/2026-05-06_paperclip_learning_research_company_requirements.md`
- `docs/PAPERCLIP_RUNTIME_INVENTORY_20260506.md`
- `docs/PAPERCLIP_SKILLS_MCP_RUNTIME_RECONCILED_20260506.md`
- `docs/PAPERCLIP_CREDENTIALS_AND_PLANS_AUDIT_20260506.md`

For personal investment assistant work, also read:

- `/vol1/maint/docs/个人投研助理方法.md`
- `/vol1/maint/docs/投研助理插件推荐.md`

For memory-management research, also read:

- `/vol1/maint/docs/agent - 记忆系统评审与优化 1.md`
- `/vol1/maint/docs/agent - 五类agent能力评审.md`

For local model research, read:

- `docs/LOCAL_MODEL_HANDOVER_20260506.md`

## When To Read The Historical PECL Package

Only treat `planning/20260428_pecl_full_implementation_prd/` as the required
authority package when the task explicitly continues old PECL lanes, Labebe DTC
acceptance, PCL-019/PCL-020 lane-runner work, Hermes production-beta history, or
old stage-artifact closeouts.

When needed, the minimum PECL read set is:

- `planning/20260428_pecl_full_implementation_prd/00_FINAL_FULL_IMPLEMENTATION_PRD.md`
- `planning/20260428_pecl_full_implementation_prd/01_CURRENT_TRUTH_BASELINE.md`
- `planning/20260428_pecl_full_implementation_prd/03_FULL_COMPLETION_ROADMAP.md`
- `planning/20260428_pecl_full_implementation_prd/06_SOURCE_AUTHORITY_AND_SUPERSESSION.md`
- `planning/20260428_pecl_full_implementation_prd/08_EVIDENCE_INDEX.md`
- `planning/20260428_pecl_full_implementation_prd/10_STAGE_REVIEW_PROTOCOL.md`
- `planning/20260428_pecl_full_implementation_prd/HUMAN_CONTROLLER_CORRECTION_LOG.md`

Do not force this PECL read set onto unrelated Paperclip MVP planning work.

## Current Product Boundaries

- `PCL Runtime` / `PECL Runtime Steward` has value as an infrastructure lab, not as
  the current business-product mainline.
- Do not continue `runtime_allocator` hardening unless the user explicitly makes it
  the current task.
- `HomePC Ollama` is research-only until local model quality, fallback and runtime
  policy are proven. Do not use it to build Paperclip.
- `claudemi` and `claudegac` are out of the effective runtime pool because credits
  are exhausted.
- `Kimi Code` is a Paperclip native ACP candidate and should be included in runtime
  research and future preflight design.
- Personal Finbot work is currently investigation, problem analysis and framework
  selection only. No production watchlist, trade signal, investment advice, broker
  action or automatic financial decision flow is authorized.
- Finbot may become production-usable only as a research-only evidence workflow:
  material intake, source evidence, validator, no-advice/no-watchlist audit,
  memory closeout and Paperclip readback. It must remain blocked for investment
  advice, watchlists, trading signals and broker/account actions.
- Memory providers including Graphiti, MemPalace, Supermemory and GBrain may only
  produce no-write challenger evidence or `candidate_memory_delta` until
  Governance explicitly approves promotion. Synthetic/local provider tests do not
  override public-doc, privacy, provenance, export or account-boundary blockers.

## Target Company Shape

Use this as the default Paperclip organization target unless the user updates it:

- Governance Company: company governance, Skill/MCP governance and memory-management
  governance. It sets rules and reviews proposals; it does not consume all business work.
- Planning Work Assistant: primary high-frequency work assistant for strategy,
  HR/organization notes and meeting recording management.
- Learning Research Company: memory architecture, Skill/MCP research, runtime/Kimi
  Code research, local model research and Finbot framework research.
- Personal Investment Research Assistant: research-only Finbot lane for current-state
  audit, historical asset analysis and future architecture selection.
- Labebe AI Transformation: keep as demo/MVP business transformation lane.

## Task Contract Rule

Every non-trivial agent or runtime task must have a short contract:

- objective;
- required context files;
- allowed read scope;
- allowed write scope;
- forbidden actions;
- runtime recommendation;
- expected evidence artifact;
- validation command or inspection method;
- stop condition.

If a task cannot name its evidence artifact, it is not ready to run.

## Runtime Delegation Rule

Use runtime lanes conservatively:

- `codex1`: controller, architecture judgment, final review, critical implementation.
- `claudekimi`: complex orchestration or long-chain research with a bounded contract.
- `claudeds`: coding fallback and cost/caching experiments.
- `claudeminmax`: repetitive audits, comparisons, low-risk automation, future Finbot
  batch processing candidates.
- `Kimi Code`: ACP/native runtime candidate, read-only/smoke first.
- `Gemini` / Pro: second-opinion review or external advisory packet when justified.

Do not delegate the immediate critical-path blocker if the controller needs the
answer before doing useful local work.

## Evidence Rule

No claim is complete unless a fresh agent can inspect the artifact path.
Chat-only summaries do not pass closeout.

For the current Paperclip production lane, a done/pass/scope-pass claim must have:

- issue ID;
- run ID or explicit no-run reason;
- stable evidence path;
- validator result;
- memory closeout or `no_write_reason`;
- Paperclip status/comment/readback;
- fail-closed blocker handling.

If any of those are missing, the correct status is blocked, not complete.

For current Paperclip MVP work, prefer artifacts under:

- `docs/`
- `docs/superpowers/plans/`
- `planning/20260428_pecl_full_implementation_prd/stage_artifacts/` only when
  continuing historical PECL lane-runner work.

## Editing Rule

This repository is noisy and contains unrelated dirty files. Never reset, revert
or normalize changes you did not make. Keep edits tightly scoped and state what
you touched in the final answer.

## Superpowers Note

Superpowers is available as local skills through the shared Codex skills root in
new Codex sessions. It is a skill workflow package, not a MCP/app tool namespace.
Use Superpowers-style plans for multi-step work, but do not let its defaults
override the user's latest scope corrections.
