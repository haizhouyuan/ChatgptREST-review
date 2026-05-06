# 2026-03-11 Production Readiness Fix TODO v1

## Goal

Drive the ChatgptREST + OpenClaw stack from current `No-Go` to a state that can pass:

- clean restart
- protected production auth
- stable live verifier
- consistent identity/provenance
- reduced public/control-plane exposure

## P0

- Unify auth contract across ChatgptREST v1, OpenMind v2, OpenClaw plugins, and guardian.
- Fix `/v2/advisor/ask` idempotency isolation so it cannot collide across sessions/users/contexts.
- Make `GET /v1/advisor/runs/{run_id}` read-only and move reconcile/retry behavior to explicit write paths.
- Re-stabilize the OpenClaw/OpenMind live verifier until the 2026-03-11 regressions are cleared.
- Close the OpenClaw memory identity gap by propagating `sessionId` and `agentAccountId` through hook context.
- Ensure current OpenClaw runtime config is valid against current schema and survives clean restart.

## P1

- Narrow public `/v2/advisor/*` exposure and separate internal `cc-*` control-plane endpoints.
- Restrict `openclaw_mcp_url` to approved local targets.
- Strengthen health/readiness so API green means chain green.
- Remove silent/fail-open behavior for required plugin/service/hook initialization paths.
- Fix `openmind-advisor` `advise` mode so it forwards real session/user/context.
- Stop leaking traceback text on `advisor_ask` failures.

## P2

- Replace in-memory-only v2 rate limiting with deployable/shared strategy or explicitly constrain deployment mode.
- Replace in-memory-only advisor trace store with durable backing.
- Remove runbook/systemd drift and hardcoded host paths.
- Improve plugin packaging/integrity story and runtime contract tests.
- Move runtime secrets out of plaintext config and onto an explicit secret-loading path.

## Repo Split

### ChatgptREST

- Auth unification and guard behavior
- Advisor API/idempotency/read-only semantics
- Health/readiness
- Public surface reduction
- Verifier expectations and regression coverage

### OpenClaw

- Hook context identity propagation
- Plugin HTTP auth/ordering hardening
- Plugin fail-open behavior
- Config schema/runtime compatibility
- Secret handling and runtime config hygiene

## Execution Order

1. Fix auth and idempotency first.
2. Fix read-side effects and readiness semantics.
3. Fix OpenClaw identity propagation and runtime config compatibility.
4. Rerun targeted tests.
5. Rerun live verifier.
6. Only then cut PR(s).
