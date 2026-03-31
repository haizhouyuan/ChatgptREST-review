## Summary

Merged the `feat/public-advisor-agent-facade` branch into the runtime branch, fixed one live MCP regression, restarted the API/MCP services, and verified that the public surface is now the small agent-only surface.

Runtime branch commits for this rollout:

- `085baf6` `merge: bring public advisor agent facade into runtime branch`
- `9f5b274` `fix(mcp): bind public agent server to runtime port`

## What Changed

The merge brought in the public advisor-agent surface:

- `/v3/agent/turn`
- `/v3/agent/session/{session_id}`
- `/v3/agent/session/{session_id}/stream`
- `/v1/cc-sessions/*`
- public MCP entrypoint with only:
  - `advisor_agent_turn`
  - `advisor_agent_cancel`
  - `advisor_agent_status`
- explicit admin MCP entrypoint preserving the legacy broad tool surface
- OpenClaw `openmind-advisor` convergence to `/v3/agent/turn`
- thought-guard default changes and deferred streaming support

## cc-sessiond Validation

Before the merge, I ran a real `cc-sessiond` validation task against the feature worktree using the official Claude Code SDK backend routed through MiniMax.

- cc-sessiond session id: `2664c6f31d00`
- Claude session id: `40b4a800-45ab-4336-a941-a047d585066c`
- artifacts dir: `/tmp/cc-sessiond-agent-merge-validation`

Prompt scope:

- read-only merge-readiness validation
- verify public MCP cutover
- verify deferred `/v3/agent` streaming
- verify thought-guard defaults
- run the focused agent/MCP regression tests

Observed result:

- Claude ran the requested test suites successfully
- Claude consumed the full turn budget and did not emit the final JSON payload
- the only notable late-stage observation was a non-blocking import probe mistake on `routes_agent_v3.py` where it expected a module-level `router` export

This was treated as supporting evidence only; final acceptance was based on direct local regression and live service verification.

## Pre-merge Safety Check

I created a disposable integration worktree from the runtime branch and performed a no-commit merge of `feat/public-advisor-agent-facade`.

Result:

- merge was clean
- no conflicts

I then ran the post-merge regression gate in the disposable worktree using the shared project virtualenv:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_thought_guard_require_thought_for.py \
  tests/test_routes_agent_v3.py \
  tests/test_agent_mcp.py \
  tests/test_agent_v3_routes.py \
  tests/test_bi14_fault_handling.py \
  tests/test_mcp_server_entrypoints.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_skill_chatgptrest_call.py \
  tests/test_cli_improvements.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_routes_advisor_v3_security.py
```

Both groups passed.

## Live Regression After Merge

After the real merge into `feature/system-optimization-20260316`, I reran the focused suites in the main repo:

```bash
./.venv/bin/pytest -q \
  tests/test_thought_guard_require_thought_for.py \
  tests/test_routes_agent_v3.py \
  tests/test_agent_mcp.py \
  tests/test_agent_v3_routes.py \
  tests/test_bi14_fault_handling.py \
  tests/test_mcp_server_entrypoints.py

./.venv/bin/pytest -q \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_skill_chatgptrest_call.py \
  tests/test_cli_improvements.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_routes_advisor_v3_security.py \
  tests/test_cc_sessiond.py \
  tests/test_cc_sessiond_routes.py \
  tests/test_api_startup_smoke.py
```

Both groups passed.

## Live MCP Regression And Fix

During the first restart, the public MCP server failed to bind `127.0.0.1:18712` and instead fell back to FastMCP's default port `8000`.

Root cause:

- `chatgptrest.mcp.server` explicitly injects `host/port` into `FastMCP`
- the new `chatgptrest.mcp.agent_mcp` did not
- the service still set `FASTMCP_HOST/FASTMCP_PORT`, but the public agent MCP object ignored them

Fix:

- added `_fastmcp_host_port()` to `chatgptrest/mcp/agent_mcp.py`
- instantiated `FastMCP(..., host=_HOST, port=_PORT, stateless_http=True)`
- added regression coverage in `tests/test_agent_mcp.py`

Verification:

```bash
./.venv/bin/pytest -q tests/test_agent_mcp.py tests/test_mcp_server_entrypoints.py
```

Passed.

## Service Restart

Restarted:

- `chatgptrest-api.service`
- `chatgptrest-mcp.service`

I also updated the user-level drop-in:

- `/home/yuanhaizhou/.config/systemd/user/chatgptrest-api.service.d/20-runtime-worktree.conf`

Change:

- moved `WorkingDirectory`, `PYTHONPATH`, `CHATGPTREST_DB_PATH`, and `CHATGPTREST_ARTIFACTS_DIR` back to `/vol1/1000/projects/ChatgptREST`

Reason:

- after the merge, the runtime no longer needed to depend on the feature worktree path
- this makes the live API and live MCP run from the same merged main repo checkout

## Live Verification

API route inventory:

```json
{
  "/v3/agent/turn": true,
  "/v3/agent/session/{session_id}": true,
  "/v3/agent/session/{session_id}/stream": true,
  "/v1/cc-sessions": true,
  "/v1/cc-sessions/{session_id}/wait": true
}
```

Live MCP `initialize + tools/list` on `http://127.0.0.1:18712/mcp` returned:

```json
{
  "tool_count": 3,
  "tool_names": [
    "advisor_agent_turn",
    "advisor_agent_cancel",
    "advisor_agent_status"
  ]
}
```

API runtime environment now resolves to the main repo path:

- `PYTHONPATH=/vol1/1000/projects/ChatgptREST`
- `CHATGPTREST_DB_PATH=/vol1/1000/projects/ChatgptREST/state/jobdb.sqlite3`
- `CHATGPTREST_ARTIFACTS_DIR=/vol1/1000/projects/ChatgptREST/artifacts`

## Notes

- `gitnexus_detect_changes()` remained stale for this branch and kept reporting two unrelated pre-existing finbot service edits in the main repo. I used local `git diff` to confirm the actual MCP hotfix scope before committing `9f5b274`.
- The main repo still has the same pre-existing unrelated dirty/untracked items:
  - `ops/systemd/chatgptrest-finbot-daily-work.service`
  - `ops/systemd/chatgptrest-finbot-theme-batch.service`
  - `.codex_tmp/`
  - `.worktrees/`
  - untracked docs noted before this task
