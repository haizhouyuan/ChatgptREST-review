## Summary

This tranche fixes service-mode coding executor discovery for the planning coding-agent lane.

The concrete failure was reproduced on the formal OpenClaw session `openclaw-real-closure-card-session-dc004183` for task `impl_9150013ffdb8`: the planning control plane correctly selected `coding_agent`, but the formal API process reported all coding executors as `ready=false` because the systemd user service PATH did not include user-local CLI locations.

## What Changed

- `chatgptrest/controller/coding_agent_executor.py`
  - Added executor-specific env override resolution.
  - Added service-safe candidate search across common user-local install paths:
    - `~/.local/bin`
    - `~/local/node/bin`
    - `~/.nvm/versions/node/*/bin`
  - Switched public executor readiness and final executor resolution to use the same resolved command path.
- `tests/test_coding_agent_executor.py`
  - Added regression for resolving `codex2` from `~/.local/bin` when PATH is empty.
  - Added regression for resolving `claudeminmax` from `CC_CLI`.

## Why

The formal product path is `Feishu/OpenClaw -> openmind_advisor_ask -> /v3/agent/turn -> planning coding-agent lane`.

If the API service cannot discover installed coding executors under its reduced PATH, the user sees `needs_followup + select_executor` even when the host already has usable executors installed. That is a product blocker at the formal entrypoint, not just a local shell mismatch.

## Verification

- `python3 -m py_compile chatgptrest/controller/coding_agent_executor.py`
- `./.venv/bin/pytest -q tests/test_coding_agent_executor.py tests/test_controller_engine_planning_pack.py tests/test_routes_agent_v3.py`
- Service-like environment probe:
  - `HOME=/home/yuanhaizhou`
  - `PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`
  - Result: `codex`, `codex2`, `claudeminmax`, `claudegac` all resolved `ready=true`

## Runtime Result

After restarting `chatgptrest-api.service`, the same formal OpenClaw task continuation no longer failed on executor discovery.

- Formal session: `openclaw-real-closure-card-session-dc004183`
- Task: `impl_9150013ffdb8`
- Execution layer projected:
  - `execution_lane=coding_agent`
  - `selected_executor=codex`
  - `executor_ready=true`

The remaining blocker moved forward to the executor runtime itself:

- artifact: `artifacts/controller_coding_agent/353fc29b294e48f1bba44b09c4b1366b/result.json`
- failure: Codex refresh token already used / re-login required

That is the expected next-layer blocker. Executor discovery is no longer the limiting factor on the formal product path.
