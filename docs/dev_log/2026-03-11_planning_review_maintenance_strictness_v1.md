# 2026-03-11 Planning Review Maintenance Strictness v1

## Scope

This round stays inside `planning review-plane / bootstrap maintenance`.

Included:

- add an optional fail-fast mode for `run_planning_review_priority_cycle.py`
- add determinism regression tests for priority queue and review scaffold

Excluded:

- runtime retrieval defaults
- planning runtime cutover
- execution telemetry contract changes
- active knowledge promotion changes

## Code Changes

- Updated [run_planning_review_priority_cycle.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_priority_cycle.py)
  - added `require_consistent` runtime option
  - CLI now exposes `--require-consistent`
  - when enabled, the cycle raises if `consistency_ok=false`
  - default behavior remains non-failing for maintenance observation runs
- Updated [test_run_planning_review_priority_cycle.py](/vol1/1000/projects/ChatgptREST/tests/test_run_planning_review_priority_cycle.py)
  - added drift case that verifies strict mode raises
- Updated [test_build_planning_review_priority_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_build_planning_review_priority_bundle.py)
  - added queue determinism regression
- Updated [test_build_planning_review_scaffold.py](/vol1/1000/projects/ChatgptREST/tests/test_build_planning_review_scaffold.py)
  - added scaffold determinism regression

## Validation

```bash
./.venv/bin/python -m py_compile \
  ops/run_planning_review_priority_cycle.py \
  tests/test_run_planning_review_priority_cycle.py \
  tests/test_build_planning_review_priority_bundle.py \
  tests/test_build_planning_review_scaffold.py

./.venv/bin/pytest -q \
  tests/test_run_planning_review_priority_cycle.py \
  tests/test_build_planning_review_priority_bundle.py \
  tests/test_build_planning_review_scaffold.py \
  tests/test_report_planning_review_consistency.py

./.venv/bin/python ops/run_planning_review_priority_cycle.py --limit 50 --require-consistent
```

The live canonical maintenance run completed cleanly under strict mode, which means the current reviewed slice/backlog/bootstrap state satisfies the consistency gate.
