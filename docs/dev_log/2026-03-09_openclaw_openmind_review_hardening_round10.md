# 2026-03-09 OpenClaw/OpenMind Review Hardening Round 10

## Why this round happened

The previous external review loop surfaced a remaining documentation/runtime mismatch:

- the blueprint still implied `maintagent` should expose and live-probe OpenMind tools in `ops`
- live verification showed that the supported baseline only needed `maintagent` as a watchdog/relay lane

While re-checking the lean verifier, another runtime-facing mismatch also appeared:

- OpenClaw sometimes wraps assistant replies as `[[reply_to_current]] ...`
- the verifier treated that transport wrapper as a functional failure

## What changed

1. Narrowed `maintagent` to the actual supported baseline:
   - `profile=minimal`
   - additive tools only: `sessions_send`, `sessions_list`
   - no direct OpenMind tool surface in the supported topology

2. Kept `main` as the sole OpenMind workbench:
   - live OpenMind probe remains on `main`
   - `maintagent` is validated through hardened tool surface plus `sessions_send` communication only

3. Hardened rebuild behavior for watchdog lanes:
   - `--prune-volatile` now clears `maintagent` session state so stale watchdog snapshots do not survive topology rebuilds

4. Hardened verifier parsing:
   - assistant text normalization now strips the `[[reply_to_current]]` wrapper before comparing expected replies

## Validation

- `./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py tests/test_verify_openclaw_openmind_stack.py`
- `./.venv/bin/python -m py_compile scripts/rebuild_openclaw_openmind_stack.py ops/verify_openclaw_openmind_stack.py tests/test_rebuild_openclaw_openmind_stack.py tests/test_verify_openclaw_openmind_stack.py`
- live `ops` rebuild + verifier
- live `lean` rebuild + verifier

## Outcome

The supported baseline is now internally consistent:

- `lean` = `main` only
- `ops` = `main + maintagent`
- `main` owns direct OpenMind cognition
- `maintagent` is a constrained watchdog/relay lane, not a second cognition lane
