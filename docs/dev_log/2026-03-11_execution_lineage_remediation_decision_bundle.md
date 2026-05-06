# 2026-03-11 Execution Lineage Remediation / Decision Input Bundle

## Goal

Add one narrow supply artifact for `#115`:

- execution lineage remediation manifest
- identity/correlation audit
- deterministic review decision input

This stays strictly inside `execution-layer / contract-supply` and
`review-plane support`.

## Added

- [build_execution_lineage_remediation_bundle.py](/vol1/1000/projects/ChatgptREST/ops/build_execution_lineage_remediation_bundle.py)
- [test_build_execution_lineage_remediation_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_build_execution_lineage_remediation_bundle.py)

## What It Builds

Starting from the existing lineage-ready execution review queue, the builder
emits:

- `identity_correlation_audit.json`
- `lineage_remediation_manifest.json`
- `review_decision_input.json`
- `review_decision_input.tsv`
- `summary.json`
- `README.md`

## Deterministic Rules

The builder does not invent runtime fields and does not change canonical
contracts. It only classifies already-exported queue rows with deterministic
review support rules:

- correlation key: `task_ref + trace_id`
- extension fields considered:
  - `lane_id`
  - `role_id`
  - `adapter_id`
  - `profile_id`
  - `executor_kind`
- lineage classes:
  - `minimal_lineage`
  - `partial_execution_identity`
  - `rich_execution_identity`
- decision buckets:
  - `review_ready`
  - `remediation_candidate`
  - `manual_review_required`
- remediation actions:
  - `none`
  - `correlate_fill_from_group`
  - `hold_sparse_lineage`

## Why This Matters

The earlier execution review surface already had:

- state audit
- lineage-ready queue
- review bundle
- review scaffold

What it did **not** yet have was a deterministic input layer for:

- execution lineage remediation review
- review decision automation scaffolding
- correlation-aware advisory generation

This bundle fills that gap without moving into runtime adoption or active
knowledge promotion.

## Boundary

This round does **not**:

- modify `TraceEvent`
- add a second live event system
- change runtime retrieval
- promote knowledge
- build an orchestrator/platform layer

It only prepares deterministic review-plane inputs.

## Live Result

Command:

```bash
PYTHONPATH=. ./.venv/bin/python \
  ops/build_execution_lineage_remediation_bundle.py \
  --limit 50 \
  --output-dir docs/dev_log/artifacts/execution_lineage_remediation_bundle_20260311
```

Result:

- `selected_atoms = 31`
- `correlation_groups = 28`
- `groups_with_mixed_identity_richness = 0`
- `rows_review_ready = 0`
- `rows_remediation_candidate = 0`
- `rows_manual_review_required = 31`

Artifacts:

- [README.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_lineage_remediation_bundle_20260311/README.md)
- [identity_correlation_audit.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_lineage_remediation_bundle_20260311/identity_correlation_audit.json)
- [lineage_remediation_manifest.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_lineage_remediation_bundle_20260311/lineage_remediation_manifest.json)
- [review_decision_input.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_lineage_remediation_bundle_20260311/review_decision_input.json)
- [review_decision_input.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_lineage_remediation_bundle_20260311/review_decision_input.tsv)
- [summary.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_lineage_remediation_bundle_20260311/summary.json)

## Interpretation

The current live archive is still sparse on execution identity extensions:

- all 28 correlation groups are `no_extension_data`
- there are no groups with mixed or rich identity data
- the generated decision layer therefore stays conservative and sends all
  currently selected rows to `manual_review_required`

That is still useful for `#115` because it provides a deterministic review
decision input and a concrete lineage sparsity baseline, without changing live
contracts or pretending runtime remediation already exists.
