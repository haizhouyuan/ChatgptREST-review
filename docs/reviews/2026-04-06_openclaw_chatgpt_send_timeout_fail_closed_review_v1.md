# 2026-04-06 OpenClaw ChatGPT Send Timeout Fail-Closed Review v1

## Scope

This batch fixes one narrow product-surface bug on the formal `OpenClaw ->
openmind_advisor_session_get -> /v3/agent/session/{session_id}` path.

The target was not answer quality.

The target was:

> when a real `chatgpt_web.ask` child job stalls in `send` without any thread
> evidence, the formal OpenClaw session surface must fail-close to
> `needs_followup + same_session_repair`, instead of drifting back to
> `running + await_job_completion`.

## What Changed

`routes_agent_v3.py` now extends the public-session fail-closed projection for
ChatGPT send-phase no-thread failures:

1. `ToolCallError + SSE stream timeout/stream ended`
2. the later `MaxAttemptsExceeded` escalation of the same condition

The rule is intentionally narrow:

- send phase only
- no `conversation_id`
- no thread URL evidence

`AGENTS.md` was updated to freeze this as current runtime truth, and a new
targeted regression file locks the projection.

## Fresh Real Evidence

Artifact root:

- `docs/dev_log/artifacts/openclaw_chatgpt_send_timeout_fail_closed_20260406_v1/`

Key captured objects:

- `manifest.json`
- `session_tool_output_v1.json`
- `job_db_snapshot_v1.json`
- `artifacts/jobs/32317fbaf2a04dbca483e48c26e4d0e5/request.json`
- `artifacts/jobs/32317fbaf2a04dbca483e48c26e4d0e5/result.json`
- `artifacts/jobs/32317fbaf2a04dbca483e48c26e4d0e5/events.jsonl`

Real formal-path identifiers:

- session: `openclaw-real-user-check-session-d88f72fa`
- task: `pln_ca3716760df3`
- child job: `32317fbaf2a04dbca483e48c26e4d0e5`

## What Was Proved

The formal OpenClaw adapter now exposes the session as:

- `status = needs_followup`
- `next_action.type = same_session_repair`

for the same real session whose child `chatgpt_web.ask` recorded:

- repeated `send`-phase timeout behaviour
- no thread evidence
- later cooldown under `verification_pending`

The important user-surface meaning is stable even though the lower-level
cooldown reason changed during retries:

1. the child job first recorded `ToolCallError: ... SSE stream timeout`
2. a later retry cooled down as `Blocked: driver blocked: verification_pending`
3. the formal OpenClaw session surface still stayed on
   `needs_followup + same_session_repair`

So the user-facing formal session no longer drifts back to:

- `running + await_job_completion`

for this class of real send-phase failure.

## Product Meaning

This closes one more real gap that only appeared after a real OpenClaw work
task, not in plugin-only review or route-only tests.

Current honest statement:

> on the formal OpenClaw path, a real ChatGPT send-phase no-thread timeout
> / blocked sequence now fail-closes as a same-session repair problem.

That is the correct product behaviour because the user still has one live task
thread to continue repairing, not a finished answer and not a generic
investigate-from-scratch failure.

## Boundary

This batch still does **not** prove:

1. that the final planning answer is already good enough for real work
2. that a real user already used the output to advance a task
3. that Feishu conversation UX is fully proven end-to-end

It only proves the formal OpenClaw session surface now fails closed correctly
for this real ChatGPT send-phase blocker.

## Result

- accepted
