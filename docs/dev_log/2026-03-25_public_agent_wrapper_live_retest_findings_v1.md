# 2026-03-25 Public Agent Wrapper Live Retest Findings v1

## Summary

I re-tested the wrapper-side fixes from:

1. `74dc247` — wrapper handoff semantics
2. `75ff09d` — docs for the wrapper fixups

From the client perspective:

1. `ISSUE-0020` is fixed.
2. The core handoff part of `ISSUE-0021` is materially improved.
3. A new sync-path issue was reproduced and should be tracked separately.

## What Passed

## 1. `ISSUE-0020` is fixed

Re-test:

- agent mode
- `--timeout-seconds 300`
- `--request-timeout-seconds 20`

Observed now:

1. `failure_stage = preflight`
2. `submission_started = false`
3. `still_running_possible = false`
4. recovery hint explicitly says the request did not start remotely

That is the correct client behavior.

## 2. Deferred early-summary handoff now works for real live requests

I re-ran real wrapper requests against the live public MCP service using public repo inputs.

### ChatGPT path

Observed summary file now includes:

1. `session_id`
2. `submission_started = true`
3. `submission_stage = submitted`
4. `delivery.mode = deferred`
5. `lifecycle.phase = accepted`
6. `recommended_client_action = wait`
7. provider-selection metadata with the normalized public repo URL

### Gemini code-review path

Observed summary file now includes:

1. `session_id`
2. `submission_started = true`
3. `delivery.mode = deferred`
4. `lifecycle.phase = accepted`
5. provider-selection metadata showing:
   - `requested_provider = gemini`
   - `enable_import_code = true`
   - normalized GitHub repo URL

This means the client no longer sits in the earlier ambiguous state where a valid request produced no usable early breadcrumb.

## Expected conflict still behaves correctly

I also re-tested:

- `goal_hint = gemini_research`
- `enable_import_code = true`

That still fails with:

- `gemini_import_code_deep_research_conflict`

This is expected policy behavior, not a regression.

## New Issue

## ISSUE-0022: sync planning path can leave `out-summary` stuck at raw MCP initialize state

### Reproduced

Yes.

### Scenario

Wrapper invocation:

1. `goal_hint = planning`
2. simple planning-style message
3. `out-summary` enabled
4. normal agent timeout

### Observed behavior

The summary file was created quickly, but it contained only an initialize-like state:

1. `status = initialized`
2. `result.status = initialized`
3. `submission_stage = initialized`
4. `submission_started = false`
5. no route
6. no next action

At the same time, the wrapper process itself was still running after the summary file was written.

After an additional observation window, the summary file remained in that initialized state instead of advancing to an accepted turn summary.

### Why this matters

This is a real client-surface bug:

1. the summary file is supposed to be an early handoff for the turn
2. instead, on this path it can expose raw MCP session-bootstrap state as if it were the task summary
3. the client is left with a misleading artifact that says the request was not submitted yet, even though the wrapper is still running

### Scope

I only reproduced this on the sync planning path so far.

I did **not** observe it on the deferred ChatGPT/Gemini repo-review paths above.

So this should be tracked as a new issue, not as evidence that `ISSUE-0021` remains unfixed wholesale.

## Recommendation

## Keep the current wrapper fix

Do not revert `74dc247`. The improvements for preflight recovery semantics and deferred handoff are real.

## Track the new issue separately

Open a new issue specifically for:

- early summary writing the MCP initialize result instead of the accepted turn summary on at least one sync path

## Follow-up investigation target

The most likely place to inspect is the summary-writing state machine in:

- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

The bug likely sits in the interaction between:

1. MCP initialize/bootstrap
2. early-summary persistence
3. sync vs deferred branch handling
