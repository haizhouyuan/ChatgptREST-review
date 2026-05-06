# 2026-03-11 Execution Experience Progress-Delta Fixture Bundle Walkthrough v1

## Scope

This walkthrough covers only the tracked fixture bundle for `progress_delta.json`.

It does not change the builder. It only freezes minimal deterministic samples
that mainline can replay while staying inside `fixture / test / docs`.

## Files

- [2026-03-11_execution_experience_progress_delta_fixture_bundle_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_execution_experience_progress_delta_fixture_bundle_v1.md)
- [test_execution_experience_progress_delta_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_progress_delta_fixture_bundle.py)
- [execution_experience_progress_delta_fixture_bundle_20260311](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_progress_delta_fixture_bundle_20260311)

## Replay model

This fixture targets the same call shape the cycle already has after two review
checkpoints exist:

1. previous governance snapshot
2. current governance snapshot
3. previous controller action plan
4. current controller action plan
5. `build_delta(...)` turns those four artifacts into one `progress_delta.json`

That is why the tracked inputs are normalized checkpoint snapshots rather than
raw candidate exports or review outputs.

## Covered shapes

The bundle pins two cases:

1. `improved`
   - reviewed candidates go up
   - backlog and validation issues go down
   - controller action severity de-escalates
   - `progress_signal = improved`
2. `regressed`
   - reviewed candidates go down
   - backlog and validation issues go up
   - controller action severity escalates
   - `progress_signal = regressed`

Together they freeze the exact fields mainline asked for:

- previous/current totals
- validation delta
- queue delta
- attention-flag flips
- `progress_signal`

## Verification

Run:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_build_execution_experience_progress_delta.py \
  tests/test_execution_experience_progress_delta_fixture_bundle.py

python3 -m py_compile \
  tests/test_execution_experience_progress_delta_fixture_bundle.py
```

The regression normalizes the four input `output_path` values down to filenames
before comparison so the snapshots stay stable across machines.

## Boundary reminder

This walkthrough does **not** authorize edits to:

- `ops/build_execution_experience_progress_delta.py`

It is only snapshot support for the controller-facing cross-cycle delta surface.
