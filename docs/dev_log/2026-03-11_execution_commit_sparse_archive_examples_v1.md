# 2026-03-11 Execution Commit Sparse Archive Examples v1

## Goal

Add commit-side sparse archive examples for `agent.git.commit`, so `#115`
review does not accidentally treat archive envelopes as always rich or
full-identity payloads.

## Why this is a separate bundle

Existing evidence already proves richer archive commit envelopes:

- [2026-03-11_archive_envelope_live_smoke.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_archive_envelope_live_smoke.md)
- [test_activity_extractor.py](/vol1/1000/projects/ChatgptREST/tests/test_activity_extractor.py)
- [test_activity_ingest.py](/vol1/1000/projects/ChatgptREST/tests/test_activity_ingest.py)

Those fixtures are useful, but they can bias review toward assuming archive
commit events always carry:

- `session_id`
- `run_id`
- full execution extensions
- `provider/model`

This bundle makes the opposite explicit.

## Artifact files

Artifact root:

- `docs/dev_log/artifacts/execution_commit_sparse_bundle_20260311/`

Included files:

1. `commit_sparse_minimal_v1.json`
2. `commit_sparse_adapter_only_v1.json`
3. `commit_sparse_expectations_v1.json`

## Case design

### `commit_sparse_minimal_v1`

Smallest commit envelope that still carries useful lineage and commit evidence:

- shared anchors: `task_ref`, `trace_id`
- commit evidence: `commit.commit`, `commit.subject`
- repo context: `repo.name`, `repo.branch`
- no `session_id`
- no `run_id`
- no execution extensions
- no `provider/model`

### `commit_sparse_adapter_only_v1`

Sparse archive commit with only one execution extension:

- shared anchors: `task_ref`, `trace_id`
- one extension: `adapter_id`
- still no `session_id`
- still no `run_id`
- no `lane_id`, `role_id`, `profile_id`, `executor_kind`
- no `provider/model`

## Review intent

This bundle is meant to lock in three review points:

1. archive commit envelopes can stay valid while missing runtime execution
   identity
2. one execution extension does not justify inferring the rest
3. commit-side archive shapes should degrade gracefully just like live-bus
   emitters

## Boundary

This is still contract supply only:

- no runtime code changes
- no live event catalog changes
- no adapter registry work
- no canonical identity widening
