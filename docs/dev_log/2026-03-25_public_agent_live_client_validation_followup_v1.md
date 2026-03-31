# 2026-03-25 Public Agent Live Client Validation Follow-up v1

## Summary

This follow-up records a second, stricter client-side validation pass after `a0ca045`, using the real public advisor-agent MCP client wrapper rather than only route/unit tests.

The result is mixed:

1. The server-side boundary fixes in `a0ca045` are still directionally correct.
2. One concrete client bug was reproduced.
3. One additional high-confidence live-usage issue surfaced around the wrapper/public-MCP interaction path.

This note is intentionally narrower than the earlier ergonomic issue pack. It focuses on **real client execution behavior**.

## What Was Re-run

I re-ran the same class of tasks that originally motivated the boundary fix:

1. ChatGPT public-repo review through the public advisor-agent MCP surface
2. Gemini public-repo review through the same surface, with imported-code intent

The concrete client used was:

- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

The public MCP target was:

- `http://127.0.0.1:18712/mcp`

## Validation Attempts

## Attempt A: invalid transport timeout override

I intentionally ran:

- agent mode
- explicit `--timeout-seconds 300`
- explicit `--request-timeout-seconds 20`

This is expected to fail locally, because the request transport timeout is shorter than the total agent run budget.

That local validation did fail as expected.

However, the returned error payload still said:

1. `still_running_possible = true`
2. `recovery_hint = Use advisor_agent_status/advisor_agent_wait ...`

This is wrong for a preflight validation failure. No remote turn was started.

## Attempt B: valid ChatGPT/Gemini public-repo turns

I then ran valid agent-mode requests with:

1. explicit `session_id`
2. public GitHub repo reference
3. no invalid timeout override

Observed behavior in the initial validation window:

1. the wrapper process remained blocked waiting for MCP response
2. no summary file was written yet
3. the explicit `session_id` was not visible in `controller_runs` or `advisor_runs` during the initial observation window
4. `chatgptrest-mcp.service` journal did show live `POST /mcp` requests and `Processing request of type CallToolRequest`

That means the client did reach the public MCP service, but from the client side the behavior is still too opaque:

1. there is no fast accepted-state handoff
2. there is no early durable breadcrumb proving the turn is running
3. the client cannot tell whether it is waiting on valid execution, stuck transport, or MCP-session semantics

## Most Likely Root-Cause Direction

I am deliberately not overstating causality, but there is a strong lead:

1. the repo's own live validation path in `chatgptrest/eval/public_agent_mcp_validation.py` performs `initialize` before `tools/call`
2. the current client wrapper in `chatgptrest_call.py` directly POSTs `tools/call`

That difference is important enough that it should be treated as a real investigation item.

I am not claiming this is the only cause.

I am claiming:

1. the wrapper/live-client path is not yet as robust as the repo's own validation path
2. the discrepancy is large enough to deserve service-side or shared-client remediation

## Issues

## Issue 1: preflight validation errors are mislabeled as possibly running

### Reproduced

Yes.

### Why it matters

This is not cosmetic. A coding agent will take `still_running_possible=true` seriously and may start polling `advisor_agent_status` for a session that never existed remotely.

That wastes time and makes error recovery noisier than it needs to be.

### Expected behavior

For local/client-side validation failures:

1. `still_running_possible` should be `false`
2. recovery hint should say this was rejected before submission
3. the message should clearly distinguish `local_validation_failure` from `transport_timeout`

### Suspect area

- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

Specifically the combination of:

1. `_validate_agent_mode_args`
2. broad exception handling in `_run_agent_turn`
3. `_looks_like_transport_timeout`

## Issue 2: wrapper/live public-MCP turn path is still not operationally crisp enough

### Reproduced

Yes, as a live client experience issue.

### What was observed

For valid requests:

1. the client blocked
2. no immediate summary/artifact was produced
3. no early durable run/session visibility appeared in `controller_runs` or `advisor_runs` during the initial observation window
4. MCP service logs did show the request entering the service

### Why it matters

From a client perspective, that is a bad ambiguity zone:

1. maybe the request is running normally
2. maybe the wrapper skipped a required MCP handshake step
3. maybe the service accepted the HTTP request but has not materialized recoverable session state yet

Any one of those is survivable.

The problem is that the current client cannot tell which one it is.

### Most likely improvement directions

One of these should happen:

1. move the wrapper onto the same shared MCP HTTP client semantics used by the repo's validation/integration helpers
2. explicitly perform `initialize`/session bootstrap in the wrapper before `tools/call`
3. ensure `advisor_agent_turn` returns an early accepted-state response with durable session visibility fast enough for client recovery
4. expose a stronger wait/accepted contract so the client is never left inferring whether the turn exists

## Recommended Follow-up

## P0

1. Fix the false `still_running_possible=true` classification for local validation failures.

## P1

1. Unify the wrapper's MCP transport path with the repo's validated MCP HTTP client/handshake path.
2. Re-run the same ChatGPT/Gemini public-repo review scenarios after that unification.

## P1/P2

1. Tighten the accepted-state semantics of `advisor_agent_turn`, so that a client can always tell whether a live turn now exists and can be resumed.

## Scope Boundary

This follow-up does **not** invalidate `a0ca045`.

The route/boundary semantics fixed there still look correct.

The new issues are about:

1. wrapper-side preflight recovery semantics
2. live wrapper/public-MCP operational behavior

Those are client-surface quality issues, not evidence that the original route fix should be reverted.
