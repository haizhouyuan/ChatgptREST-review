# Launch Hardening Todo v2

**Date**: 2026-03-13
**Branch**: `codex/launch-hardening-20260313`

## Code and Contract

- [x] fix EvoMap executor/savepoint rollback breakage
- [x] fix sandbox merge-back savepoint breakage
- [x] stabilize execution review failure fixture bundle
- [x] refresh MCP tool registry snapshot
- [x] make report redact scan inspect the full draft
- [x] route Google Workspace delivery through effects outbox only
- [x] remove direct Gmail/Docs side effects from report finalize hot path
- [x] unify recall telemetry with shared `TelemetryRecorder`
- [x] add mixed-hit telemetry recording for KB + EvoMap recall
- [x] return `query_id` from `/v1/advisor/recall`
- [x] add `/v1/advisor/recall/feedback`
- [x] mark atoms used when feedback provides atom ids
- [x] make `/v2/cognitive/health` honest when runtime is not initialized
- [x] tighten EvoMap visibility on launch-critical hot paths without breaking explicit graph-query flows
- [x] fix convergence validation runner to follow the selected python env in worktrees

## Regression and Validation

- [x] targeted regression for executor + sandbox savepoint fixes
- [x] targeted regression for report redact/outbox behavior
- [x] targeted regression for recall telemetry + feedback flow
- [x] targeted regression for cognitive health honesty
- [x] targeted regression for convergence validation runner default pytest resolution
- [x] full repository `pytest -q`
- [x] convergence validation required waves green
- [x] business-flow simulation wave green
- [x] fault-injection wave green
- [x] bounded soak wave green
- [x] live wave green by runner acceptance contract

## Documentation and Closeout

- [x] keep original adjudication/todo as `v1`
- [x] write updated adjudication as `v2`
- [ ] write walkthrough for the final hardening tranche
- [ ] run `gitnexus_detect_changes()` before final commit
- [ ] commit final hardening tranche
- [ ] execute closeout workflow + closeout script
