# 2026-04-14 Live Runtime Root-Cure Execution Plan v2

## Why v2 Exists

`v1` closed the send-phase truth drift and the MCP validation drift. The remaining root-cure target is the system-owned live runtime tail that was still surfacing as:

- `TargetClosedError`
- `RuntimeError: <empty error>`
- wait/export recovery stalls that later degrade into `WebRetryBudgetExceeded`
- `needs_followup` jobs that then get tombstoned by backlog janitor as `BacklogJanitorStale`

This is no longer a classification-only problem. It is a missing runtime recovery problem.

## Updated Root-Cause Statement

The remaining defect is asymmetry between providers:

1. Gemini already has executor/provider-side prompt-surface reopen and self-check recovery.
2. ChatGPT still relies too heavily on worker requeue after runtime transport/page loss.
3. The worker/browser retry budget is therefore forced to absorb failures that should have been recovered inside the executor first.
4. Once those jobs fall into `needs_followup`, backlog janitor later turns the symptom into `BacklogJanitorStale`, obscuring the original runtime family.

So the root-cure target is to eliminate system-owned transient failures before they become worker-budget or janitor problems.

## Current Failure Census

Recent live evidence shows the dominant remaining system-owned clusters are:

- `chatgpt_web.ask wait-phase`
  - `Target page, context or browser has been closed`
  - `RuntimeError: <empty error>`
  - backend export/API `429 Too many requests`
- `chatgpt_web.ask send-phase`
  - transient target/page closed before stable thread evidence exists
- downstream symptom inflation
  - `WebRetryBudgetExceeded`
  - `BacklogJanitorStale`

The dominant Gemini failures in the same window are external/precondition families, not the same runtime-recovery gap:

- `GeminiUnsupportedRegion`
- rare `MaxAttemptsExceeded`

## Execution Goals

1. Give ChatGPT the same class of executor-side transient runtime recovery that Gemini already has.
2. Ensure wait/send transient recovery happens before browser retry budget accounting.
3. Convert self-check-detected external/manual issues into explicit follow-up states instead of generic infra churn.
4. Re-run live MCP/public-surface validation, including a real `claudeminmax` scenario.

## Planned Code Changes

### 1. ChatGPT executor transient recovery

- Add explicit ChatGPT wait transient classification.
- On wait transient errors:
  - run `chatgpt_web_self_check`
  - continue waiting if self-check succeeds
  - requeue with explicit transient recovery metadata if self-check still fails transiently
  - escalate to manual follow-up only when self-check reveals verification/captcha/unusual-activity style blockers

### 2. ChatGPT send transient recovery

- Before returning send-phase cooldown/error for transient page/transport failures:
  - run `chatgpt_web_self_check`
  - retry the same ask once or twice under the same idempotency key
- This must preserve the no-duplicate-prompt guarantee.

### 3. Evidence and validation

- Add focused tests for:
  - wait transient recovery success
  - wait transient requeue on failed self-check
  - wait transient manual-followup escalation when self-check sees verification
  - send transient retry after self-check
- Run live validation again:
  - `public_agent_mcp_validation`
  - `public_surface_launch_gate`
  - `public_agent_live_cutover_validation`
  - explicit `requested_executor=claudeminmax` advisor-agent scenario

## Root-Cure Success Standard

This round only counts as successful if all of the following are true:

1. ChatGPT executor recovers transient page/transport loss locally instead of pushing the majority of those cases into worker retry budget.
2. The new tests prove send/wait self-check recovery behavior.
3. Live MCP/public-surface validation still passes.
4. A real `claudeminmax` scenario still works through the MCP/public-agent path after the runtime recovery changes.
5. The remaining irreducible risk is external-only:
   - verification / captcha / login
   - unsupported region
   - upstream web/backend throttling beyond local recovery budget
