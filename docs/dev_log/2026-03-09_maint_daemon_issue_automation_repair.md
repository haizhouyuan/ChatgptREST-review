# 2026-03-09 Maint Daemon Issue Automation Repair

## Summary

- Restored live issue/incident automation after two regressions in `chatgptrest-maint-daemon.service`.
- Root causes were:
  - `ops/maint_daemon.py` shadowed the imported `sig_hash()` helper with a local variable inside `main()`, which made `job_scan` crash with `UnboundLocalError`.
  - `chatgptrest/ops_shared/subsystems.py` still imported pause helpers from `chatgptrest.core.job_store` even though `set_pause_state()` now lives in `chatgptrest.core.pause`.
- Restarted `chatgptrest-maint-daemon.service` after the fix and verified the repaired process no longer emits `job_scan` or `auto_pause` errors.

## Code Changes

- `ops/maint_daemon.py`
  - Renamed `main()` local `sig_hash` variables to `signature_hash` / `pending_signature_hash`.
  - This removed Python local-scope shadowing and restored all `sig_hash(...)` helper calls in `job_scan`, `ui_canary`, and proxy incident creation.
- `chatgptrest/ops_shared/subsystems.py`
  - `BlockedStateSubsystem.tick()` now imports `get_pause_state()`, `set_pause_state()`, and `clear_pause_state()` from `chatgptrest.core.pause`.
- `tests/test_ops_shared_subsystems.py`
  - Added a regression test that exercises `BlockedStateSubsystem.tick()` with `enable_auto_pause=true` and asserts we get `auto_pause_set`, not `auto_pause_error`.
- `tests/test_behavior_issue_detection.py`
  - Added a `maint_daemon.main()` regression that seeds a `needs_followup` Gemini job, runs long enough to cross the 5-second `job_scan` floor, and asserts no `UnboundLocalError` plus a created incident row.

## Test Evidence

- `PYTHONPATH=. ./.venv/bin/pytest -q tests/test_ops_shared_subsystems.py tests/test_behavior_issue_detection.py tests/test_maint_daemon_auto_repair_check.py tests/test_maint_daemon_incident_upsert.py`
- `./.venv/bin/python -m py_compile ops/maint_daemon.py chatgptrest/ops_shared/subsystems.py tests/test_behavior_issue_detection.py tests/test_ops_shared_subsystems.py`

## Live Verification

- Restarted `chatgptrest-maint-daemon.service` at `2026-03-09T04:14:17Z`.
- Post-restart log filter from `artifacts/monitor/maint_daemon/maint_20260309.jsonl` shows:
  - `blocked_state` emits only the normal `chatgptmcp_blocked_state` metric
  - no `subsystem_error` entries after restart
  - `job_scan` resumed and created `20260309_041419Z_d4eb820ef05c`
- This confirms the service is running the repaired code path.

## Ledger Cleanup

- Mitigated issue-ledger items after confirming the Gemini deep-research followup/classification fix is live:
  - `iss_1b4a828c9ec645379448d1699d4ab75f`
  - `iss_0f8d654d2e8e41d59a5f021e3348b3fb`
  - `iss_b1dda113e47e4fba83f3d7f4c233b656`
  - `iss_3ea5a3d38d124b83bc8803579e1113aa`
- Resolved stale incident records that no longer match live reality:
  - old Gemini region `ui_canary:*unsupported region*`
  - `needs_followup:gemini:gemini_web.ask:GeminiUnsupportedRegion`
  - old `error:qwen:qwen_web.ask:ValueError:Unknown job kind: qwen_web.ask`
  - old Gemini plan-stub `needs_followup:gemini:gemini_web.ask:RuntimeError`

## Remaining Open Items

- Left open because they are not proven fixed:
  - `iss_85c224e728624823988f1b35121b6617`
    - external review environment cannot mount the local bundle path
  - `iss_512ae3d14aae4ef8834f20b7b7474741`
  - `iss_413d43141d4546849ee1e501a587451d`
    - Qwen browser profile still needs login
  - historical `chatgpt_web.ask: MaxAttemptsExceeded` / `gemini_web.ask: DriveUploadFailed`
    - left open because they came from specific bundle/file-path upload failures and were not re-validated in this repair pass
