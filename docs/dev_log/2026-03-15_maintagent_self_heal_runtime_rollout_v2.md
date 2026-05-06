## Scope

This follow-up fixed a deployment alignment bug discovered after PR #189 merged:

- `chatgptrest-worker-send.service`
- `chatgptrest-worker-wait.service`
- `chatgptrest-worker-repair.service`

were already running from the clean runtime worktree, but:

- `chatgptrest-maint-daemon.service`

was still running from the dirty primary repo checkout because the self-heal enablement script only replaced `ExecStart` and did not override `WorkingDirectory` or `PYTHONPATH`.

That meant the maintagent diagnosis and autofix path was not guaranteed to run the same code as the workers.

## Root Cause

The operator entrypoint:

- `ops/systemd/enable_maint_self_heal.sh`

generated:

- `~/.config/systemd/user/chatgptrest-maint-daemon.service.d/30-self-heal.conf`

with a new `ExecStart`, but left the service's existing runtime path untouched. In this environment, the inherited working directory and import path still pointed at `/vol1/1000/projects/ChatgptREST`, which currently sits on a different dirty branch.

## Change

Updated:

- `ops/systemd/enable_maint_self_heal.sh`

to write:

- `WorkingDirectory=${ROOT_DIR}`
- `Environment=PYTHONPATH=${ROOT_DIR}`

into the generated self-heal drop-in. `ROOT_DIR` is the checkout from which the operator ran the script, so maintagent now follows the same rollout artifact as the worker services.

## Live Validation

After rerunning:

```bash
cd /vol1/1000/projects/ChatgptREST/.worktrees/runtime-feature-memory
ops/systemd/enable_maint_self_heal.sh
```

the live service should show:

- `chatgptrest-maint-daemon.service WorkingDirectory=/vol1/1000/projects/ChatgptREST/.worktrees/runtime-feature-memory`
- `PYTHONPATH=/vol1/1000/projects/ChatgptREST/.worktrees/runtime-feature-memory`

This brings `maint_daemon`, `send`, `wait`, and `repair` onto the same merged codebase while still sharing the canonical DB and artifacts directory under `/vol1/1000/projects/ChatgptREST`.

## Why This Matters

Without this fix, maintagent memory loading, issue targeting, SRE routing, and guarded autofix could diverge from the worker behavior. The system would appear "enabled" while still operating as a split-brain deployment.

This change closes that gap and makes the self-heal rollout reproducible instead of relying on hand-edited local overrides.
