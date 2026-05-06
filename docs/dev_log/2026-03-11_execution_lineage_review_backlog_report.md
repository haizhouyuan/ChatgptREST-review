# 2026-03-11 Execution Lineage Review Backlog Report

## Goal

Add a deterministic status-report layer for the lineage review scaffold /
decision overlay artifacts.

This stays fully inside review-plane support:

- it reads existing scaffold/decision TSVs
- it does not generate final decisions
- it does not mutate runtime state

## Added

- [report_execution_lineage_review_backlog.py](/vol1/1000/projects/ChatgptREST/ops/report_execution_lineage_review_backlog.py)
- [test_report_execution_lineage_review_backlog.py](/vol1/1000/projects/ChatgptREST/tests/test_report_execution_lineage_review_backlog.py)

## What It Reports

Given a lineage review scaffold or merged decision TSV, the report emits:

- `total_rows`
- `reviewed_rows`
- `backlog_rows`
- `suggested_by_bucket`
- `final_by_bucket`
- `backlog_by_suggested_bucket`
- `backlog_by_remediation_action`
- `backlog_by_lineage_class`
- `backlog_rows_with_candidate_fill_fields`
- `sample_backlog_rows`

## Why This Matters

The previous rounds already provided:

- remediation / decision input
- tracked fixture bundle
- review scaffold
- reviewed-decision overlay path

What was still missing was a compact state summary for that review surface.
Without it, mainline has to manually inspect the TSV to answer:

- how much lineage review backlog remains
- whether backlog is mostly `manual_review_required` or `remediation_candidate`
- whether candidate-fill cases still exist

This report fills that gap without widening the contract.

## Live Result

Command:

```bash
PYTHONPATH=. ./.venv/bin/python \
  ops/report_execution_lineage_review_backlog.py \
  --input-tsv docs/dev_log/artifacts/execution_lineage_remediation_bundle_20260311/review_decisions_scaffold.tsv \
  --top-n 5
```

Result on current live scaffold:

- `total_rows = 31`
- `reviewed_rows = 0`
- `backlog_rows = 31`
- `backlog_rows_with_candidate_fill_fields = 0`
- `backlog_by_suggested_bucket = {manual_review_required: 31}`

## Boundary

This round still does **not**:

- automate final decisions
- execute remediation
- mutate the live telemetry contract
- promote knowledge

It only reports backlog state for the existing review-plane artifacts.
