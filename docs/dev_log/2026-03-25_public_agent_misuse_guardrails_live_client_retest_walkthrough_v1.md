# 2026-03-25 Public Agent Misuse Guardrails Live Client Retest Walkthrough v1

## What I did

I validated the post-`9d1177d` misuse-guardrail package from the client side.

The key question was:

`does the standard live wrapper path now preserve a real caller identity, or does it still collapse into generic mcp-agent/public-mcp?`

## Why I narrowed the conclusion

The implementing agent claimed three improvements:

1. caller identity preservation
2. microtask blocking
3. duplicate heavy-turn reuse

In this retest, only the first one produced a fully clean, inspectable live signal.

So I intentionally did **not** generalize beyond the evidence.

## Evidence chain

1. Started a real wrapper request with an explicit session id.
2. Observed accepted/deferred early summary, meaning the request did actually enter the live public-agent path.
3. Read back the persisted session JSON for that exact session id.
4. Inspected `task_intake.context.client`.

The value was still:

1. `name = mcp-agent`
2. `instance = public-mcp`

That is exactly the generic identity the new change was supposed to improve beyond.

## Why this deserves a separate issue

This is not a reason to revert the rest of the guardrail work.

It is a reason to open one smaller, sharper issue:

- the live wrapper path still does not prove richer caller identity persistence end-to-end
