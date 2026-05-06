# 2026-03-11 Execution Lineage Review Decision Overlay

## Goal

Add the smallest possible overlay path for reviewed lineage decisions.

This round still stays in `execution-layer / contract-supply`:

- no runtime adoption
- no automatic final judgment
- no mutation of live canonical telemetry

It only gives the review scaffold a deterministic merge/overlay target.

## Added

- [compose_execution_lineage_review_decisions.py](/vol1/1000/projects/ChatgptREST/ops/compose_execution_lineage_review_decisions.py)
- [test_compose_execution_lineage_review_decisions.py](/vol1/1000/projects/ChatgptREST/tests/test_compose_execution_lineage_review_decisions.py)

## What It Does

Input:

- a prior lineage review decision TSV (optional)
- a reviewed delta TSV

Output:

- a merged versioned lineage review decision TSV
- a sibling `.summary.json`

The overlay keeps the same review-plane fields from the scaffold:

- `final_decision_bucket`
- `approved_fill_fields`
- `final_remediation_action`
- `reviewer`
- `review_notes`

## Why This Matters

The previous rounds already provided:

- live lineage sparsity baseline
- deterministic remediation/decision input
- tracked sample bundle
- ready-to-fill review scaffold

What was still missing was a deterministic way to version and overlay reviewed
lineage decisions without inventing a new runtime system.

This overlay script fills that final contract-supply gap.

## Fixture Result

The tracked fixture bundle now includes:

- `review_decisions_base_v1.tsv`
- `review_decisions_delta_v1.tsv`
- `review_decisions_merged_v1.tsv`
- `review_decisions_merged_summary_v1.json`

Those fixture files capture:

- one replaced reviewed row
- two newly added reviewed rows
- final counts by `final_decision_bucket`
- final counts by `final_remediation_action`

## Boundary

This round still does **not**:

- execute remediation
- automate final decision generation
- change runtime retrieval
- promote execution knowledge

It only composes already-reviewed lineage decision rows.
