# Advisor Orchestrate Rollback Drill Report (Issue #16)

Date: 2026-02-25  
Branch: `feat/advisor-orchestrate-v1-issue16`

## Drill Objective

Verify that orchestration features can be stopped quickly without breaking legacy advisor execution.

## Drill Levels

### L1: Disable orchestrate at request level

1. Send advisor requests with `orchestrate=false` (default behavior).
2. Verify `/v1/advisor/advise` falls back to single downstream ask job path.
3. Confirm no new `advisor.orchestrate` jobs are enqueued.

Expected outcome: immediate behavior fallback for new traffic.

### L2: Block `advisor.orchestrate` kind at submission point

1. Feature-gate or route policy rejects new `advisor.orchestrate` submissions.
2. Existing runs stay observable via `/v1/advisor/runs/*`.
3. Manual takeover endpoint remains available for degraded runs.

Expected outcome: no new orchestration control jobs, legacy ask path unaffected.

### L3: Version rollback

1. Deploy previous service revision.
2. Confirm DB compatibility (new tables are additive, old paths ignore them).
3. Confirm artifacts compatibility (`advisor_runs` artifacts are sidecar-only).

Expected outcome: service restored without data corruption.

## Drill Acceptance Checklist

1. New orchestration creation can be stopped within 5 minutes.
2. Legacy `/v1/advisor/advise` execute path remains healthy within 30 minutes.
3. Existing run/event artifacts remain readable after rollback.
4. No schema-destructive migration is required.

## Observed Constraints

1. Replay/takeover endpoints are additive; old clients do not depend on them.
2. OpenClaw integration is opt-in (`openclaw_mcp_url`), so rollback surface is limited.
