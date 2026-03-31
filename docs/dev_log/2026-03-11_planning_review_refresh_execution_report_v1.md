# 2026-03-11 Planning Review Refresh Execution Report v1

## Scope

Continue the `planning -> EvoMap` mainline without touching runtime retrieval cutover:

- build a real incremental refresh snapshot
- review only the uncovered delta slice
- overlay delta decisions onto the current full baseline
- validate `import_review_plane + bootstrap_allowlist` on a temp EvoMap copy

## Code Added

- [planning_review_refresh.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_review_refresh.py)
- [run_planning_review_refresh.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_refresh.py)
- [compose_planning_review_decisions.py](/vol1/1000/projects/ChatgptREST/ops/compose_planning_review_decisions.py)
- [test_planning_review_refresh.py](/vol1/1000/projects/ChatgptREST/tests/test_planning_review_refresh.py)
- [test_compose_planning_review_decisions.py](/vol1/1000/projects/ChatgptREST/tests/test_compose_planning_review_decisions.py)

## Compatibility Fixes

`planning_review_plane.py` was hardened so `merge_review_outputs()` can now consume:

- top-level JSON arrays from `gemini`
- wrapper payloads whose `result/response` contains a fenced JSON array
- numeric `service_readiness` scores such as `0.7`

This was required to make multi-runner delta review usable without hand-editing JSON.

## Real Refresh Run

Refresh snapshot root:

- [20260311T032642Z](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T032642Z)

Key result after fixing baseline semantics:

- `review_needed_docs = 36`
- `role_changed_docs = 0`
- `added_service_candidates = 0`
- `removed_service_candidates = 0`
- `decision_source_dir = /vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane/20260311T022504Z`

Key delta files:

- [review summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/refresh/summary.json)
- [review needed](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/refresh/review_needed.tsv)
- [incremental review pack](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/refresh/planning_incremental_review_pack_v1.json)

## Runner Usage

Delta pack reviewers actually used:

- `gemini_no_mcp`
- `claudeminmax`

Artifacts:

- [review_runs_delta](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/review_runs_delta)

Observed runner status:

- `gemini_no_mcp`: succeeded
- `claudeminmax`: succeeded
- `codex_auth_only`: failed because the isolated Codex auth refresh token is no longer valid (`refresh_token_reused`)

The Codex failure did not block the lane because the merge path now tolerates two-runner review.

## Delta Merge Result

Merged delta decisions:

- [planning_review_decisions_delta_v1.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/planning_review_decisions_delta_v1.tsv)
- [planning_review_decisions_delta_v1.summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/planning_review_decisions_delta_v1.summary.json)

Delta verdict distribution:

- `17 service_candidate`
- `2 procedure`
- `8 review_only`
- `7 controlled`
- `2 archive_only`

Full overlaid decision set:

- [planning_review_decisions_v3.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/planning_review_decisions_v3.tsv)
- [planning_review_decisions_v3_allowlist.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/planning_review_decisions_v3_allowlist.tsv)
- [planning_review_decisions_v3.summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/planning_review_decisions_v3.summary.json)

Full `v3` result:

- `156 reviewed docs`
- `116 allowlist docs`
- by bucket:
  - `103 service_candidate`
  - `12 procedure`
  - `1 correction`
  - `25 review_only`
  - `7 controlled`
  - `7 archive_only`
  - `1 reject_noise`

## Temp DB Validation

Validation target:

- [evomap_validation.db](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/validation/evomap_validation.db)

Validation command path:

- `import_review_plane` with `planning_review_decisions_v3.tsv`
- `apply_bootstrap_allowlist` with `planning_review_decisions_v3_allowlist.tsv`

Validation result:

- `updated_docs = 3350`
- `imported_family_docs = 28`
- `imported_review_pack_docs = 8`
- `imported_model_run_docs = 350`
- `imported_decision_docs = 156`
- bootstrap:
  - `allowlist_docs = 116`
  - `candidate_atoms = 226`
  - `promoted_atoms = 201`
  - `deferred_atoms = 25`
  - `reconciled_out_atoms = 0`

Planning atom status change on temp copy:

- baseline canonical before validation: `168 active / 21 candidate / 40712 staged`
- temp copy after validation: `201 active / 25 candidate / 40675 staged`

## Boundary

This round intentionally did **not** write the refreshed `v3` decisions back into the live canonical DB.

Reason:

- another Codex lane is concurrently validating live telemetry / EvoMap coverage
- this round preserved shared-runtime isolation by validating on a temp DB copy first

## Outcome

The `planning -> EvoMap` line is now beyond one-shot bootstrap:

- refresh is incremental
- multi-runner review is usable on delta packs
- delta decisions can be composed into a full reviewed baseline
- the full apply path has been validated end-to-end on a temp EvoMap copy
