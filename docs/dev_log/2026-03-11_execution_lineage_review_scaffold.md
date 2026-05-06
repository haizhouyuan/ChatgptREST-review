# 2026-03-11 Execution Lineage Review Scaffold

## Goal

Add one more narrow review-plane support artifact on top of the lineage
remediation decision input.

This round still stays below runtime adoption and below active knowledge. It
does not change any canonical event contract. It only turns the already-built
decision input into a ready-to-fill TSV scaffold.

## Added

- [build_execution_lineage_review_scaffold.py](/vol1/1000/projects/ChatgptREST/ops/build_execution_lineage_review_scaffold.py)
- [test_build_execution_lineage_review_scaffold.py](/vol1/1000/projects/ChatgptREST/tests/test_build_execution_lineage_review_scaffold.py)

## What It Writes

Input:

- `review_decision_input.json`

Output:

- `review_decisions_scaffold.tsv`

The scaffold preserves the suggested decision state but leaves final review
fields blank:

- `suggested_decision_bucket`
- `final_decision_bucket`
- `approved_fill_fields`
- `final_remediation_action`
- `reviewer`
- `review_notes`

## Why This Matters

The previous rounds already provided:

- a live lineage sparsity baseline
- a deterministic remediation/decision-input builder
- a tracked sample bundle with expected remediation outputs

What was still missing was the last small handoff surface for actual review
work. Mainline should not need to derive its own spreadsheet template from the
JSON payload every time.

This scaffold fills that gap without introducing a new live subsystem.

## Live Result

Command:

```bash
PYTHONPATH=. ./.venv/bin/python \
  ops/build_execution_lineage_review_scaffold.py \
  --input-json docs/dev_log/artifacts/execution_lineage_remediation_bundle_20260311/review_decision_input.json \
  --output-tsv docs/dev_log/artifacts/execution_lineage_remediation_bundle_20260311/review_decisions_scaffold.tsv
```

Result:

- `selected_rows = 31`
- `suggested_review_ready = 0`
- `suggested_remediation_candidate = 0`
- `suggested_manual_review_required = 31`

## Boundary

This round still does **not**:

- modify `TraceEvent`
- widen runtime schema
- execute remediation
- automate final review decisions
- promote knowledge

It only prepares a deterministic review-plane scaffold.
