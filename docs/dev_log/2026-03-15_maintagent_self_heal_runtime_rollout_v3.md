## Scope

This follow-up fixed a production regression discovered immediately after the runtime-worktree rollout:

- `chatgptrest-maint-daemon.service` switched onto the clean merged checkout
- systemd watchdog then started killing it every 30 seconds

The root cause was not systemd configuration. The clean branch's `ops/maint_daemon.py` still defined `_kick_watchdog()` but no longer drove any heartbeat loop.

## Root Cause

The dirty primary checkout had a newer watchdog implementation:

- `_systemd_notify(...)`
- `_start_watchdog_heartbeat(...)`
- `_stop_watchdog_heartbeat(...)`

The merged runtime branch was missing that logic. As long as maintagent ran from the dirty checkout this stayed hidden. Once deployment was corrected, the regression became live-visible immediately.

## Change

Updated:

- `ops/maint_daemon.py`

to restore the watchdog heartbeat path:

- best-effort systemd notify via `NOTIFY_SOCKET`
- daemon heartbeat thread every 5 seconds
- `READY=1` notification on boot
- clean shutdown of the heartbeat thread on process exit
- `_kick_watchdog(status=...)` compatibility for tests and ad hoc callers

Added:

- `tests/test_maint_daemon_stuck_watchdog.py`

to cover:

- direct watchdog kick payload generation
- heartbeat bootstrap behavior and thread reuse

## Validation

Targeted regression suite:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_maint_daemon_stuck_watchdog.py \
  tests/test_sre_fix_request.py \
  tests/test_repair_autofix_codex_fallback.py \
  tests/test_issue_targets.py \
  tests/test_maint_bootstrap_memory.py
```

Expected result:

- `19 passed`

## Why This Matters

Without this fix, maintagent could look correctly configured for self-heal while being continuously restarted by systemd, which destroys its ability to:

- accumulate diagnosis context
- submit guarded repairs reliably
- keep issue/incident state coherent

This restores the maint side of the self-heal loop after the runtime deployment was made consistent.
