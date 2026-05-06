# 2026-03-27 Low-Level Ask Live Smoke HMAC And OPS Fallback v1

## Scope

Close the remaining operator-validation gap after the first live smoke helper rollout.

The previous helper proved:

- unsigned HMAC-required maintenance calls are rejected
- `planning-wrapper` sufficiency-gate and substantive review paths behave as expected

What it did not yet prove was:

- live HMAC success paths for maintenance clients
- `/v1/jobs*` bearer auth via `CHATGPTREST_OPS_TOKEN` fallback when both API and OPS tokens exist

## Changes

### 1. Expand live smoke helper coverage

File:

- `ops/run_low_level_ask_live_smoke.py`

New behavior:

- reads both `CHATGPTREST_API_TOKEN` and `CHATGPTREST_OPS_TOKEN` from the live env file
- if both exist and differ, exercises both bearer paths separately
- uses `build_registered_client_hmac_headers(...)` with the live env map so maintenance probes can be signed correctly
- validates:
  - unsigned maintenance probe => `403 low_level_ask_client_auth_failed`
  - signed `chatgptrestctl-maint` => `200` + `job_id`
  - signed `chatgptrest-admin-mcp` => `200` + `job_id`
  - deterministic `planning-wrapper` sufficiency gate => `403 reason=sufficiency_gate`
  - substantive `planning-wrapper` JSON review => `200` + `job_id`

### 2. Update operator docs

Files:

- `docs/runbook.md`
- `README.md`

New wording makes explicit that the helper now validates both:

- maintenance HMAC success path
- OPS token fallback path for `/v1/jobs*` when it is observable on the host

## Validation

Ran:

- `./.venv/bin/python -m py_compile ops/run_low_level_ask_live_smoke.py`
- `./.venv/bin/python ops/run_low_level_ask_live_smoke.py`

Observed live result:

- helper completed with `ok=true`
- unsigned maintenance probes returned `403 low_level_ask_client_auth_failed`
- signed `chatgptrestctl-maint` probe returned `200` + `job_id`
- signed `chatgptrest-admin-mcp` probe returned `200` + `job_id`
- `planning-wrapper` sufficiency-gate probe returned `403 reason=sufficiency_gate`
- `planning-wrapper` substantive review returned `200` + `job_id`
- token report showed both API and OPS tokens present and distinct, so the OPS fallback path was actually exercised

## Residual

- this closes the smoke evidence gap for maintenance HMAC and bearer fallback
- it does not change the underlying trust model for `openclaw-wrapper`, `planning-wrapper`, or `advisor-automation`, which remain `registry` mode
