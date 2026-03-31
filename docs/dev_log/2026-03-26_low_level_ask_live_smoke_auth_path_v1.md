# 2026-03-26 Low-Level Ask Live Smoke Auth Path v1

## Scope

Close the remaining operational documentation gap after `5af3120`.

The repo-side fix and service reload were already done, but external reviewers still lacked a reproducible explanation for how live `/v1/jobs` smoke is supposed to authenticate and reach the ask guard.

## Problem

Reviewers could confirm:

- repo changes were present
- services were reloaded
- tests passed

But they could not independently replay the raw live `/v1/jobs` smoke with the same HTTP outcomes, because the bearer-auth path was under-documented.

In practice there are three separate ingress layers:

1. global bearer middleware in `chatgptrest/api/app.py`
2. write trace-header gate
3. low-level ask identity/auth/intent guard

If an operator misses layer 1 or 2, the request never reaches layer 3.

## What was added

### 1. Runbook clarification

`docs/runbook.md` now states explicitly that:

- non-`/v1/ops/*` routes accept `Authorization: Bearer <CHATGPTREST_API_TOKEN>`
- `/v1/jobs*` also accepts `Authorization: Bearer <CHATGPTREST_OPS_TOKEN>` as a fallback
- with `CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE=1`, live write requests also need `X-Client-Instance` and `X-Request-ID`

### 2. Reproducible smoke helper

Added:

- `ops/run_low_level_ask_live_smoke.py`

Behavior:

- reads the live env file directly instead of assuming the current shell has the same token values
- picks `CHATGPTREST_API_TOKEN`, or falls back to `CHATGPTREST_OPS_TOKEN`
- sends the required trace headers automatically
- validates four concrete outcomes:
  - unsigned `chatgptrest-admin-mcp` => `403 low_level_ask_client_auth_failed`
  - unsigned `chatgptrestctl-maint` => `403 low_level_ask_client_auth_failed`
  - deterministic `planning-wrapper` sufficiency-gate probe => `403 reason=sufficiency_gate`
  - substantive `planning-wrapper` JSON review => `200` + `job_id`

### 3. README pointer

`README.md` now points operators at the helper instead of implying that any shell bearer token assumption is sufficient for live `/v1/jobs` replay.

## Validation

Ran:

- `./.venv/bin/python -m py_compile ops/run_low_level_ask_live_smoke.py`
- `./.venv/bin/python ops/run_low_level_ask_live_smoke.py`

The live smoke helper completed successfully and printed the expected 403/403/403/200 outcome matrix.

## Residual

- this closes the reproducibility gap for live `/v1/jobs` smoke
- it does not change the remaining trust-model residual:
  - `openclaw-wrapper`
  - `planning-wrapper`
  - `advisor-automation`
  still remain `registry` mode rather than HMAC
