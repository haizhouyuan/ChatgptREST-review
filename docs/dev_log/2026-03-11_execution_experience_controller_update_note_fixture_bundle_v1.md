# 2026-03-11 Execution Experience Controller-Update-Note Fixture Bundle v1

## Goal

Add a tracked fixture bundle for the controller-facing `controller_update_note.md`
surface that mainline just introduced.

This round stays in `fixture / test / docs` only.

## Artifact root

- `docs/dev_log/artifacts/execution_experience_controller_update_note_fixture_bundle_20260311/`

## Included files

1. `first_cycle_controller_update_note_v1.md`
2. `second_cycle_controller_update_note_v1.md`
3. `README.md`

## What this bundle encodes

The tracked fixtures cover the two controller-update-note states that mainline
explicitly asked to preserve:

1. no previous cycle
   - `progress_signal = -`
2. later cycle with a real landed delta
   - `progress_signal = unchanged`

Both snapshots keep the four note sections mainline called out:

- current state
- progress delta
- next steps
- artifact links

## Why this matters

Mainline already landed the update-note builder and cycle wiring. What was still
missing was a tracked markdown surface that freezes how the controller-facing
note reads:

- before any previous-cycle baseline exists
- after the cycle can materialize a real `progress_delta.json`

This bundle fills that gap without touching the builder or the cycle.

## Validation

The bundle is consumed by:

- [test_execution_experience_controller_update_note_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_controller_update_note_fixture_bundle.py)

The regression:

1. seeds the minimal review DB and decision TSV
2. runs the cycle once
3. snapshots the first-cycle `controller_update_note.md`
4. runs the cycle a second time
5. snapshots the later-cycle `controller_update_note.md`
6. normalizes temp-root and dynamic cycle-dir path drift
7. compares both notes against tracked markdown fixtures

## Boundary

This round does **not**:

- modify `ops/build_execution_experience_controller_update_note.py`
- modify `ops/run_execution_experience_review_cycle.py`
- touch runtime adoption
- touch the live `TraceEvent` canonical contract
- do active knowledge promotion
