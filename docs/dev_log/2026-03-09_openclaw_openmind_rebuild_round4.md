# OpenClaw/OpenMind Rebuild Round 4

## What changed

- Updated [`scripts/rebuild_openclaw_openmind_stack.py`](/vol1/1000/projects/ChatgptREST/scripts/rebuild_openclaw_openmind_stack.py) to materialize `channels.defaults.heartbeat` as indicator-only:
  - `showOk=false`
  - `showAlerts=false`
  - `useIndicator=true`
- Added regression coverage in [`tests/test_rebuild_openclaw_openmind_stack.py`](/vol1/1000/projects/ChatgptREST/tests/test_rebuild_openclaw_openmind_stack.py) to lock the new heartbeat visibility contract.

## Why

- Managed role agents should use heartbeats for internal upkeep and `sessions_send` back to `main`, not external Feishu alert delivery.
- The live gateway had already been rebuilt with `target: none` heartbeats, but OpenClaw channel heartbeat visibility still defaults to `showAlerts=true`.
- That default caused Feishu delivery attempts to the synthetic `heartbeat` target and failed with Feishu scope `contact:user.employee_id:readonly`.

## Validation

Repo validation:

- `./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py tests/test_install_openclaw_cognitive_plugins.py`
- `./.venv/bin/python -m py_compile scripts/rebuild_openclaw_openmind_stack.py tests/test_rebuild_openclaw_openmind_stack.py`

Live rebuild + runtime validation:

- Re-ran:
  - `./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --openclaw-bin /home/yuanhaizhou/.local/bin/openclaw`
- Rebuilt OpenClaw state with backup root:
  - `/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw.migration-backup-20260308T171922Z`
- Verified:
  - `openclaw channels status --probe` -> `Feishu default/research: works`
  - `openclaw agent --agent main ... openmind_memory_status ...` -> `READY`
  - `main -> maintagent` via `sessions_spawn` + child `sessions_send` announce-back works
  - gateway delivery queue emptied after recovery

## Live config changes outside git

- Added `OPENMIND_RATE_LIMIT=120` to:
  - `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env`
- Restarted:
  - `chatgptrest-api.service`
  - `openclaw-gateway.service`
- Reinstalled gateway systemd unit via official CLI on non-nvm Node:
  - `openclaw gateway install --force --runtime node --port 18789 --token <existing-token>`
- Result:
  - `openclaw gateway status --json` now reports `configAudit.ok=true`
  - service command now points to `/usr/local/lib/nodejs/node-v22.12.0-linux-x64/bin/node`

## Residual notes

- Feishu startup probe still has an upstream 10s timeout quirk; transient `bot info probe timed out after 10000ms` can appear during startup even when `channels status --probe` later turns green.
- One pre-existing pending delivery was recovered once after service reinstall. After recovery, `delivery-queue/` returned to empty and no new post-fix `feishu:heartbeat` entries were generated from the managed config.
