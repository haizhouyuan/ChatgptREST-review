# OpenClaw Finbot Deploy Fix Walkthrough v1

## What happened

After pushing the `finbot` automation lane to `master`, the first live rebuild wrote an invalid OpenClaw config:

- `agents.list[].sandbox.workspaceAccess = "full"`

The installed OpenClaw build only accepts:

- `none`
- `ro`
- `rw`

That meant the code was merged, but `finbot` was not actually deployable until the sandbox vocabulary was corrected.

## Fix

Updated:

- `scripts/rebuild_openclaw_openmind_stack.py`

Change:

- `finbot.sandbox.workspaceAccess: "full" -> "rw"`

## Why this is the right fix

`finbot` needs write access inside its own workspace because it writes inbox artifacts and runs deterministic helper scripts.
The closest valid OpenClaw setting is therefore `rw`, not `none` or `ro`.

## Validation plan

1. Rebuild `~/.openclaw` with topology `ops`
2. Run `verify_openclaw_openmind_stack.py --expected-topology ops`
3. Run:
   - `python3 ops/openclaw_finbot.py dashboard-refresh --format json`
   - `python3 ops/openclaw_finbot.py watchlist-scout --format json`
4. Confirm `~/.openclaw/agents/finbot/` exists and `openclaw sandbox explain --agent finbot --json` succeeds

## Note

GitNexus impact/detect_changes MCP calls still timed out at 120s during this fix, so validation relies on targeted regression plus live rebuild/verify.
