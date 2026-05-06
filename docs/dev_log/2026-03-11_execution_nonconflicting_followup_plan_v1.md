# 2026-03-11 Execution Nonconflicting Follow-up Plan v1

## Context

As of 2026-03-11, the main execution review line already moved forward via:

- `955d4d9` `feat: add execution review lineage decision cycle`
- `ddf472c` `feat: add execution experience review cycle`

That means the current mainline now already owns:

- execution lineage registry
- execution review decision governance
- execution experience candidate export
- execution experience review cycle

This follow-up plan is therefore intentionally scoped to **non-conflicting**
work only.

## Explicit No-Touch Area

Until mainline asks otherwise, do **not** add new slices inside these files:

- `ops/build_execution_activity_lineage_registry.py`
- `ops/build_execution_activity_review_scaffold.py`
- `ops/compose_execution_activity_review_decisions.py`
- `ops/export_execution_experience_candidates.py`
- `ops/run_execution_activity_review_cycle.py`
- `ops/build_execution_experience_review_pack.py`
- `ops/compose_execution_experience_review_decisions.py`
- `ops/merge_execution_experience_review_outputs.py`
- `ops/run_execution_experience_review_cycle.py`

Also stay out of:

- runtime adoption
- `TraceEvent` live canonical contract changes
- active knowledge promotion
- retrieval-default cutover

## Objective

Use the remaining safe surface to improve:

1. maint-side runner readiness evidence
2. supply-side visibility into live-vs-fixture gaps
3. review-plane consumption clarity

without overlapping the now-mainline-owned execution review cycles.

## Slice A: Maint Runner Capability Snapshot Bundle

### Goal

Turn the current maint-side runner preparation work into a single tracked,
portable capability snapshot bundle.

### Repo

- `/vol1/maint`

### Proposed additions

- `ops/scripts/build_runner_capability_snapshot_bundle.py`
- `tests/test_build_runner_capability_snapshot_bundle.py`
- `docs/2026-03-11_runner_capability_snapshot_bundle.md`
- tracked bundle root under `docs/artifacts/runner_capability_snapshot_bundle_20260311/`

### Inputs

- latest `runner_lane_probe` projection/validation outputs
- latest `codex_batch_doctor` summary
- `codex_batch.sh`
- `gemini_batch.sh`
- `hcom_preflight.sh`

### Outputs

- `capability_snapshot.json`
- `validation_summary.json`
- `doctor_summary.json`
- `adapter_identity_matrix.tsv`
- `README.md`

### Value

This gives mainline a stable, versioned upstream adapter-preparation artifact
without requiring any runtime wiring.

### Validation

- `pytest -q tests/test_runner_lane_probe.py tests/test_codex_batch_doctor.py tests/test_build_runner_capability_snapshot_bundle.py`
- one live bundle run on maint

## Slice B: Execution Live-vs-Fixture Gap Report

### Goal

Compare the tracked lineage-remediation fixture bundle against the current live
execution lineage backlog, so mainline can see exactly what is missing in live
archive data.

### Repo

- `/vol1/1000/projects/ChatgptREST`

### Proposed additions

- `ops/report_execution_lineage_fixture_gap.py`
- `tests/test_report_execution_lineage_fixture_gap.py`
- `docs/dev_log/2026-03-11_execution_lineage_fixture_gap_report.md`

### Inputs

- `docs/dev_log/artifacts/execution_lineage_remediation_fixture_bundle_20260311/`
- `docs/dev_log/artifacts/execution_lineage_remediation_bundle_20260311/`
- current backlog report output

### Outputs

- `fixture_gap_summary.json`
- `fixture_gap_table.tsv`
- optional markdown summary for issue copy/paste

### Questions answered

- which identity fields exist in tracked fixture but never appear in live
- whether live has any `remediation_candidate` rows
- whether live has any mixed-richness groups
- how far live is from the smallest non-sparse fixture state

### Validation

- `pytest -q tests/test_report_execution_lineage_fixture_gap.py`
- one live run against the current lineage bundle

## Slice C: Review-Plane Consumption Runbook

### Goal

Document the exact operator sequence for consuming the current execution
review-plane outputs without touching runtime code.

### Repo

- `/vol1/1000/projects/ChatgptREST`

### Proposed addition

- `docs/dev_log/2026-03-11_execution_review_plane_consumption_runbook.md`

### Topics

1. when to use `review_decision_input.json`
2. when to generate `review_decisions_scaffold.tsv`
3. how to produce reviewed delta TSVs
4. how to compose reviewed overlays
5. how to read backlog summaries
6. how to hand off reviewed experience candidates without promoting them

### Value

This reduces coordination friction and keeps future work from accidentally
rebuilding local ad hoc flow around the same artifacts.

## Slice D: Candidate-Fill / Sparse-Lineage Fixture Expansion

### Goal

Extend the tracked fixture bundle with a few more edge cases that are still
strictly review-plane and deterministic.

### Repo

- `/vol1/1000/projects/ChatgptREST`

### Candidate cases

1. same `task_ref` with multiple `trace_id`s
2. same `trace_id` but conflicting partial extension sets
3. no `task_ref`, `trace_id` only degraded family
4. partial group where `profile_id` appears without `lane_id/role_id`

### Proposed additions

- new fixture JSON/TSV files under
  `docs/dev_log/artifacts/execution_lineage_remediation_fixture_bundle_20260311/`
- one or two targeted tests extending the current fixture regressions

### Validation

- focused fixture tests only

## Recommended Order

1. Slice A
2. Slice B
3. Slice C
4. Slice D

Reason:

- Slice A improves upstream adapter evidence outside the mainline-owned code
- Slice B turns current live sparsity into a precise gap report
- Slice C makes all current artifacts easier to consume
- Slice D is useful but should come after the live gap is explicitly measured

## Stop Conditions

Stop immediately if:

- mainline asks for a new approved slice
- mainline starts editing the same new report/runbook files
- any proposed work begins to require touching the execution review cycle or
  execution experience review cycle files listed above

## Current Recommendation

The safest next implementation is:

- **Slice A first**, in `/vol1/maint`

because it strengthens the upstream adapter-preparation lane and does not touch
the execution review-plane code that mainline just advanced.
