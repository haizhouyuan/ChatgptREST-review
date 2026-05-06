# 2026-03-10 Controller Lane Continuity v0.1

## Why

The current local development workflow has a real continuity gap:

- the main controller is a human-facing Codex session
- auxiliary Codex / Claude lanes can finish a chunk and exit
- there is no durable lane state, no shared heartbeat, and no automatic restart

That forces the human to keep watching windows and manually relaunch lanes.

## What was implemented

Added a narrow operational continuity layer:

- `ops/controller_lane_continuity.py`
  - SQLite-backed lane registry
  - heartbeat and final-report updates
  - stale detection
  - optional auto-restart using stored launch/resume commands
  - text digest for the controller

- `tests/test_controller_lane_continuity.py`
  - register / status roundtrip
  - heartbeat updates
  - completed lanes do not restart
  - stale `idle` lane restarts with `launch_cmd`
  - stale restarted lane uses `resume_cmd`
  - digest highlights checkpoint attention

- `docs/ops/controller_lane_continuity_v0_1.md`
  - operator guide and systemd usage

- `ops/systemd/chatgptrest-controller-lanes.service`
- `ops/systemd/chatgptrest-controller-lanes.timer`
  - optional periodic `sweep --restart`
  - follow-up fix: use `OnUnitInactiveSec=2min` for the oneshot service, so the timer keeps scheduling instead of elapsing once

## Design choices

- Did **not** build a general agent teams platform.
- Kept one controller and subordinate lanes.
- Used a durable SQLite registry instead of in-memory state.
- Treated `needs_gate` / `checkpoint_pending` as stop conditions for restart.
- Kept launch/resume commands generic so Codex, Claude, or shell lanes can all use the same continuity layer.

## What this intentionally does not solve

- cross-lane semantic coherence
- automatic task planning
- role-aware routing
- product-side agent collaboration

This is only the continuity substrate for the local dev team.
