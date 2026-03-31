---
title: Execution Lineage Decision Experience Cycle
version: v1
updated: 2026-03-11
status: completed
---

# Goal

Push the execution telemetry line from:

- canonical ingest works
- review bundle can be emitted

to a stricter posthoc review-plane state where:

- lineage is explicit enough to audit by family / trace / gap
- review decisions can be versioned and overlaid
- review-backed experience candidates can be exported deterministically

This change stays below runtime retrieval cutover and does not mutate the live
`TraceEvent` contract.

# Added

- `ops/build_execution_activity_lineage_registry.py`
- `ops/compose_execution_activity_review_decisions.py`
- `ops/export_execution_experience_candidates.py`
- extended `ops/build_execution_activity_review_scaffold.py`
- extended `ops/run_execution_activity_review_cycle.py`

# What Changed

## 1. Lineage is now explicit

The execution cycle now emits a lineage subdirectory with:

- `lineage_summary.json`
- `lineage_family_registry.json`
- `lineage_family_registry.tsv`
- `lineage_trace_registry.json`
- `lineage_trace_registry.tsv`
- `lineage_gap_queue.json`
- `lineage_gap_queue.tsv`
- `lineage_atoms.json`

The registry groups execution atoms into posthoc lineage families using:

- `task_ref` when present
- `trace_id` as a degraded fallback
- atom-scoped missing buckets when neither anchor exists

This makes lineage gaps visible without altering live canonical payloads.

## 2. Decision governance is now stateful

The execution review scaffold now carries governance fields, not just a blank
bucket column:

- `lineage_family_id`
- `lineage_status`
- `lineage_action`
- `family_atom_count`
- `family_trace_count`
- `suggested_bucket`
- `experience_kind`
- `experience_title`
- `experience_summary`

Decision overlays are handled by:

- `ops/compose_execution_activity_review_decisions.py`

This produces versioned decision files plus an allowlist for:

- `lesson`
- `procedure`
- `correction`

## 3. Experience extraction is now deterministic

Given a merged execution decision TSV, the cycle can now export:

- `experience/experience_candidates.json`
- `experience/experience_candidates.tsv`
- `experience/summary.json`

This stays in review-plane artifact form. It does not promote anything into
active knowledge.

# Live Result

Command:

```bash
PYTHONPATH=. ./.venv/bin/python ops/run_execution_activity_review_cycle.py --limit 50
```

Result on 2026-03-11:

- `selected_atoms = 31`
- `audit_missing_lineage_atoms = 25`
- `lineage_families = 40`
- `lineage_gap_atoms = 39`
- output dir:
  - `/vol1/1000/projects/ChatgptREST/artifacts/monitor/execution_activity_review_cycle/20260311T055821Z`

Interpretation:

- the execution line no longer stops at “queue + bundle”
- lineage-ready atoms, degraded lineage atoms, and trace groupings are visible in one cycle
- review decisions now have a versioned overlay path
- experience extraction has a deterministic artifact target once decisions exist

# Boundary

This change does **not**:

- modify the live `TraceEvent` canonical contract
- introduce a second live event standard
- lift archive/review-plane contracts into live runtime canonical
- change runtime retrieval defaults
- promote execution experiences into active knowledge automatically

# Verification

Focused tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_build_execution_activity_lineage_registry.py \
  tests/test_compose_execution_activity_review_decisions.py \
  tests/test_export_execution_experience_candidates.py \
  tests/test_build_execution_activity_review_scaffold.py \
  tests/test_run_execution_activity_review_cycle.py
```
