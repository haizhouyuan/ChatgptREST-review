# 2026-04-04 W1 OpenClaw live session pause projection fix v1

## What changed

This batch fixes a specific W1 false-projection problem on the public session surface.

Before this patch, real OpenClawBot live runs could end up in a send-side blocked/cooldown state while `GET /v3/agent/session/{session_id}` still projected:

- `status=running`
- `next_action.type=check_status`

That made the live completion gate fail as a vague `terminal_wait_timeout` even when the underlying job already had enough evidence to say "this still needs same-session repair".

This patch changes that behavior.

## Code scope

- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [test_routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3.py)
- [contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/contract_v1.md)

## Fix summary

### 1. Queued send-pause now projects as actionable repair

If the authoritative job snapshot shows:

- `job_status=queued`
- `phase=send`
- positive `retry_after_seconds`
- active global pause with `pause_mode=send|all`
- `pause_reason` indicating a real send-side block such as `auto_blocked:*`

the public session surface now projects:

- `status=needs_followup`
- `next_action.type=same_session_repair`

instead of pretending the session is still in a generic running state.

### 2. Recoverable send cooldown now projects as actionable repair

If the authoritative job snapshot shows:

- `job_status=cooldown`
- `phase=send`
- recoverable same-session repair markers in `last_error`

the public session surface now also projects:

- `status=needs_followup`
- `next_action.type=same_session_repair`

This batch explicitly includes the SSE / JSON-RPC termination family that showed up in live Gemini runs.

### 3. `_job_snapshot()` now carries pause metadata

`_job_snapshot()` now includes:

- `pause_reason`
- `pause_mode`

when a global pause is active, so the public projection layer can make a correct fail-closed decision.

## Test evidence

Targeted tests passed:

- queued send pause -> `needs_followup`
- send cooldown with missing conversation URL -> `needs_followup`
- send cooldown with SSE/JSON-RPC termination -> `needs_followup`
- stale child protection remains covered

Relevant file:
- [test_routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3.py)

## Live evidence

### Before

The earlier live gates still failed as timeout-style session projection:

- [v15 report](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v15/report_v1.json)
- [v16 report](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v16/report_v1.json)

Those runs had real send-side churn/block conditions underneath, but the public session surface still looked like `running/check_status`.

### After

The new live run:

- [v17 report](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v17/report_v1.json)
- [v17 markdown](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v17/report_v1.md)

now ends with:

- `terminal_status=needs_followup`

This is still not a green completion result, but it is the correct fail-closed projection boundary:

- no more fake "still running, just keep polling" posture
- no more masking a broken send-side session as ordinary progress
- the live gate now receives an actionable terminal repair state

## Independent judgment

This patch closes a real W1 observability/projection defect.

It does **not** complete W1 by itself.

What is now true:

- the public session layer can report actionable same-session repair for real send-side blocked/cooldown cases
- the live completion gate no longer has to fail as a misleading timeout for this class of incident

What is still not true:

- the OpenClawBot live chain still does not consistently complete end-to-end on Gemini
- the remaining W1 work is now concentrated in live provider stability / bridge completion, not in session projection ambiguity

## Next step

Keep W1 open and move to the next live-chain stabilization slice:

- reduce real send-side provider churn
- improve bridge/provider completion coverage
- re-run live completion gate until the terminal state can become `completed`, not merely `needs_followup`
