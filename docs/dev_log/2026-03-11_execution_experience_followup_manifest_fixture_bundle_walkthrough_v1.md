# 2026-03-11 Execution Experience Followup-Manifest Fixture Bundle Walkthrough v1

## Scope

This walkthrough covers only the tracked fixture bundle for
`followup_manifest.json`.

It does not change the builder or the cycle. It only freezes a minimal,
deterministic sample that mainline can replay while staying inside
`fixture / test / docs`.

## Files

- [2026-03-11_execution_experience_followup_manifest_fixture_bundle_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_execution_experience_followup_manifest_fixture_bundle_v1.md)
- [test_execution_experience_followup_manifest_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_followup_manifest_fixture_bundle.py)
- [execution_experience_followup_manifest_fixture_bundle_20260311](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_followup_manifest_fixture_bundle_20260311)

## Replay model

This fixture targets the same call shape the cycle uses in-process:

1. upstream branch builders/exporters have already returned summary dicts
2. `build_manifest(...)` receives those dicts
3. the builder writes one `followup_manifest.json`

That is why the tracked inputs are branch-summary JSON snapshots rather than raw
candidate exports or review TSVs.

## Fixture contents

The bundle pins four branch inputs:

- `acceptance_pack_input_v1.json`
- `revision_worklist_input_v1.json`
- `deferred_revisit_queue_input_v1.json`
- `rejected_archive_queue_input_v1.json`

And one expected output:

- `followup_manifest_v1.json`

The chosen counts are intentionally distinct:

- `accept = 2`
- `revise = 1`
- `defer = 3`
- `reject = 4`

That makes branch swaps visible in snapshot diffs while still keeping the
bundle small.

## Verification

Run:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_build_execution_experience_followup_manifest.py \
  tests/test_execution_experience_followup_manifest_fixture_bundle.py

python3 -m py_compile \
  tests/test_execution_experience_followup_manifest_fixture_bundle.py
```

The fixture regression normalizes temp-directory paths down to filenames before
comparison so the tracked JSON stays stable across machines.

## Boundary reminder

This walkthrough does **not** authorize edits to:

- `ops/build_execution_experience_followup_manifest.py`
- `ops/run_execution_experience_review_cycle.py`

It is only snapshot support for the controller-facing manifest surface.
