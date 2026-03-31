# 2026-03-31 Public Agent Manual-Repair Cooldown Projection Fix v1

## Background

During the external harness-review workflow, a structured `report_grade` public advisor-agent turn stayed on:

- `session.status = running`
- `next_action = await_job_completion`

even though the underlying child `chatgpt_web.ask` job had already become:

- `status = cooldown`
- `phase = send`
- `conversation_url = null`
- `error_type = Blocked`
- `error = driver blocked: cloudflare`

That combination means the request never entered a browser-visible ChatGPT conversation. Waiting on the public session was therefore misleading: the job needed human/browser repair, not more polling.

## Root Cause

The public facade already folded stale child jobs into `needs_followup` when the child reached:

- `blocked`
- `needs_followup`
- other explicit terminal-like statuses

but it still mapped every `cooldown` to public `running`.

That was acceptable for retryable background cooldowns, but wrong for **send-phase verification cooldowns** where:

- no `conversation_url` exists
- the driver is blocked by Cloudflare / verification / captcha
- the correct operator action is `same_session_repair`

So the mismatch was:

1. jobs contract: correctly says `cooldown + blocked-by-verification`
2. public session facade: still says `running`
3. MCP wait/watch: keeps waiting because session never surfaces a repair state
4. browser: shows no harness conversation, because none was ever created

## Fix

Changed `chatgptrest/api/routes_agent_v3.py` to add a public projection layer for job snapshots:

- preserve generic `cooldown -> running`
- but project **manual-repair cooldowns** as:
  - `agent_status = needs_followup`
  - `next_action.type = same_session_repair`

Projection rule is intentionally narrow:

- `job_status == cooldown`
- `phase == send`
- `conversation_url` is empty
- and the blocker looks like verification/captcha/Cloudflare (`last_error_type=Blocked` or matching error markers)

This projection is now used by:

- `_job_snapshot()`
- `_controller_snapshot()`
- `get_session` / stream refresh path

## Validation

### Targeted tests

Passed:

```bash
cd /vol1/1000/projects/ChatgptREST
./.venv/bin/pytest -q tests/test_bi14_fault_handling.py tests/test_routes_agent_v3.py -k 'cooldown or same_session_repair or stale'
```

### Added coverage

- generic `cooldown` mapping still stays `running`
- send-phase blocked cooldown projects to `needs_followup + same_session_repair`
- stale controller snapshot now promotes this cooldown class correctly during `get_session`

## Operational Result

After API reload, previously misleading harness-review sessions should no longer appear as indefinitely `running` when the real child job is a send-phase verification cooldown.

Instead, operators and MCP clients see:

- `status = needs_followup`
- `recommended_client_action = patch_same_session`
- `next_action.type = same_session_repair`

which matches the real recovery path.
