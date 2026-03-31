# 2026-03-11 Execution Experience Revision-Worklist Fixture Bundle Walkthrough v1

## Purpose

This walkthrough explains how the tracked revision-worklist fixture bundle maps
onto mainline's new revise-only worklist surface.

## Files and roles

- [experience_candidates_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_revision_worklist_fixture_bundle_20260311/experience_candidates_v1.json)
  defines the candidate metadata available to the worklist builder
- [execution_experience_review_decisions_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_revision_worklist_fixture_bundle_20260311/execution_experience_review_decisions_v1.tsv)
  is the reviewed decision input with one `accept` row and one `revise` row
- [revision_worklist_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_revision_worklist_fixture_bundle_20260311/revision_worklist_v1.tsv)
  records the revise-only filtered output
- [revision_worklist_v1_summary.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_revision_worklist_fixture_bundle_20260311/revision_worklist_v1_summary.json)
  records the normalized summary for that output

## Filtering behavior this bundle demonstrates

The builder ignores non-`revise` decisions and carries through only the fields
needed for the rewrite/tightening pass. In this minimal fixture:

- `execxp_accept` is dropped
- `execxp_revise` becomes the only worklist row

The output row also keeps blank follow-up fields ready for the next pass:

- `revised_title`
- `revised_summary`
- `revision_editor`
- `revision_notes`

## Normalization used by the regression

The builder summary includes tmp-directory paths for:

- `candidates_path`
- `decisions_path`
- `output_tsv`
- `summary_path`

The regression normalizes those to basenames before comparing against
`revision_worklist_v1_summary.json`. The emitted TSV is compared directly.

## Why this is still non-conflicting

This bundle does not edit:

- `ops/build_execution_experience_revision_worklist.py`
- `ops/run_execution_experience_review_cycle.py`
- `ops/merge_execution_experience_review_outputs.py`
- runtime retrieval / promotion paths
- reviewer orchestration / platform behavior

It only adds tracked fixtures, one regression file, and explanatory docs around
the already-approved revise-only worklist surface.
