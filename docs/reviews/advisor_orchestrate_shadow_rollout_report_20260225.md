# Advisor Orchestrate Gray Rollout Report (Issue #16)

Date: 2026-02-25  
Branch: `feat/advisor-orchestrate-v1-issue16`

## Scope

This rollout report covers the v2 advisor orchestration additions:

1. OpenClaw `sessions_spawn/sessions_send/session_status` adapter wiring.
2. Gate engine (`quality + role + evidence`) and retry/degrade behavior.
3. Event replay + snapshot generation (`/v1/advisor/runs/{run_id}/replay`).
4. Manual takeover + compensation flow (`/v1/advisor/runs/{run_id}/takeover`).

## Rollout Strategy

1. Keep `orchestrate=false` default, no behavior change for existing advisor clients.
2. Run shadow validation with `orchestrate=true` on non-prod requests.
3. Require explicit `openclaw_mcp_url` to activate OpenClaw protocol path.
4. Keep `openclaw_required=false` by default to allow soft fallback during gray period.

## Key Observability Signals

1. `/v1/advisor/runs/{run_id}/events` timeline includes gate and takeover events.
2. `artifacts/advisor_runs/<run_id>/snapshot.json` updated on run reconciliation.
3. `gate.failed` followed by retry dispatch is visible via event stream.
4. `run.degraded -> run.taken_over` path is auditable with compensation payload.

## Validation Evidence

Primary test modules:

1. `tests/test_advisor_orchestrate_api.py`
2. `tests/test_advisor_runs_replay.py`
3. `tests/test_openclaw_adapter.py`

Target behaviors covered:

1. Orchestrate child dispatch, event persistence, and completion.
2. Gate failure -> retry -> eventual completion.
3. Gate failure with exhausted retries -> degrade.
4. Manual takeover and replay persistence.
5. OpenClaw required-path failure triggers controlled degrade.

## Residual Risks

1. OpenClaw tool schemas may vary across deployments; adapter uses best-effort pass-through.
2. Gate scoring is deterministic heuristic v1; may need tuning against production answer distributions.
3. Replay currently rebuilds from persisted events and does not reconcile external systems.
