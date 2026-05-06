## Decision

This branch is the clean extraction of the **useful, mergeable** team-control-plane portion that PR `#178` was aiming for.

The original intent of `#178` is now implemented on top of current `origin/master` with the three blocking gaps closed:

1. checkpoint approval/rejection no longer finalizes a parent run while other checkpoints remain pending
2. `topology_id` now meaningfully overlays explicit `team` payloads instead of being silently ignored
3. `max_concurrent` is now enforced during parallel team fan-out instead of remaining dead config

## Independent Adjudication

### What Was Worth Keeping From `#178`

- persistent team runtime state in SQLite
- topology / gate / role catalog wiring
- advisor v3 team-control routes
- native team dispatch runtime with role fan-out, digest, and manual checkpoints

### What Was Wrong In The Original Form

- run closure semantics were incorrect for multi-checkpoint runs
- public route contract for `topology_id + team` was only partially implemented
- topology concurrency caps were declared but not enforced
- PR hygiene was poor, so it could not be merged directly

### Why This Clean Branch Is Mergeable

- the feature commit was rebased onto current `origin/master`
- the three functional blockers were fixed with dedicated regression tests
- the full-repo test run is green
- the only additional fix discovered during full-repo validation was a test-isolation issue in the new team-control route test helper; no production runtime code required follow-up changes

## Impact / Risk Summary

GitNexus MCP is still stale in this main session, so impact analysis was performed via GitNexus CLI and a fresh agent check.

- `resolve_team_spec`: high-contract surface / critical blast radius, so the overlay fix was kept minimal and additive
- `dispatch_team`, `_run_team_roles`, `_resolve_checkpoint`: low-risk, localized changes with direct regression coverage
- final change-scope check for the last follow-up commit showed only:
  - `tests/test_routes_advisor_v3_team_control.py::_make_client`
  - no production runtime symbol changes

## Final Judgment

This branch closes the meaningful, product-facing remainder of `#178`.

It is appropriate to open and merge as a clean replacement for the team runtime portion, while continuing to treat the original `#178` as superseded/no-longer-mergeable.
