# 2026-03-11 Execution Experience Acceptance-Pack Fixture Bundle Walkthrough v1

## Purpose

This walkthrough explains how the tracked acceptance-pack fixture bundle maps
onto mainline's new accept-branch handoff surface.

## Files and roles

- [experience_candidates_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_acceptance_pack_fixture_bundle_20260311/experience_candidates_v1.json)
  defines the candidate metadata available to the exporter
- [execution_experience_review_decisions_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_acceptance_pack_fixture_bundle_20260311/execution_experience_review_decisions_v1.tsv)
  is the reviewed decision input with one `accept` row and one `revise` row
- [accepted_candidates_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_acceptance_pack_fixture_bundle_20260311/accepted_candidates_v1.json)
  and [accepted_candidates_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_acceptance_pack_fixture_bundle_20260311/accepted_candidates_v1.tsv)
  record the accept-only filtered output
- [manifest_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_acceptance_pack_fixture_bundle_20260311/manifest_v1.json)
  records the normalized review-plane-only boundary and exported file set
- [smoke_manifest_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_acceptance_pack_fixture_bundle_20260311/smoke_manifest_v1.json)
  records the compact accept-branch handoff preview

## Filtering behavior this bundle demonstrates

The exporter ignores non-`accept` decisions and carries through only rows
eligible for the acceptance handoff. In this minimal fixture:

- `execxp_accept` is included
- `execxp_revise` is excluded

The pack boundary is explicit in the manifest:

- review-plane only
- no default runtime cutover
- no active knowledge promotion

## Normalization used by the regression

The manifest includes tmp-directory paths for:

- `source.candidates_path`
- `source.decisions_path`
- `files.accepted_candidates_json`
- `files.accepted_candidates_tsv`

The regression normalizes those path-bearing fields to basenames before
comparing against `manifest_v1.json`. The JSON/TSV content and smoke manifest
are compared directly.

## Why this is still non-conflicting

This bundle does not edit:

- `ops/export_execution_experience_acceptance_pack.py`
- `ops/run_execution_experience_review_cycle.py`
- `ops/merge_execution_experience_review_outputs.py`
- runtime retrieval / promotion paths
- reviewer orchestration / platform behavior

It only adds tracked fixtures, one regression file, and explanatory docs around
the already-approved accept-branch handoff surface.
