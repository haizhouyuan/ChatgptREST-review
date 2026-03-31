# 2026-03-25 Public Agent Wrapper Live Retest Findings Walkthrough v1

## What I tested

I validated the live wrapper fixes after `74dc247` / `75ff09d` from the client side.

The target client was:

- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

The target surface was:

- `http://127.0.0.1:18712/mcp`

## Test slices

1. Re-ran the old `ISSUE-0020` timeout-mismatch scenario.
2. Re-ran valid live ChatGPT public-repo request.
3. Re-ran valid live Gemini imported-code code-review request.
4. Re-ran a simple sync planning scenario to probe the residual note mentioned in service-side closeout.

## Why I split the outcome

I did not collapse all observations into one verdict because the fixes landed unevenly:

1. preflight error classification is now correct
2. deferred early handoff is now materially better
3. a new sync-path summary bug appears to exist

That is exactly the kind of case where separate issue tracking matters. Otherwise the service team would read “still broken” and miss that two previously real problems are now actually fixed.

## Why ISSUE-0022 is new instead of reopening ISSUE-0021

`ISSUE-0021` was about the live wrapper path lacking crisp accepted-state observability in general.

After the fix, the deferred ChatGPT and Gemini repo-review paths now do provide that accepted-state handoff:

1. early summary exists
2. session_id is present
3. delivery/lifecycle/provider-selection are present

The newly observed problem is narrower:

1. a sync planning path writes an initialize-only summary
2. that summary remains misleading while the process is still running

That is a different failure mode and should stay separately traceable.
