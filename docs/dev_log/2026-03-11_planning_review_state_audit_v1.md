# 2026-03-11 Planning Review State Audit v1

## Scope

Add a small audit entrypoint for the planning reviewed slice so maintenance can answer one narrow question:

`Does live canonical still match the latest planning allowlist / bootstrap contract?`

Added:

- [report_planning_review_state.py](/vol1/1000/projects/ChatgptREST/ops/report_planning_review_state.py)
- [test_report_planning_review_state.py](/vol1/1000/projects/ChatgptREST/tests/test_report_planning_review_state.py)

## What It Reports

Given:

- canonical EvoMap DB
- latest planning allowlist TSV

the script reports:

- `allowlist_docs`
- `reviewed_docs`
- `planning_review_plane_docs`
- planning atom status counts
- `allowlist_docs_without_live_atoms`
- `stale_live_atoms_outside_allowlist`
- `reviewed_but_unclassified_docs`

This is intentionally maintenance-scoped. It does not change retrieval or promotion behavior.

## Live Result

Command:

```bash
./.venv/bin/python ops/report_planning_review_state.py
```

Result:

- `allowlist_path = artifacts/monitor/planning_review_plane_refresh/20260311T032642Z/planning_review_decisions_v3_allowlist.tsv`
- `allowlist_docs = 116`
- `reviewed_docs = 156`
- `planning_review_plane_docs = 542`
- planning atom status:
  - `201 active`
  - `25 candidate`
  - `40675 staged`
- `allowlist_docs_without_live_atoms = 0`
- `stale_live_atoms_outside_allowlist = 0`
- `reviewed_but_unclassified_docs = 3194`

## Interpretation

Two things are true at the same time:

1. The reviewed bootstrap slice is healthy.
   - No allowlisted docs are missing live `active/candidate` atoms.
   - No stale bootstrap atoms remain outside the allowlist.

2. The planning family is still mostly unreviewed.
   - `3194` planning docs have `planning_review.document_role` metadata but no `decision.final_bucket`.
   - That is not drift in the reviewed slice.
   - It is the remaining review backlog outside the current reviewed baseline.

## Validation

```bash
./.venv/bin/python -m py_compile \
  ops/report_planning_review_state.py \
  tests/test_report_planning_review_state.py

./.venv/bin/pytest -q \
  tests/test_report_planning_review_state.py \
  tests/test_run_planning_review_cycle.py \
  tests/test_planning_review_refresh.py
```

## Boundary

This round did **not**:

- widen the planning service slice
- modify live retrieval rules
- alter generic promotion contracts

It only adds a deterministic audit surface for planning reviewed-baseline maintenance.
