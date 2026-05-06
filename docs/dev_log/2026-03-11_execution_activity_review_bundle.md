# 2026-03-11 Execution Activity Review Bundle

## Goal

Turn the lineage-ready execution activity queue into a small, review-friendly
bundle, without moving into active knowledge or changing runtime retrieval.

Added:

- [build_execution_activity_review_bundle.py](/vol1/1000/projects/ChatgptREST/ops/build_execution_activity_review_bundle.py)
- [test_build_execution_activity_review_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_build_execution_activity_review_bundle.py)

## What It Writes

Given the canonical DB, the builder emits:

- `review_queue.json`
- `review_queue.tsv`
- `summary.json`
- `README.md`

The bundle consumes the same narrow queue contract:

- `promotion_reason = activity_ingest`
- `promotion_status = staged`
- `canonical_question != ''`
- `task_ref != ''`
- `trace_id != ''`

## Boundary

This round still does **not**:

- classify active knowledge
- alter retrieval defaults
- widen planning runtime usage
- change promotion rules

It only turns the execution review queue into a deterministic artifact bundle.

## Live Result

Command:

```bash
PYTHONPATH=. ./.venv/bin/python \
  ops/build_execution_activity_review_bundle.py \
  --limit 50 \
  --output-dir artifacts/monitor/execution_activity_review_bundle/latest
```

Result:

- `selected_atoms = 25`
- output dir:
  - `artifacts/monitor/execution_activity_review_bundle/latest/review_queue.json`
  - `artifacts/monitor/execution_activity_review_bundle/latest/review_queue.tsv`
  - `artifacts/monitor/execution_activity_review_bundle/latest/summary.json`
  - `artifacts/monitor/execution_activity_review_bundle/latest/README.md`

## Interpretation

The execution review layer now has a deterministic handoff artifact:

- the audit answers what exists
- the queue answers which staged atoms are lineage-ready
- the bundle makes that queue portable for later review/candidate work

This is still intentionally below active knowledge and below runtime retrieval.
