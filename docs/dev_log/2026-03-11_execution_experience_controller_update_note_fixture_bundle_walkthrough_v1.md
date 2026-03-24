# 2026-03-11 Execution Experience Controller-Update-Note Fixture Bundle Walkthrough v1

## Scope

This walkthrough covers only the tracked fixture bundle for
`controller_update_note.md`.

It does not change the update-note builder or the cycle. It only freezes minimal
deterministic markdown snapshots while staying inside `fixture / test / docs`.

## Files

- [2026-03-11_execution_experience_controller_update_note_fixture_bundle_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_execution_experience_controller_update_note_fixture_bundle_v1.md)
- [test_execution_experience_controller_update_note_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_controller_update_note_fixture_bundle.py)
- [execution_experience_controller_update_note_fixture_bundle_20260311](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_controller_update_note_fixture_bundle_20260311)

## Replay model

This fixture bundle snapshots the update note at the cycle output layer.

The regression does not call `build_note(...)` directly. Instead it:

1. seeds the minimal review DB and decision TSV
2. runs `run_cycle(...)` once
3. captures the first-cycle `controller_update_note.md`
4. runs `run_cycle(...)` a second time
5. captures the later-cycle `controller_update_note.md`
6. normalizes temp-root and dynamic cycle-dir paths
7. compares both files against tracked markdown fixtures

That keeps the bundle aligned with the real cycle contract, not just the
standalone builder contract.

## Covered states

The bundle pins:

1. `first_cycle_controller_update_note_v1.md`
2. `second_cycle_controller_update_note_v1.md`

The second snapshot uses the simplest stable replay:

- the first cycle establishes the baseline
- the second cycle materializes `progress_delta.json`
- `progress_signal = unchanged`

This is enough to freeze the two states mainline explicitly requested:

- no previous cycle
- later cycle with a real landed progress delta

## Verification

Run:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_run_execution_experience_review_cycle.py \
  tests/test_execution_experience_controller_update_note_fixture_bundle.py

python3 -m py_compile \
  tests/test_execution_experience_controller_update_note_fixture_bundle.py
```

The fixture regression rewrites the dynamic cycle directories to:

- `experience_cycle/CYCLE_DIR`
- `experience_cycle/CYCLE_DIR_01`

so the tracked markdown stays stable across runs.

## Boundary reminder

This walkthrough does **not** authorize edits to:

- `ops/build_execution_experience_controller_update_note.py`
- `ops/run_execution_experience_review_cycle.py`

It is only snapshot support for the controller-facing update-note surface.
