# 2026-03-11 Execution Lineage Remediation Fixture Bundle v1

## Goal

Provide a tracked, deterministic sample bundle for the `#115` lineage
remediation / review decision supply line.

This is narrower than runtime adoption:

- no `TraceEvent` changes
- no new live event system
- no automatic remediation execution

## Artifact root

- `docs/dev_log/artifacts/execution_lineage_remediation_fixture_bundle_20260311/`

## Included files

1. `fixture_seed_v1.json`
2. `identity_correlation_audit_v1.json`
3. `lineage_remediation_manifest_v1.json`
4. `review_decision_input_v1.json`
5. `review_decision_input_v1.tsv`
6. `review_decisions_scaffold_v1.tsv`
7. `review_decisions_base_v1.tsv`
8. `review_decisions_delta_v1.tsv`
9. `review_decisions_merged_v1.tsv`
10. `review_decisions_merged_summary_v1.json`
11. `review_decisions_scaffold_backlog_summary_v1.json`
12. `review_decisions_merged_backlog_summary_v1.json`
13. `summary_v1.json`
14. `README.md`

## Fixture shape

The sample bundle encodes three representative review-plane cases:

1. `at_sparse`
   - same `task_ref + trace_id` group as a richer row
   - no execution extensions present
   - should be `remediation_candidate`
2. `at_rich`
   - partial execution identity only
   - no candidate fill fields remain within its group
   - should stay `manual_review_required`
3. `at_full`
   - full extension tuple
   - should be `review_ready`

## Why this bundle exists

The live archive result from
[2026-03-11_execution_lineage_remediation_decision_bundle.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_execution_lineage_remediation_decision_bundle.md)
is intentionally conservative because the current archive is sparse.

That live result is useful as a baseline, but it is not sufficient as a
portable consumer example because it does not contain mixed richness groups.

This fixture bundle adds that missing deterministic sample surface so mainline
can review:

- correlation grouping
- remediation candidate derivation
- manual-review hold behavior
- full review-ready behavior

without depending on the current state of the live DB.

## Validation

The bundle is consumed by:

- [test_execution_lineage_remediation_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_lineage_remediation_fixture_bundle.py)
- [test_build_execution_lineage_review_scaffold.py](/vol1/1000/projects/ChatgptREST/tests/test_build_execution_lineage_review_scaffold.py)
- [test_compose_execution_lineage_review_decisions.py](/vol1/1000/projects/ChatgptREST/tests/test_compose_execution_lineage_review_decisions.py)
- [test_report_execution_lineage_review_backlog.py](/vol1/1000/projects/ChatgptREST/tests/test_report_execution_lineage_review_backlog.py)

That regression seeds a temporary DB from `fixture_seed_v1.json`, runs
`build_execution_lineage_remediation_bundle.py`, normalizes the generated
artifacts, and compares them against the tracked expected JSON/TSV outputs.

The tracked `review_decisions_scaffold_v1.tsv` gives the same sample bundle a
ready-to-fill review surface.
