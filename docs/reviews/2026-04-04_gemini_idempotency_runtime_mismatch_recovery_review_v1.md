# 2026-04-04 Gemini Idempotency Runtime Mismatch Recovery Review v1

## Scope

This batch narrows the earlier unsafe `blank in_progress recovery` attempt into a runtime-scoped repair for Gemini idempotency zombies.

Changed code:

- `chatgpt_web_mcp/idempotency.py`
- `tests/test_driver_idempotency_upload_hash.py`

Explicitly reverted before commit:

- the over-broad Gemini wait root-flap requeue change in `chatgpt_web_mcp/providers/gemini/wait.py`
- the companion isolated helper test in `tests/test_gemini_wait_sidebar_thread_guard.py`

## What changed

Completed in this batch:

- added `runtime_instance_id` to the idempotency row model, with in-place schema migration in `_idempotency_db_init()`
- stamped new and reset rows with the current process-scoped runtime marker
- changed blank unsent `in_progress` recovery so it only auto-recovers when all of these are true:
  - key starts with `chatgptrest:`
  - row is still blank (`sent=false`, no conversation URL, no result JSON, no error)
  - row belongs to a different or missing runtime instance
  - row age exceeds `CHATGPT_IDEMPOTENCY_EMPTY_IN_PROGRESS_RETRY_SECONDS`
- changed blank rows for the same runtime to fail closed instead of auto-resetting
- changed blank rows for non-`chatgptrest:` keys to fail closed instead of flowing into the broad stale branch
- kept the broad stale recovery path only for non-blank `in_progress` rows that already captured partial state
- documented the boundary assumption that this recovery remains safe under the repo's single-live-driver posture and is not meant to normalize overlapping writers against the same idempotency DB

## Why this was needed

The earlier live evidence showed a real `Gemini send zombie replay` failure mode:

- job `861949a9f07f4035b2fab86fbf1b8248` exhausted send retries behind an idempotency row that stayed:
  - `status=in_progress`
  - `sent=0`
  - no `conversation_url`
  - no `result_json`
  - no `error`
- that row was not a meaningful replay target; it was a blank zombie from a failed earlier send attempt

The first repair attempt fixed that symptom but introduced two unsafe behaviors:

- same-process queued requests could be mistaken for stale blank rows and replayed as duplicate sends
- Gemini wait root fallbacks could be downgraded too broadly to `in_progress`

This batch keeps the zombie fix while removing those two regressions.

## Test evidence

Passed:

- `python3 -m py_compile chatgpt_web_mcp/idempotency.py tests/test_driver_idempotency_upload_hash.py`
- `./.venv/bin/pytest -q tests/test_driver_idempotency_upload_hash.py tests/test_gemini_idempotency_replay_recovery.py tests/test_gemini_wait_sidebar_thread_guard.py tests/test_gemini_wait_conversation_url_upgrade.py tests/test_gemini_wait_conversation_hint.py tests/test_gemini_wait_param_compat.py`

New coverage in `tests/test_driver_idempotency_upload_hash.py` now proves:

- blank unsent rows recover when the runtime marker changed
- blank unsent rows do not recover for the same runtime
- blank unsent rows do not recover for non-`chatgptrest:` keys
- legacy idempotency DBs without `runtime_instance_id` migrate in place and can still recover a stale blank `chatgptrest:` row

## Live evidence after the safer narrowing

What is now proven:

- the previous unsafe wait broadening was removed before commit
- the idempotency recovery logic is now significantly narrower and test-backed

Current live state is mixed:

- previous live gate evidence in `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v2/` had already shown a real Gemini thread handoff into `wait` for provider job `722a29272d0743c4bdc912829bafbafe`
- after the narrowed idempotency patch and service restart, a new live OpenClaw completion run produced provider job `af24cd6c140943adbb5e2e20d7ad99c5`
- this new job did **not** show the old blank-zombie replay signature; instead it cooled down on a separate infrastructure failure:
  - `InfraError`
  - `CDP connect failed (TargetClosedError ...)`
  - persisted result envelope in `state/driver/mcp_idempotency.sqlite3`
- the manual `v3` gate invocation was interrupted after long terminal polling, so this batch does not claim a new green live completion verdict

## Independent judgment

This batch is safe to commit.

Why:

- the original high-risk regressions identified by red-team review were removed
- the surviving change is now narrow, explicit, and covered by both fresh-schema and legacy-schema tests
- the remaining live blocker is no longer the unsafe idempotency fix itself, but broader OpenClaw/Gemini live send stability (`CDP connect failed`, long-running send/wait terminalization)

## What this batch does not claim

This batch does **not** claim:

- `W1` is complete
- OpenClawBot live completion is green
- Gemini Pro send stability is green
- live terminal probe latency is solved

## Next useful work after this batch

Stay inside `W1` and narrow to the next real blocker:

1. inspect why OpenClaw live send hit `CDP connect failed (TargetClosedError ...)` on job `af24cd6c140943adbb5e2e20d7ad99c5`
2. decide whether that failure belongs in driver bootstrap hardening, Chrome/noVNC readiness, or Gemini lane cooldown/retry handling
3. only after that, re-run the live completion gate to see whether the main path can move from `send/wait instability` toward a clean terminal proof
