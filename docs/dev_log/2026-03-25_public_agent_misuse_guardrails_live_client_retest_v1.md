# 2026-03-25 Public Agent Misuse Guardrails Live Client Retest v1

## Summary

I re-tested the `9d1177d` guardrail package from the real client side.

Result:

1. the code and unit/integration tests pass
2. the live wrapper path still does **not** expose the richer upstream caller identity I expected to see
3. because of that, I am opening a new issue only for caller-identity observability, not for the whole guardrail bundle

This note does **not** claim the new microtask and duplicate-session guards are broken.
It claims the caller-identity part is still not showing up correctly in the most important real client path.

## What I validated

## Code/test baseline

At the time of validation:

1. `HEAD = 9d1177d`
2. `tests/test_agent_mcp.py` and `tests/test_routes_agent_v3.py` were already reported green by the implementing agent
3. I also verified the repo was on the documented fix commits

## Live wrapper case

I ran a real wrapper-based public-agent request using:

1. `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
2. `goal_hint=code_review`
3. explicit `session_id = agent_sess_guardrail_identity_test_20260325`
4. a real heavy review prompt

The early summary showed the turn was accepted and backgrounded correctly.

I then inspected the persisted session file:

- `state/agent_sessions/agent_sess_guardrail_identity_test_20260325.json`

Observed `task_intake.context.client`:

```json
{
  "instance": "public-mcp",
  "name": "mcp-agent"
}
```

That is still the generic identity.

I expected to see a richer caller identity reflecting the actual upstream MCP client/wrapper.

## Why this matters

The whole point of this guardrail family was not only to block misuse, but also to make public-agent traffic attributable to the real caller.

If the live wrapper path still collapses to:

1. `name = mcp-agent`
2. `instance = public-mcp`

then server-side observability is still too coarse for the most common coding-agent path.

That means:

1. session attribution remains weaker than intended
2. duplicate/misuse investigation still has to infer the caller from prompt/session patterns
3. the service-side caller-preservation change is not yet delivering its full practical value for this client path

## Scope boundary

I am **not** opening a new issue for:

1. microtask blocking
2. duplicate heavy-session reuse

Reason:

I did not get a clean enough live trace for those two behaviors in this pass, and I do not want to overclaim.

The only fully evidenced live-client issue here is the caller-identity one.

## New issue

## ISSUE-0023: live wrapper path still persists generic `mcp-agent/public-mcp` caller identity

### Reproduced

Yes.

### Evidence

1. live wrapper request accepted successfully
2. persisted session file exists
3. `task_intake.context.client` remains generic instead of carrying richer upstream MCP caller identity

### Expected behavior

For the standard wrapper path, I expected persisted session state to preserve fields such as:

1. actual MCP client name
2. client id / wrapper identity
3. any richer upstream caller labeling now available from `agent_mcp`

### Most likely investigation target

The mismatch is probably in one of these places:

1. the wrapper is not actually establishing MCP client identity in a way that survives into the tool execution context
2. `agent_mcp` is collecting the richer caller identity but the live public MCP transport does not expose it the same way as tests/mock contexts do
3. the richer caller identity is reaching `/v3/agent/turn` but is later overwritten or collapsed before session persistence

## Recommendation

Keep the current guardrail bundle in place.

But open a follow-up specifically for:

- proving that the standard live wrapper path really persists the real upstream caller identity end-to-end
