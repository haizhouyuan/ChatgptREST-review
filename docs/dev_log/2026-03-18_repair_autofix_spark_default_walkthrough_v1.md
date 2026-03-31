# 2026-03-18 repair.autofix Spark Default Walkthrough v1

## What Changed

- Set the shared default `repair.autofix` model to `gpt-5.3-codex-spark`.
- Applied that default at job-creation time in `chatgptrest/core/repair_jobs.py`.
- Added executor-side fallback in `chatgptrest/executors/repair.py` so older queued jobs without `params.model` still avoid drifting to Codex1 `gpt-5.4`.
- Registered the default in `chatgptrest/core/env.py` as `CHATGPTREST_CODEX_AUTOFIX_MODEL_DEFAULT`.
- Updated the worker-repair systemd template to make the Spark default explicit in ops-visible config.

## Why

- Recent usage analysis showed `repair.autofix` was attempting Codex without an explicit model, which let the CLI default drift to the expensive Codex1 `gpt-5.4` path.
- The desired behavior is narrower: background exec/autofix should stay on a cheaper fallback model by default, while interactive human planning can still use stronger models explicitly.
- The fix is intentionally scoped to `repair.autofix`; it does not change global Codex CLI defaults or unrelated Codex callers.

## Scope

- `chatgptrest/core/repair_jobs.py`
- `chatgptrest/executors/repair.py`
- `chatgptrest/core/env.py`
- `ops/systemd/chatgptrest-worker-repair.service`
- `tests/test_worker_auto_autofix_submit.py`
- `tests/test_repair_autofix_codex_fallback.py`
- `tests/test_maint_daemon_auto_repair_check.py`

## Validation

Ran:

```bash
./.venv/bin/pytest -q \
  tests/test_worker_auto_autofix_submit.py \
  tests/test_repair_autofix_codex_fallback.py \
  tests/test_maint_daemon_auto_repair_check.py \
  tests/test_mcp_repair_submit.py

./.venv/bin/pytest -q \
  tests/test_sre_fix_request.py \
  tests/test_repair_check.py
```

All passed.

## Notes

- Explicit model overrides still win. If a caller sets `params.model`, that value is preserved.
- The new env var is a default, not a hard lock. Operators can still override the background model without code changes.
