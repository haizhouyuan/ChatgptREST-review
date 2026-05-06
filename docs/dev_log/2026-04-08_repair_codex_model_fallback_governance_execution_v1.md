## Summary

This execution log completes the governance plan in `2026-04-08_repair_codex_model_fallback_governance_plan_v1.md`.

The change set does four things:

- scrubs ambient `OPENAI_*` env vars from ChatgptREST Codex CLI subprocesses by default
- keeps `repair.autofix` on an explicit cheap-tier profile and records which fallback path was actually used
- gives `sre.fix_request` an explicit default Codex profile plus fail-open manual fallback
- gives `repair.open_pr` explicit mode-based model/reasoning defaults instead of ambient behavior

## Why This Was Needed

The prior state had three systemic weaknesses:

1. Codex CLI runs could silently drift onto API-key transport because ambient `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL` leaked into subprocesses.
2. `sre.fix_request` still depended on ambient model selection and could fail the whole controller job when Codex was unavailable.
3. `repair.open_pr` had no mode-based model policy even though `p0` and `p2` do not justify the same spend.

## Implemented Changes

### 1. `chatgptrest/core/codex_runner.py`

- Added a scrubbed subprocess env builder.
- Default behavior now removes ambient `OPENAI_*` / `openai_*` variables before running `codex exec`.
- Added `CHATGPTREST_CODEX_RUNNER_PRESERVE_OPENAI_ENV=1` as an explicit opt-out.

Effect:

- ChatgptREST Codex batch jobs now prefer the local login lane by default instead of accidentally switching to API-key transport.

### 2. `repair.autofix`

- Kept the lane on `gpt-5.3-codex-spark` by default.
- Kept primary reasoning at `low`.
- Kept optional secondary Codex fallback at `minimal`.
- Added explicit report fields:
  - `execution_path`
  - `codex_profile`

Operationally this makes the lane auditable:

- `heuristic_fast_path_before_codex`
- `codex_primary`
- `codex_secondary_fallback`
- `heuristic_fallback_after_codex_failure`

### 3. `sre.fix_request`

- Added explicit default model selection:
  - default model: `gpt-5.3-codex-spark`
- Added explicit reasoning defaults:
  - resume/default diagnosis: `low`
  - fresh diagnosis: `medium`
- Added fail-open behavior:
  - if Codex fresh diagnosis fails after heuristic routing already missed, the controller now emits a structured `manual` decision instead of failing the whole job
- Added `codex` report metadata to `sre_fix_report.json`
- Stopped forwarding the controller’s default model into downstream `repair.autofix` / `repair.open_pr` jobs unless the caller explicitly requested a model override

That last point is important: downstream lanes now keep their own default model policy.

### 4. `repair.open_pr`

- Added explicit mode-based defaults:
  - `p0 -> gpt-5.3-codex-spark + low`
  - `p1 -> gpt-5.3-codex + medium`
  - `p2 -> gpt-5.3-codex + high`
- Added optional `params.reasoning_effort`
- Added `codex_profile` to `repair_open_pr_report.json`

## Documentation Updates

Updated:

- `docs/contract_v1.md`
- `docs/runbook.md`

Frozen separately:

- `docs/dev_log/2026-04-08_repair_codex_model_fallback_governance_plan_v1.md`

## Verification

### Tests

Ran:

```bash
./.venv/bin/pytest -q \
  tests/test_codex_runner.py \
  tests/test_repair_autofix_codex_fallback.py \
  tests/test_repair_open_pr_executor.py \
  tests/test_sre_fix_request.py
```

Result:

- `33 passed`

Also ran:

```bash
python3 -m py_compile \
  chatgptrest/core/codex_runner.py \
  chatgptrest/executors/repair.py \
  chatgptrest/executors/sre.py \
  chatgptrest/core/env.py
```

Result:

- passed

### Key Assertions Covered

- Codex runner scrubs ambient `OPENAI_*` env by default and can preserve it only via explicit opt-out.
- `repair.autofix` reports `execution_path` and stays on spark-tier defaults.
- `sre.fix_request` defaults to spark-tier diagnosis and falls back to `manual` instead of failing hard on Codex error.
- `repair.open_pr` uses mode-based defaults and supports explicit model/reasoning override.

## Residual Risk

- This change improves lane governance but does not by itself disable every upstream trigger source.
- Worker auto-autofix was already disabled live before this execution log; maint daemon remains the automatic authority.
- If operators intentionally set `CHATGPTREST_CODEX_RUNNER_PRESERVE_OPENAI_ENV=1`, Codex subprocesses can still be pushed back onto API-key transport.
