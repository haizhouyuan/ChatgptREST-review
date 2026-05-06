# Pro Wait Stale Tool False Progress RCA v1

Date: 2026-04-27

## Scope

Follow-up investigation for the stuck Pro comparison workflow around job:

- old Pro corrective job: `076c4a2b073b495d87bb93a7d097b12a`
- Gemini DeepThink comparison job: `0dada145364746529cd8585ebf7bbf5d`
- mistaken Gemini Pro job: `05cb0a998ccb42fd8929c2778d831207`

This is a deeper continuation of `docs/dev_log/2026-04-27_pro_thinking_fast_answer_partial_finality_rca_v1.md`.

## What Happened

The old Pro job stayed `in_progress / wait` for an extended period. The user observed that the ChatGPT Web activity pane did not appear to be making real progress.

Runtime status showed the worker was alive and polling. This was not a dead worker or API outage. The event stream repeatedly showed:

- `wait_partial_answer_progressed` with `answer_chars=472`
- `wait_active_finalization_observed`
- `best_role=tool`
- `best_progress=30.116840781560022`
- repeated `wait_requeued`

The 472-character “answer” was the user’s corrective prompt echo, not an assistant answer.

Conversation export inspection showed one stale `tool` node:

- role: `tool`
- status: `in_progress`
- create_time: before the current corrective user prompt
- parent: an earlier follow-up user turn
- metadata: `pro_progress=30.116840781560022`, `model_slug=gpt-5-5-pro`

After the current corrective user prompt, the export only contained an empty `assistant` thoughts message and no usable assistant text.

## Root Cause

Three wait guards interacted badly.

First, active-finalization detection scanned the whole conversation export for any `status=in_progress` tool/finalization node. It did not scope the scan to the latest user turn. A stale in-progress tool from an earlier turn therefore made a later follow-up look like it was still generating.

Second, partial-answer progress dedupe compared the current full normalized answer text with the previously stored 240-character preview. Because the previous value was truncated, the same prompt echo was repeatedly recorded as changed progress with `delta_chars=0`. That kept refreshing the no-progress anchor.

Third, prompt echo was not separated from partial assistant progress. The existing echo detectors were used by completion/finality guards, but the wait progress recorder could still write the first prompt echo as `wait_partial_answer_progressed`. That made logs look like the model had produced text when the text was only the current user prompt.

Together, these two bugs made the job immortal:

1. stale tool progress kept active-finalization grace alive;
2. repeated prompt echo progress kept no-progress detection from firing;
3. the job stayed in the limited in-flight set;
4. the requested new Pro comparison could not be submitted while old Pro and Gemini occupied the two available slots.

## Fix

Worker changes:

- `_conversation_export_active_finalization_details(...)` now ignores `in_progress` export messages whose `create_time` is older than the latest user message in the export.
- `_wait_partial_answer_progress_payload(...)` now compares the previous stored preview with the current preview head, not the full current text.
- prompt echoes are now recorded as `wait_partial_answer_echo_observed`, a non-progress diagnostic event, instead of `wait_partial_answer_progressed`.
- `_record_wait_progress_signals(...)` writes a clearing `wait_active_finalization_observed` event when a previously live active-finalization state disappears. This prevents stale active-finalization events from continuing to extend Pro/thinking grace windows.

Public MCP validation changes:

- `ops/run_public_agent_mcp_validation.py` had drifted behind the current streamable-HTTP handshake helper and no longer passed `client_name` / `client_version`.
- The live validation now checks the `automation_job_cancel` input schema includes `reason`, because the source code and unit tests already supported it while a running client session still exposed the old one-argument schema.

Skill guidance changes:

- `chatgptrest-call` now explicitly says Gemini DeepThink requests must use `preset=deep_think`.
- It also tells agents to treat `low_level_ask_client_concurrency_exceeded` as an admission state to inspect/wait/cancel, not as a reason to loop with new idempotency keys.
- It documents that a missing `reason` argument on `automation_job_cancel` means the MCP service/client schema is stale and needs restart/session refresh.

Admission response changes:

- client-wide `low_level_ask_client_concurrency_exceeded` now returns `active_jobs`, `retry_after_seconds`, and `safe_next_action`, matching the operational guidance that clients should wait on or explicitly cancel a known stale job instead of resubmitting blindly.

## Expected Runtime Behavior

For job `076c4a2b073b495d87bb93a7d097b12a`, the corrected worker should no longer treat the old tool node as current progress. If no real assistant text appears, the job should reach `WaitNoProgressTimeout` / `needs_followup` instead of holding an in-flight slot indefinitely.

Gemini DeepThink job `0dada145364746529cd8585ebf7bbf5d` is a different case: it has a stable Gemini conversation URL and Web UI text saying Deep Think is still generating. It should continue to wait unless it reaches its own retry/no-progress budget.

## Tests

Added/updated coverage in `tests/test_worker_and_answer.py`:

- stale tool active-finalization before the latest user turn is ignored;
- repeated partial answer preview does not create fake progress;
- prompt echo is classified as non-progress wait evidence;
- stale active-finalization no longer extends Pro grace;
- current active-finalization still gets the longer Pro grace.

Added/updated coverage in `tests/test_public_agent_mcp_validation.py`:

- the public MCP validation report fails if the live `automation_job_cancel` schema does not advertise a `reason` argument.
- the validation runner uses the current MCP initialize handshake contract with explicit client name/version.

Added/updated coverage in `tests/test_low_level_ask_guard.py`:

- client-wide in-flight admission failures include actionable active-job metadata and a safe next action.

## Live Verification

After restarting `chatgptrest-worker-wait.service`, the old Pro job `076c4a2b073b495d87bb93a7d097b12a` moved from the prompt-echo plateau to:

```text
status: needs_followup
phase: wait
last_error_type: WaitNoProgressTimeout
```

The event stream shows the stale active-finalization state being cleared before terminalization:

```text
wait_active_finalization_observed cleared=true
wait_no_progress_timeout reason=no_progress status=needs_followup
```

After restarting `chatgptrest-mcp.service`, a live `tools/list` schema check for `automation_job_cancel` returned both `job_id` and `reason` properties.

## Operational Lesson

“Wait longer” is only correct when the current turn has live generation evidence. It is not correct when the only evidence is:

- a stale in-progress node before the latest user turn;
- an unchanged prompt echo;
- repeated export SHA churn without new assistant content.

For Pro jobs, long budget and low-frequency polling are necessary but not sufficient. The wait layer must distinguish current-turn progress from historical export residue.
