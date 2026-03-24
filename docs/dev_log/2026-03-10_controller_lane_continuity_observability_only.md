# 2026-03-10 Controller Lane Continuity: observability-only

## Why

The original continuity service unit ran:

```bash
controller_lane_continuity.py sweep --restart
```

That assumed `launch_cmd` / `resume_cmd` could reliably restart Codex lanes.
Live verification showed the assumption was false:

- the lane registry was empty in production
- the timer was sweeping an empty fleet
- `codex exec ... - </dev/null` exits immediately with `No prompt provided via stdin`
- `codex exec resume --last --cd ...` does not match the continuity session model

So the continuity layer is kept, but downgraded to `observability-first`.

## Change

- `ops/systemd/chatgptrest-controller-lanes.service`
  - `sweep --restart` -> `sweep`

This keeps:

- lane registry
- heartbeat / report
- stale detection
- digest generation

And explicitly stops pretending that automatic lane restart is production-ready.

## Next

- register real lanes for observability only
- keep `launch_cmd` / `resume_cmd` optional
- revisit restart only after a real lane wrapper exists
