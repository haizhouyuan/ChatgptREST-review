# 2026-04-04 W1 Send Priority and Blank Gemini Autofix Alignment Walkthrough v1

## What I did

1. Reproduced the latest `OpenClawBot` live completion failure and checked current queued/running jobs.
2. Confirmed the generic send worker was repeatedly claiming long `repair.autofix` jobs generated from blank Gemini cooldowns.
3. Added send-phase priority so real ask traffic is claimed ahead of `repair.*`.
4. Added a worker guard to skip auto-autofix for blank Gemini timeout cooldowns with no thread evidence.
5. Added targeted unit tests for both behaviors.
6. Restarted the generic send worker, cleared stale live-gate backlog via cancel requests, and reran the live completion gate.
7. Captured the new evidence bundle and updated the runbook/master-plan baseline.

## Why I changed it

The previous state had already moved past fake-green, but it still had a queue pathology: when Gemini timed out before producing a thread, the system would often spawn `repair.autofix`, and those long repair jobs then occupied the generic send worker before the next real ask. That made live evidence slower and noisier, and it hid the actual provider problem behind operational churn.

## What changed in behavior

After this batch:

1. send workers prefer normal ask traffic ahead of `repair.*`;
2. blank Gemini timeout cooldowns without thread evidence no longer auto-submit repair work;
3. the live completion gate now more reliably reaches terminal `needs_followup` instead of hanging on send-worker backlog.

## What did not change

1. Gemini still does not reliably produce a completed answer within the current live gate contract.
2. ChatGPT live lane is still verification-blocked.
3. session boundary and stateful read-refresh are still phase-1 design debts.

## Verification run

### Tests

- `python3 -m py_compile chatgptrest/core/job_store.py chatgptrest/worker/worker.py tests/test_claim_priority.py tests/test_worker_auto_autofix_submit.py`
- `./.venv/bin/pytest -q tests/test_claim_priority.py tests/test_worker_auto_autofix_submit.py tests/test_gemini_provider_timeout_budget.py tests/test_gemini_idempotency_replay_recovery.py tests/test_openclawbot_planning_task_plane_live_completion_gate.py tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py`

### Live evidence

- `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v8/`

## Current takeaway

This batch is a queue-discipline and truthful-fail-closed improvement. It reduces self-inflicted interference and makes the remaining provider blocker easier to isolate.
