# 2026-03-11 Execution Experience Controller-Surfaces Smoke Fixture Bundle Walkthrough v1

## Scope

This walkthrough covers only the tracked fixture bundle for the seeded
controller-surfaces smoke.

It does not change the smoke runner or any builder. It only freezes the current
deterministic output set while staying inside `fixture / test / docs`.

## Files

- [2026-03-11_execution_experience_controller_surfaces_smoke_fixture_bundle_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_execution_experience_controller_surfaces_smoke_fixture_bundle_v1.md)
- [test_execution_experience_controller_surfaces_smoke_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_controller_surfaces_smoke_fixture_bundle.py)
- [execution_experience_controller_surfaces_smoke_fixture_bundle_20260311](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_controller_surfaces_smoke_fixture_bundle_20260311)

## Replay model

This fixture bundle snapshots the smoke runner at the output layer.

The regression does not seed raw inputs by hand. Instead it:

1. runs `run_smoke(...)`
2. reads `controller_surfaces_smoke_summary.json`
3. follows the four controller-facing paths recorded there
4. normalizes temp-root and cycle-dir path drift
5. compares the normalized outputs against tracked snapshots

That makes the bundle more faithful to the real smoke contract, because the
summary and the referenced files are verified together as one chain.

## Covered outputs

The bundle pins:

- smoke summary JSON
- controller packet JSON
- controller action plan JSON
- review brief markdown
- review reply draft markdown

The current seeded smoke shape is intentionally left as-is:

- `mode = refresh_merge_only`
- `recommended_action = collect_missing_reviews`
- `reason = review coverage is incomplete`

## Verification

Run:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_run_execution_experience_controller_surfaces_smoke.py \
  tests/test_execution_experience_controller_surfaces_smoke_fixture_bundle.py

python3 -m py_compile \
  tests/test_execution_experience_controller_surfaces_smoke_fixture_bundle.py
```

The fixture regression rewrites both the temp root and the dynamic cycle
directory name to `experience_cycle/CYCLE_DIR/...` so the snapshots stay stable
across runs.

## Boundary reminder

This walkthrough does **not** authorize edits to:

- `ops/run_execution_experience_controller_surfaces_smoke.py`
- `ops/run_execution_experience_review_cycle.py`

It is only snapshot support for the controller-facing smoke surface.
