# 2026-03-11 Planning Review Consistency Hardening v1

## Scope

This round stays inside `planning review-plane / bootstrap maintenance`.

Included:

- add a unified consistency audit across reviewed slice, backlog, priority queue, and live bootstrap atoms
- include the consistency artifact in the planning priority review maintenance cycle
- lock the consistency invariants with narrow regression tests

Excluded:

- runtime retrieval defaults
- planning runtime cutover
- execution telemetry contract changes
- active knowledge promotion changes

## Code Changes

- Added [ops/report_planning_review_consistency.py](/vol1/1000/projects/ChatgptREST/ops/report_planning_review_consistency.py)
  - joins `report_state`, `report_backlog`, and `build_priority_queue`
  - checks:
    - `reviewed_backlog_partition_ok`
    - `allowlist_subset_of_reviewed_ok`
    - `allowlist_live_coverage_ok`
    - `bootstrap_allowlist_alignment_ok`
    - `priority_queue_within_candidate_pool_ok`
    - `candidate_pool_within_backlog_ok`
    - `latest_output_backlog_within_backlog_ok`
- Updated [run_planning_review_priority_cycle.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_priority_cycle.py)
  - now writes `consistency_audit.json`
  - now exposes `consistency_ok` in `summary.json`
- Added [test_report_planning_review_consistency.py](/vol1/1000/projects/ChatgptREST/tests/test_report_planning_review_consistency.py)
- Updated [test_run_planning_review_priority_cycle.py](/vol1/1000/projects/ChatgptREST/tests/test_run_planning_review_priority_cycle.py)
  - seeds minimal live atoms for the reviewed slice
  - verifies `consistency_audit.json` is emitted
  - verifies `summary["consistency_ok"] == true`

## Validation

### Tests

```bash
./.venv/bin/python -m py_compile \
  ops/report_planning_review_consistency.py \
  ops/run_planning_review_priority_cycle.py \
  tests/test_report_planning_review_consistency.py \
  tests/test_run_planning_review_priority_cycle.py

./.venv/bin/pytest -q \
  tests/test_report_planning_review_consistency.py \
  tests/test_run_planning_review_priority_cycle.py \
  tests/test_report_planning_review_state.py \
  tests/test_report_planning_review_backlog.py \
  tests/test_build_planning_review_priority_bundle.py
```

### Live Read-Only Checks

```bash
./.venv/bin/python ops/report_planning_review_consistency.py --limit 50
./.venv/bin/python ops/run_planning_review_priority_cycle.py --limit 50
```

Live result on canonical EvoMap:

- `allowlist_docs = 116`
- `reviewed_docs = 156`
- `backlog_docs = 3194`
- `candidate_pool_docs = 1483`
- `selected_docs = 50`
- `live_active_atoms = 201`
- `live_candidate_atoms = 25`
- `checks[*] = true`
- `ok = true`

Cycle output:

- [consistency_audit.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_priority_cycle/20260311T055904Z/consistency_audit.json)
- [summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_priority_cycle/20260311T055904Z/summary.json)

## Outcome

Planning maintenance now has a single artifact that states whether:

- reviewed slice still partitions cleanly against backlog
- allowlist is still covered by live bootstrap atoms
- bootstrap live atoms have not drifted outside the allowlist
- priority queue is still bounded by the candidate pool and backlog

This hardens maintenance visibility without expanding into runtime or promotion work.
