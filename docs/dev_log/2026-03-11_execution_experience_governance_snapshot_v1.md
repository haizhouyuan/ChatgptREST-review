# 2026-03-11 Execution Experience Governance Snapshot v1

## What changed

- added `ops/build_execution_experience_governance_snapshot.py`
- wired `ops/run_execution_experience_review_cycle.py` to emit `governance_snapshot.json`
- covered refresh-only, merge, and validation-failed cycle paths with focused tests

## Why

The cycle already emitted backlog, validation, governance queue, and follow-up artifacts, but controller-facing governance still required stitching multiple JSON files together. This slice adds one stable review-plane summary that flattens:

- backlog pressure
- reviewer validation health
- governance queue distribution
- follow-up branch counts

It stays strictly in candidate/review plane:

- no runtime adoption
- no active knowledge promotion
- no new live event contract

## Output

Each cycle now writes `governance_snapshot.json` alongside the existing cycle artifacts. The snapshot carries:

- totals for candidate coverage and follow-up load
- review-state counters such as `under_reviewed_candidates` and `disputed_candidates`
- validation-state counters and missing/unexpected reviewers
- queue-state counts for governance states/actions and follow-up branches
- simple attention flags for controller-facing governance

## Verification

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_build_execution_experience_governance_snapshot.py \
  tests/test_run_execution_experience_review_cycle.py \
  tests/test_build_execution_experience_followup_manifest.py \
  tests/test_build_execution_experience_rejected_archive_queue.py \
  tests/test_build_execution_experience_deferred_revisit_queue.py \
  tests/test_export_execution_experience_acceptance_pack.py \
  tests/test_build_execution_experience_revision_worklist.py

PYTHONPATH=. ./.venv/bin/python -m py_compile \
  ops/build_execution_experience_governance_snapshot.py \
  ops/run_execution_experience_review_cycle.py \
  tests/test_build_execution_experience_governance_snapshot.py \
  tests/test_run_execution_experience_review_cycle.py
```
