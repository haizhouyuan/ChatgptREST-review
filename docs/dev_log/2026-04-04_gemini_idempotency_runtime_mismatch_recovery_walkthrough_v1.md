# 2026-04-04 Gemini Idempotency Runtime Mismatch Recovery Walkthrough v1

## What I did

- reviewed the uncommitted `blank in_progress recovery` batch against live evidence
- sent the batch to a `gpt-5.4 xhigh` red-team review
- accepted the red-team rejection of the first version
- reverted the over-broad `gemini/wait.py` root-flap requeue change before commit
- redesigned the idempotency repair so blank unsent auto-recovery depends on runtime mismatch instead of raw age alone
- added a schema migration path for legacy idempotency DBs that lack `runtime_instance_id`
- added targeted tests for:
  - runtime-changed blank recovery
  - same-runtime blank fail-closed behavior
  - non-`chatgptrest:` blank fail-closed behavior
  - legacy-schema migration
- restarted runtime services and re-ran live inspection against the current OpenClaw completion path

## Key commands

```bash
python3 -m py_compile chatgpt_web_mcp/idempotency.py tests/test_driver_idempotency_upload_hash.py
./.venv/bin/pytest -q tests/test_driver_idempotency_upload_hash.py tests/test_gemini_idempotency_replay_recovery.py tests/test_gemini_wait_sidebar_thread_guard.py tests/test_gemini_wait_conversation_url_upgrade.py tests/test_gemini_wait_conversation_hint.py tests/test_gemini_wait_param_compat.py
systemctl --user restart chatgptrest-driver.service chatgptrest-api.service chatgptrest-worker-send.service chatgptrest-worker-wait.service
```

## Red-team loop

First red-team verdict:

- rejected the initial batch because:
  - blank `in_progress` recovery was broad enough to replay same-process queued requests
  - the Gemini wait root-flap helper was too permissive and could mask true thread loss

My response:

- reverted the wait helper entirely
- replaced age-only blank recovery with runtime-mismatch blank recovery
- added legacy-schema test coverage

Second red-team position after the narrowing:

- `approve-with-fixes`
- remaining concerns reduced to:
  - overlapping live writers against the same idempotency DB remain unsupported
  - legacy-schema migration coverage was missing until the final added test

## Live evidence notes

Proven old failure:

- job `861949a9f07f4035b2fab86fbf1b8248` previously died behind a blank unsent idempotency zombie

Proven intermediate improvement:

- live artifact pack `openclawbot_planning_task_plane_live_completion_gate_20260404_v2` showed provider job `722a29272d0743c4bdc912829bafbafe` reaching a real Gemini thread and entering `wait`

New live observation after narrowing:

- provider job `af24cd6c140943adbb5e2e20d7ad99c5` now shows a separate `CDP connect failed (TargetClosedError ...)` cooldown path instead of the original blank-zombie wedge
- the manual `v3` gate run was interrupted after long terminal polling, so I did not freeze a false green/false red result for that run
