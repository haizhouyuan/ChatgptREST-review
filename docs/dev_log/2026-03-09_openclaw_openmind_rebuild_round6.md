# 2026-03-09 OpenClaw/OpenMind Rebuild Round 6

## Summary

- Fixed Codex auth synchronization so the rebuild script updates every existing agent auth store that already contains an `openai-codex` profile, not just the small set of currently managed role agents.
- Rebuilt the live OpenClaw state after stopping the gateway, which resynchronized stale OAuth material across all historical agent dirs.
- Verified that `main` and `openclaw-orch` recovered real `openai-codex/gpt-5.4` execution and no longer emitted `refresh_token_reused`.

## Root Cause

The previous rebuild flow only synchronized Codex OAuth credentials for agents whose configured primary model matched `openai-codex/*`.

That left a large number of existing agent auth stores stale, including historical lanes and some still-active agents. The live state had split into two populations:

- fresh stores carrying the current token set
- stale stores carrying an older refresh token that OpenAI now rejects with `refresh_token_reused`

Most importantly, `main` had drifted back to the stale token set even though `openclaw-orch` already carried the fresh token set.

This was not a platform limitation. It was a local auth-material synchronization gap.

## Code Changes

### `scripts/rebuild_openclaw_openmind_stack.py`

`sync_codex_auth_profiles(...)` now:

- keeps the explicit target list
- scans `state_dir/agents/*/agent/auth-profiles.json`
- auto-includes any agent that already has a stored `provider == "openai-codex"` profile
- rewrites all of those stores to the canonical `~/.codex/auth.json` token set

This makes the rebuild idempotent across historical agent dirs instead of silently leaving stale Codex profiles behind.

### `tests/test_rebuild_openclaw_openmind_stack.py`

Expanded the Codex auth sync regression so that:

- explicit target `main` is still updated
- a sibling agent with an existing Codex profile is auto-discovered and updated too

That locks in the real failure mode that was observed on the live system.

## Validation

### Code-level

Passed:

```bash
./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py
./.venv/bin/python -m py_compile scripts/rebuild_openclaw_openmind_stack.py tests/test_rebuild_openclaw_openmind_stack.py
```

### Live recovery procedure

Executed:

```bash
systemctl --user stop openclaw-gateway.service
./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --openclaw-bin /home/yuanhaizhou/.local/bin/openclaw
systemctl --user start openclaw-gateway.service
systemctl --user start chatgptrest-api.service
```

Observed rebuild output:

- `synced_codex_auth_agents` now includes all existing agent dirs with stored Codex OAuth profiles, not just `main` and `openclaw-orch`

Post-rebuild auth inventory confirmed:

- all existing `openai-codex:default` stores now share the same access token hash and expiry

### Live agent probes

Successful probes after restart:

```bash
openclaw agent --agent planning --message 'Reply ONLY READY.' --json --timeout 180
openclaw agent --agent main --message 'Reply ONLY READY.' --json --timeout 180
openclaw agent --agent openclaw-orch --message 'Reply ONLY READY.' --json --timeout 180
```

Results:

- `planning` returned `READY.`
- `main` returned `READY` using provider `openai-codex`, model `gpt-5.4`
- `openclaw-orch` returned `READY` using provider `openai-codex`, model `gpt-5.4`

Gateway journal after restart showed:

- no new `refresh_token_reused`
- successful `ws ⇄ res ✓ agent` completions for the repaired lanes
- expected `adopted newer OAuth credentials from main agent` log entries for child lanes inheriting the repaired main store

## Remaining Notes

- `openclaw channels status --probe` now reaches the gateway again, but the standalone CLI still emits plugin provenance and dependency warnings for some global plugin paths. The gateway service itself is healthy and continues to register the OpenMind and Feishu/DingTalk tools.
- `maintagent` and `research-orch` still deserve a separate focused runtime pass because their skill/bootstrap mix can trigger longer-running behaviors than the minimal READY probes used here.
