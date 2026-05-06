# Pro Min Chars And Contract Projection RCA v1

Date: 2026-04-27

## Scope

Investigated ChatGPT conversation:

```text
https://chatgpt.com/c/69ef1df6-38b8-83e8-8dea-5e8348d05d9a
```

Mapped ChatgptREST jobs:

- `198bca6c92944f3bb1dfac79a00c3191`: initial fresh Pro conversation.
- `540689e6941b4ca2ad2fb2e429851ead`: same-conversation follow-up.

This is a continuation of:

- `docs/dev_log/2026-04-27_pro_thinking_fast_answer_partial_finality_rca_v1.md`
- `docs/dev_log/2026-04-27_pro_wait_stale_tool_false_progress_rca_v1.md`

## What Happened

The initial job used ChatGPT Pro:

- requested/effective preset: `pro_extended`
- backend export model slug: `gpt-5-5-pro`
- backend export thinking effort: `extended`
- export finish type: `stop`
- export marked the assistant message complete

The answer was still not acceptable as the requested external advisor result. It was a complete but shallow 3,776-character response, below `min_chars=5000`. It started like a loaded-context acknowledgment and light memo:

```text
看来文件已成功加载并准备好继续...
```

The worker repeatedly re-exported the same complete answer and downgraded it because it was under `min_chars`. Since the answer was already final, waiting could not make it longer. After four browser-visible retry attempts it ended as:

```text
status: needs_followup
last_error_type: WebRetryBudgetExceeded
```

The same-conversation follow-up then produced a usable 9,276-character answer and the worker correctly wrote:

```text
completion_contract_recorded: answer_state=final
canonical_answer_recorded: ready=true
```

But the public MCP status still returned `completion_contract.answer_state=provisional` and `canonical_answer.ready=false`. That made the completed follow-up look nonfinal even though `artifacts/jobs/.../result.json` was already final.

## Root Cause

There were two distinct bugs.

### 1. Complete final answer under `min_chars` was treated as waitable progress

The min-chars completion guard did not distinguish:

- a partial/in-progress answer that may still grow, from
- a backend-complete final answer that is too short and needs a follow-up.

For research/Pro contracts, a backend-complete answer under `min_chars` is not a reason to keep waiting. It is a terminal quality failure that should become `needs_followup` immediately, preserving the provisional evidence and avoiding retry-budget burn.

### 2. Public job projection preferred stale downgrade events over recorded final contract

`routes_jobs._job_event_summary(...)` considered these events semantic finality events:

- `completion_guard_downgraded`
- `completion_guard_completed_under_min_chars`
- `completion_guard_research_contract_blocked`
- `rescue_followup_shortcircuited`

It did not consider `completion_contract_recorded`.

For job `540689e...`, the event order was:

```text
completion_guard_downgraded
answer_completed_from_export
status_changed -> completed
completion_contract_recorded(answer_state=final)
canonical_answer_recorded(ready=true)
```

Because `completion_contract_recorded` was ignored, the public job view looked backward and kept the stale `completion_guard_downgraded` reason. This contaminated `completion_quality`, `completion_contract`, `canonical_answer`, `phase_detail`, and `action_hint`.

## Fix

Worker finality fix:

- `_min_chars_guard_should_complete_under_min_chars(...)` now accepts `complete_final`.
- `_run_once(...)` passes `complete_final=true` only when the export-selected assistant is complete, has a final finish type, and there is no in-progress export marker.
- For research contracts, `semantically_final + complete_final + answer_chars < min_chars` now returns `should_complete=false` with:

```text
decision_reason: semantic_final_under_min_chars
terminal_action: needs_followup
research_contract_blocked: true
```

Public projection fix:

- `completion_contract_recorded` is now a semantic finality event.
- `_completion_quality_for_job(...)` treats `completion_contract_recorded(answer_state=final)` as `final`.
- Nonfinal recorded contracts can still surface their recorded `finality_reason`.

## Live Verification

After restarting `chatgptrest-api.service`, `chatgptrest-mcp.service`, `chatgptrest-worker-send.service`, and `chatgptrest-worker-wait.service`, the live public MCP view for follow-up job `540689e...` returned:

```text
status: completed
phase_detail: completed
answer_chars: 9276
completion_contract.answer_state: final
completion_contract.finality_reason: completed
canonical_answer.ready: true
action_hint: fetch_answer
```

`automation_job_answer` successfully returned the authoritative answer chunk from:

```text
jobs/540689e6941b4ca2ad2fb2e429851ead/answer.md
```

The original job `198bca...` remains correctly nonfinal:

```text
status: needs_followup
last_error_type: WebRetryBudgetExceeded
authoritative_job_id: 540689e6941b4ca2ad2fb2e429851ead
```

That is expected for the historical job. The fixed worker should avoid repeating the same retry-budget burn for future complete-final-but-under-min-chars Pro answers.

Read-only browser inspection was also captured without clicks or typing:

```text
artifacts/monitor/manual_session_inspections/20260427_69ef1df6/inspection.json
artifacts/monitor/manual_session_inspections/20260427_69ef1df6/screen.png
```

The inspection observed the requested conversation URL, page title `Labebe运营系统设计`, no visible login/rate-limit marker, and visible text containing the expected Paperclip/advisor content. This is only manual evidence; it is not yet the shared Browser Harness contract proposed in `2026-04-27_browser_harness_architecture_assessment_v1.md`.

## Tests

Validated with:

```text
python3 -m py_compile chatgptrest/api/routes_jobs.py chatgptrest/worker/worker.py tests/test_job_view_progress_fields.py tests/test_min_chars_completion_guard.py
./.venv/bin/pytest -q tests/test_job_view_progress_fields.py::test_completed_job_view_uses_recorded_final_contract_after_stale_downgrade tests/test_min_chars_completion_guard.py::test_min_chars_guard_research_contract_complete_final_requests_followup
./.venv/bin/pytest -q tests/test_job_view_progress_fields.py tests/test_min_chars_completion_guard.py tests/test_worker_and_answer.py -k 'job_result or canonical_completion_contract or stale_downgrade or min_chars_guard or research_contract_escalates or wait_partial_answer_prompt_echo or stale_active_finalization'
```

## Operational Lesson

Long Pro wait budgets are necessary only when there is current-turn generation evidence. If the backend export says the assistant answer is complete and final but the answer is below the research contract threshold, the correct action is `needs_followup`, not more browser retry.

The public status layer must treat `completion_contract_recorded` and `canonical_answer_recorded` as authoritative state transitions. Older downgrade events are diagnostics; they must not override a later final contract.
