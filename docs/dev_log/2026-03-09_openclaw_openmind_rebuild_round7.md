# 2026-03-09 OpenClaw/OpenMind Rebuild Round 7

## Summary

- Added two missing rebuild behaviors: prune unmanaged legacy OpenClaw agent dirs, and prune unmanaged cron jobs that still reference retired agents.
- Hardened `maintagent` bootstrap/heartbeat guidance so localhost health checks use `exec` + `curl` instead of `web_fetch`.
- Rebuilt the live OpenClaw state again, which removed stale historical agent lanes that were still competing for Codex OAuth and dragging old cron definitions forward.

## Why This Round Was Needed

Round 6 fixed Codex auth sync, but the live OpenClaw state still contained a large amount of historical agent state:

- legacy agent dirs under `~/.openclaw/agents/*`
- legacy cron jobs under `~/.openclaw/cron/jobs.json`
- stale role lanes such as `chatgptrest-guardian`, `pm`, `hragent`, and old worker agents

Those lanes were no longer part of the intended five-agent topology, but they still existed in the live state and could continue to:

- wake background work
- retain old auth stores
- trigger refresh-token reuse or unrelated runtime drift

At the same time, `maintagent` had previously attempted local health checks with `web_fetch http://127.0.0.1:18711/health`, which is the wrong tool for localhost probing.

## Code Changes

### `scripts/rebuild_openclaw_openmind_stack.py`

Added:

- `prune_unmanaged_agent_dirs(...)`
  - moves any agent dir not in the managed five-agent set into the rebuild backup under `unmanaged_agents/`
- `prune_unmanaged_cron_jobs(...)`
  - rewrites `cron/jobs.json` to keep only jobs owned by currently managed agents

Updated `main()` to:

- compute the managed agent-id set
- prune legacy agent dirs before rewriting state
- prune legacy cron jobs before printing the rebuild summary
- include `pruned_agent_dirs` and `pruned_cron_jobs` in the JSON result

Also tightened `maintagent` prompt material in:

- role heartbeat prompt
- `HEARTBEAT.md`
- `TOOLS.md`
- `AGENTS.md`

The new rule is explicit:

- localhost / private-network health endpoints must be checked via shell `exec` and `curl`
- `web_fetch` should not be used for local health probes

### `tests/test_rebuild_openclaw_openmind_stack.py`

Added regression coverage for:

- pruning unmanaged legacy agent dirs into backup storage
- pruning unmanaged cron jobs owned by retired agents
- keeping the new localhost `exec/curl` guidance materialized in the managed `maintagent` workspace files

## Validation

### Code-level

Passed:

```bash
./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py
./.venv/bin/python -m py_compile scripts/rebuild_openclaw_openmind_stack.py tests/test_rebuild_openclaw_openmind_stack.py
```

### Live rebuild

Executed:

```bash
systemctl --user stop openclaw-gateway.service
./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --openclaw-bin /home/yuanhaizhou/.local/bin/openclaw
systemctl --user start openclaw-gateway.service
systemctl --user start chatgptrest-api.service
```

Observed rebuild output included:

- `pruned_agent_dirs`
- `pruned_cron_jobs`
- `synced_codex_auth_agents`

Legacy state moved out of the active OpenClaw tree included retired agents such as:

- `chatgptrest-guardian`
- `chatgptrest-orch`
- `chatgptrest-codex-w1`
- `chatgptrest-codex-w2`
- `chatgptrest-codex-w3`
- `pm`
- `hragent`

Legacy cron jobs removed from active state included:

- `pm` hourly job
- `hragent` governance/quota jobs

Post-rebuild live state confirmed:

- `~/.openclaw/openclaw.json` now lists only:
  - `main`
  - `planning`
  - `research-orch`
  - `openclaw-orch`
  - `maintagent`
- `~/.openclaw/agents/` now contains only those five managed agent dirs
- `~/.openclaw/cron/jobs.json` no longer references retired agent ids

### Live probes

Successful probes after restart:

```bash
openclaw agent --agent planning --message 'Reply ONLY READY.' --json --timeout 180
openclaw agent --agent main --message 'Reply ONLY READY.' --json --timeout 180
openclaw agent --agent openclaw-orch --message 'Reply ONLY READY.' --json --timeout 180
```

Observed results:

- `planning` returned `READY.`
- `main` returned `READY` using `openai-codex/gpt-5.4`
- `openclaw-orch` returned `READY` using `openai-codex/gpt-5.4`

Gateway journal after the prune rebuild showed:

- no new `refresh_token_reused`
- OpenMind plugins registering successfully
- Feishu tools registering successfully
- the earlier `refresh_token_reused` entries were pre-prune historical failures, not post-prune regressions

### `maintagent` note

The default probe:

```bash
openclaw agent --agent maintagent --message 'Reply ONLY READY.' --json --timeout 60
```

collided with the existing persistent `maintagent` session and produced a session-file lock timeout.

That is a session-topology issue, not a fresh auth or plugin regression:

- `maintagent` is a persistent watchdog lane with scheduled heartbeat behavior
- probing it without an explicit session id reuses the same durable session
- if the watchdog session is already active, a foreground probe can contend on the same JSONL lock

For focused validation of `maintagent`, use an explicit isolated session id instead of the default durable lane.

## Current Assessment

This round meaningfully improved the live topology:

- the active OpenClaw state is now aligned with the intended five-agent design
- stale background agent state no longer remains in the live tree
- Codex auth recovery is no longer immediately undermined by retired historical lanes

The remaining issues are narrower:

- CLI/global plugin provenance warnings from root-level legacy install paths are still noisy
- `maintagent` validation should use isolated probe sessions instead of the default durable session

Neither of those invalidates the core rebuild result from this round.
