# 2026-04-04 W1 OpenClaw live session pause projection fix walkthrough v1

## Why this batch existed

The OpenClawBot live completion gate had crossed an important boundary:

- the provider side was already clearly unhealthy or blocked
- but the public session surface still looked like `running/check_status`

That mismatch made the live gate fail as a timeout instead of an actionable repair state.

## What I changed

1. Added send-pause-aware public projection in [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py).
2. Extended recoverable same-session repair markers to include the SSE / JSON-RPC termination family.
3. Passed pause metadata through `_job_snapshot()` so the projector could see active global pause state.
4. Added targeted tests in [test_routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3.py).
5. Updated [contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/contract_v1.md) so the public session contract matches runtime behavior.

## What I verified

### Code-level

- `python3 -m py_compile chatgptrest/api/routes_agent_v3.py tests/test_routes_agent_v3.py`
- `./.venv/bin/pytest -q tests/test_routes_agent_v3.py -k 'pause_as_needs_followup or sse_end_cooldown_as_needs_followup or cooldown_without_conversation_url_as_needs_followup or stale_child_as_needs_followup'`

### Live-level

I cleared the previous leftover live-eval session job, then re-ran:

- `ops/run_openclawbot_planning_task_plane_live_completion_gate.py`

with:

- `CHATGPTREST_EVAL_OUT_DIR=..._v17`
- `CHATGPTREST_EVAL_TERMINAL_TIMEOUT_SECONDS=240`

The new run produced:

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v17/report_v1.json)

The key result is:

- `terminal_status=needs_followup`

instead of another fake timeout-shaped `running/check_status` projection.

## What this means

This batch improves truthfulness, not raw provider quality.

It proves:

- the public session surface is less misleading than before
- W1 is now cleaner to debug because the live gate can distinguish "incomplete provider work that needs same-session repair" from "ordinary still-running progress"

It does not yet prove:

- stable green end-to-end OpenClawBot live completion

## Handoff note

If the next batch still fails live completion, the remaining problem is now more likely in:

- provider-side send stability
- bridge/tool caller propagation
- true live completion semantics

not in session projection ambiguity.
