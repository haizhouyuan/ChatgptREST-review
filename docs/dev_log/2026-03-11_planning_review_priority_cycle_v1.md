# 2026-03-11 Planning Review Priority Cycle v1

## Goal

Collapse the planning backlog review surface into one maintenance entrypoint, while staying below runtime cutover and below active-knowledge changes.

Added:

- [run_planning_review_priority_cycle.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_priority_cycle.py)
- [build_planning_review_scaffold.py](/vol1/1000/projects/ChatgptREST/ops/build_planning_review_scaffold.py)
- [test_run_planning_review_priority_cycle.py](/vol1/1000/projects/ChatgptREST/tests/test_run_planning_review_priority_cycle.py)
- [test_build_planning_review_scaffold.py](/vol1/1000/projects/ChatgptREST/tests/test_build_planning_review_scaffold.py)

## What One Cycle Emits

One invocation now writes:

- `state_audit.json`
- `backlog_audit.json`
- `review_queue.json`
- `summary.json`
- `bundle/review_queue.json`
- `bundle/review_queue.tsv`
- `bundle/summary.json`
- `bundle/README.md`
- `bundle/review_decisions_template.tsv`

## Boundary

This remains a maintenance/review entrypoint only:

- no runtime retrieval changes
- no automatic apply into the reviewed slice
- no generic promotion changes
- no planning runtime cutover

## Live Result

Command:

```bash
./.venv/bin/python \
  ops/run_planning_review_priority_cycle.py \
  --limit 50
```

Result:

- `reviewed_docs = 156`
- `backlog_docs = 3194`
- `selected_docs = 50`
- `latest_output_backlog_docs = 160`
- output dir:
  - [20260311T050547Z](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_priority_cycle/20260311T050547Z)

## Interpretation

Planning maintenance now has a single deterministic entrypoint for the next review round:

- reviewed slice health
- backlog shape
- priority queue
- portable review bundle
- TSV scaffold for reviewer decisions

That means the planning line is no longer depending on ad hoc assembly from separate audit scripts when reviewer lanes need a fresh batch.
