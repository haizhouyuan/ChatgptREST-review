# 2026-04-04 W1 Gemini Single-Slot UI Canary Skip Execution Review v1

## Scope
This batch only fixes the `maint_daemon -> ui_canary -> gemini self_check` interference on the W1 OpenClawBot live main path. It does **not** claim the Gemini live lane is fully healthy.

## Why this batch existed
Live evidence had already shown two stacked W1 blockers:

1. `maint_daemon` periodic `gemini_web_self_check` was competing for the only Gemini page slot when `GEMINI_MAX_CONCURRENT_PAGES=1`.
2. After isolating that interference, the deeper live provider path still failed with `GeminiBlankSendTimeout`.

This batch addresses blocker #1 permanently in code instead of relying on manual daemon shutdown.

## Code changes
- `ops/maint_daemon.py`
  - added `_ui_canary_skip_for_runtime_policy(provider=...)`
  - when `provider=gemini` and `GEMINI_MAX_CONCURRENT_PAGES=1`, `ui_canary` now records a healthy `status=skipped` round entry instead of trying to run `gemini_web_self_check`
  - this skip is overridable via `CHATGPTREST_UI_CANARY_ALLOW_GEMINI_SINGLE_SLOT=1`
- `tests/test_maint_daemon_ui_canary.py`
  - added coverage for the single-slot skip and override behavior
- `docs/runbook.md`
  - documented the new single-slot Gemini skip behavior

## Verification
### Targeted tests
- `python3 -m py_compile ops/maint_daemon.py tests/test_maint_daemon_ui_canary.py`
- `./.venv/bin/pytest -q tests/test_maint_daemon_ui_canary.py`
- `./.venv/bin/pytest -q tests/test_ops_endpoints.py -k 'ui_canary_attention or ignores_ui_canary_failures_below_threshold'`

### Runtime validation
- restarted `chatgptrest-maint-daemon.service` with the live env unchanged
- confirmed live env still had:
  - `CHATGPTREST_UI_CANARY_PROVIDERS=chatgpt,gemini`
  - `GEMINI_MAX_CONCURRENT_PAGES=1`
  - `GEMINI_REUSE_EXISTING_CDP_PAGE=0`
- reran live gate into:
  - `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v12/`

### Key live evidence
`artifacts/monitor/ui_canary/latest.json` now shows:
- `chatgpt`: still failing separately due Cloudflare/timeout issues
- `gemini`: `ok=true`, `status=skipped`, `reason=gemini_single_slot_reserved_for_live_ask`

This proves the daemon is no longer trying to occupy the only Gemini page slot during periodic UI canary rounds.

## Result
### Fixed in this batch
- the W1 top-level `ui_canary` page-slot contention is now removed in the single-slot Gemini runtime
- daemon no longer needs to be manually stopped just to let the OpenClawBot Gemini live path proceed

### Still failing after this batch
The same live gate still ended:
- `terminal_status=needs_followup`
- `next_action.type=same_session_repair`
- provider job result: `GeminiBlankSendTimeout`
- underlying original error: `mcp_http tool gemini_web_ask_pro failed ... SSE stream timeout (deadline exceeded)`

So W1 is **not complete** yet. The remaining blocker is now clearly narrowed to the Gemini send/runtime path, not to `maint_daemon/ui_canary` contention.

## Follow-up
Next batch should focus on the remaining W1 blocker only:
- `gemini_web_ask_pro` send/runtime timeout / blank-send recovery
- preserve the new `ui_canary` skip behavior while debugging deeper Gemini live execution
