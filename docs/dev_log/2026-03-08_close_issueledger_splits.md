# 2026-03-08 Issue Ledger split closure

## Summary

Closed the actionable follow-ups that were previously mixed into the umbrella
post-merge review for PR #98 and PR #100.

## Changes

1. EvoMap supersede transitions now go through `PromotionEngine.supersede()`
   instead of directly mutating `promotion_status` in the executor.
2. `tests/test_driver_singleton_lock_guard.py` now patches the current shared
   infra seams instead of the removed legacy `_run_cmd` hooks.
3. The OpenClaw integration contract now explicitly states that OpenMind is the
   durable cognitive substrate and OpenClaw is an optional front-end, with M1 /
   M2 / M3 maturity gates spelled out in the integration doc.

## Validation

- `./.venv/bin/pytest -q tests/test_promotion_engine.py tests/test_evolution_queue.py`
- `./.venv/bin/pytest -q tests/test_driver_singleton_lock_guard.py tests/test_maint_daemon_codex_sre.py -k 'driver or systemd or singleton'`

## Notes

- Left unrelated local changes untouched, including `docs/gemini_web_ui_reference.md`
  and untracked `knowledge/` artifacts.
