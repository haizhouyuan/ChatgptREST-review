# 2026-03-27 Wrapper Low-Level Governance Lockdown Walkthrough v1

## What was done

This slice closed the remaining live low-level ask governance gap for wrapper identities.

Before this change:

- maintenance/internal identities were already HMAC-scoped
- `planning-wrapper`, `openclaw-wrapper`, and `advisor-automation` still represented the last automation identities that could plausibly touch low-level ask without the same hard-auth standard

After this change:

- `planning-wrapper` is HMAC-only and runtime-limited
- `openclaw-wrapper` is public-agent-only
- `advisor-automation` is internal-runtime-only

## Why this shape

The goal was not "every wrapper gets HMAC and keeps its current privileges."

The goal was:

- shrink low-level ask surface area first
- keep only one narrowly justified automation low-level lane
- require strong auth on that remaining lane
- enforce runtime containment at ingress

That is why:

- planning stayed, but got HMAC + concurrency + dedupe
- openclaw did not get a new low-level lane; it got removed from that surface
- advisor-automation stayed available only as an internal runtime label, not as an external `/v1/jobs` identity

## Files changed

Core enforcement:

- [chatgptrest/core/ask_guard.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/ask_guard.py)
- [chatgptrest/api/routes_jobs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_jobs.py)
- [ops/policies/ask_client_registry.json](/vol1/1000/projects/ChatgptREST/ops/policies/ask_client_registry.json)

Tests:

- [tests/test_low_level_ask_guard.py](/vol1/1000/projects/ChatgptREST/tests/test_low_level_ask_guard.py)
- [tests/test_jobs_write_guards.py](/vol1/1000/projects/ChatgptREST/tests/test_jobs_write_guards.py)

Operator/live verification:

- [ops/run_low_level_ask_live_smoke.py](/vol1/1000/projects/ChatgptREST/ops/run_low_level_ask_live_smoke.py)

Contract/docs sync:

- [README.md](/vol1/1000/projects/ChatgptREST/README.md)
- [docs/contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/contract_v1.md)
- [docs/runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md)
- [docs/client_projects_registry.md](/vol1/1000/projects/ChatgptREST/docs/client_projects_registry.md)
- [planning/docs/chatgptREST.md](/vol1/1000/projects/planning/docs/chatgptREST.md)
- [planning/AGENTS.md](/vol1/1000/projects/planning/AGENTS.md)
- [openclaw/docs/chatgptREST.md](/vol1/1000/projects/openclaw/docs/chatgptREST.md)
- [openclaw/AGENTS.md](/vol1/1000/projects/openclaw/AGENTS.md)

## Validation outcomes

Repo-level validation target:

- unsigned planning low-level ask fails auth
- signed planning substantive review succeeds
- immediate duplicate signed planning review is rejected
- openclaw low-level ask is rejected
- advisor alias low-level ask is rejected

Live validation target:

- unsigned maintenance HMAC callers fail
- signed maintenance HMAC callers succeed
- signed planning wrapper follows the expected allow/block matrix
- openclaw/advisor low-level probes fail closed

## Residual

This slice intentionally does not grant new low-level permissions to additional wrappers.

Remaining future decision, if ever needed:

- whether any new automation wrapper should be approved for low-level ask at all

The default answer after this lockdown should be "no, use public advisor-agent MCP" unless a narrow, explicit low-level lane is justified and HMAC-scoped from day one.
