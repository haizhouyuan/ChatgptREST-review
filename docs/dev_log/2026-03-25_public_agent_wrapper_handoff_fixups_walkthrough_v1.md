# 2026-03-25 Public Agent Wrapper Handoff Fixups Walkthrough v1

## Goal

Close the gap between the repo’s validated public-MCP client behavior and the shared `chatgptrest_call.py` wrapper used by coding-agent clients.

## Steps

1. Re-read the wrapper path and the client validation notes.
   - Confirmed the wrapper still called streamable-HTTP `tools/call` directly.
   - Confirmed local timeout-budget validation errors were being misclassified because the recovery heuristic looked for generic `timeout` text.

2. Ran GitNexus impact analysis before editing:
   - `_run_agent_turn`
   - `_run_mcp_tool`
   - `_validate_agent_mode_args`
   - `_looks_like_transport_timeout`
   - `_build_agent_summary`
   - All relevant symbols came back `LOW` risk and were isolated to the wrapper/tests surface.

3. Updated the wrapper implementation.
   - Added `initialize` + best-effort `notifications/initialized`.
   - Added MCP session-header propagation.
   - Added deferred-delivery preference for long review-style agent requests.
   - Added `advisor_agent_wait` handoff and early summary snapshots.
   - Added `submission_started` / `failure_stage` so preflight failures stop advertising fake recoverability.

4. Expanded wrapper tests.
   - Added handshake coverage for `_initialize_mcp_session`.
   - Added coverage for deferred code-review handoff to `advisor_agent_wait`.
   - Added regression coverage for the false `still_running_possible=true` preflight case.
   - Updated existing agent-mode tests to account for the new MCP initialize helper.

5. Verified and committed.
   - `74dc247 Fix public MCP wrapper handoff semantics`

6. Restarted live services.
   - `systemctl --user restart chatgptrest-api.service chatgptrest-mcp.service`

7. Ran a cheap post-restart public MCP validation.
   - `initialize` and `tools_list` passed.
   - The validator still reports an unrelated clarify-route drift on the sample planning request; left untouched in this pass.

## Why this shape

- The wrapper should not invent a second public-MCP transport contract. The repo already had a validated `initialize -> tools/call` path, so the shared client needed to converge onto it.
- Early summary snapshots plus deferred/wait handoff give clients a durable `session_id` and observable progress before the model run finishes.
- Recoverability hints are only useful when the request plausibly reached the service. Recommending `advisor_agent_status` for local validation failures creates false recovery work and hides the real bug.
