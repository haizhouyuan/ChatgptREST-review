# 2026-04-07 Controller Completion Contract Reconcile Review Packet For Claude v1

## Review Scope

This packet covers A2 only:

- `chatgptrest/controller/engine.py`
- `tests/test_public_agent_pro_regenerate_guard.py`

It intentionally excludes:

- public MCP surface changes from A1
- wrapper changes from A1
- `server.py` role cleanup
- project-scoped substrate work

## Problem Statement

After A1, public agent payloads expose:

- `answer_state`
- `completion_contract`
- `canonical_answer`

But controller reconciliation still used legacy completion semantics:

- if `job.status == completed`
- and `job.answer_path` exists
- then mark the execution work item as `DELIVERED`

That allowed a mismatch where:

- job/result contract says `provisional`
- controller run says `DELIVERED`

## Patch Summary

### engine.py

Adds `_job_completion_view()`:

- reads `result.json` if present
- merges result payload with current job row
- derives:
  - `completion_contract`
  - `canonical_answer`
  - `answer_state`
  - `canonical_ready`
  - `authoritative_job_id`
  - `authoritative_answer_path`
  - `answer_provenance`

Changes `_reconcile_job_work_item()`:

- final contract path:
  - `completed + canonical_ready + authoritative_answer_path`
  - remains `DELIVERED`
- provisional path:
  - `completed + !canonical_ready`
  - now remains `WAITING_EXTERNAL`
  - `next_action=await_job_completion`
  - delivery stays `in_progress`

### tests

Adds:

1. `test_controller_reconciles_completed_job_with_final_contract_to_delivered`
2. `test_controller_keeps_completed_job_with_provisional_contract_waiting_external`
3. `test_controller_reconciles_completed_legacy_job_without_result_json_to_delivered`

Also absorbs follow-up findings from a fork-resume `claudegac` review:

- provisional delivery now carries `"answer": ""` for schema consistency
- `_job_completion_view()` is only invoked inside the completed branch
- legacy fallback without `result.json` is now explicitly covered by regression test

## Expected Review Questions

Please review for:

1. Whether controller now trusts the right source of truth for completion finality.
2. Whether the fallback behavior is still backward-compatible when `result.json` is absent.
3. Whether authoritative answer path propagation is correct.
4. Whether the provisional test is realistic enough.
5. Whether there is a smaller or safer implementation inside `engine.py`.

## Regression Coverage Run

Executed locally:

- `./.venv/bin/pytest -q tests/test_public_agent_pro_regenerate_guard.py`
- `./.venv/bin/pytest -q tests/test_agent_v3_routes.py`
- `./.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py -k "controller or v3_ask_returns_controller_snapshot"`
- `./.venv/bin/pytest -q tests/test_routes_agent_v3_session_job_alignment.py`

## Risk Posture

GitNexus impact for `_reconcile_job_work_item` is `CRITICAL`.

Because of that, this patch stays intentionally narrow:

- no new route shape
- no prompt changes
- no MCP surface changes
- no `server.py` restructuring

## Requested Verdict

Needed from Claude review:

- findings-first review
- explicit `no findings` if acceptable
- residual risks if no blocking issues remain
