## Summary

This change removes the temporary runtime split where systemd pointed at the premium-ingress feature worktree.

The runtime is now anchored on `master`.

Because the primary repository checkout at `/vol1/1000/projects/ChatgptREST` is intentionally being used for a separate finbot feature branch, the live runtime now uses the clean `master` worktree:

- `/vol1/1000/worktrees/chatgptrest-dashboard-p0-20260317-clean`

That keeps runtime on `master` without disturbing the user's active feature checkout.

## What changed

1. Merged `feat/premium-ingress-blueprint-implementation` into `master`.
2. Resolved dashboard merge conflicts in favor of the existing `master` dashboard implementation.
   - Reason: the premium-ingress branch carried an older dashboard line; `master` already had the accepted dashboard fixes.
3. Updated systemd drop-ins:
   - `chatgptrest-api.service.d/20-runtime-worktree.conf`
   - `chatgptrest-mcp.service.d/20-runtime-worktree.conf`
4. Reloaded systemd and restarted:
   - `chatgptrest-api.service`
   - `chatgptrest-mcp.service`

## Verification

Targeted regression suites passed on merged `master`:

- `tests/test_routes_agent_v3.py`
- `tests/test_agent_v3_routes.py`
- `tests/test_agent_mcp.py`
- `tests/test_mcp_server_entrypoints.py`
- `tests/test_openclaw_cognitive_plugins.py`
- `tests/test_skill_chatgptrest_call.py`
- `tests/test_cli_improvements.py`
- `tests/test_rebuild_openclaw_openmind_stack.py`
- `tests/test_cc_sessiond.py`
- `tests/test_cc_sessiond_routes.py`
- `tests/test_api_startup_smoke.py`
- `tests/test_ask_contract.py`
- `tests/test_prompt_builder.py`
- `tests/test_post_review.py`
- `tests/test_thought_guard_require_thought_for.py`
- `tests/test_dashboard_routes.py`
- `tests/test_routes_advisor_v3_security.py`
- `tests/test_advisor_v3_end_to_end.py`
- `tests/test_bi14_fault_handling.py`

Live probes after restart:

- `/v3/agent/turn` exists in OpenAPI
- `/v3/agent/session/{session_id}` exists in OpenAPI
- `/v3/agent/session/{session_id}/stream` exists in OpenAPI
- `/v1/cc-sessions` exists in OpenAPI
- unauthenticated `POST /v3/agent/turn` returns `401`
- live MCP `tools/list` returns only:
  - `advisor_agent_turn`
  - `advisor_agent_cancel`
  - `advisor_agent_status`

## Result

There is no longer a temporary feature-worktree runtime path for ChatgptREST API/MCP.

The live runtime now follows the merged `master` branch worktree.
