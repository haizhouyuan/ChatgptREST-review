# 2026-03-11 Execution Activity Review Scaffold

## Goal

Add a deterministic TSV scaffold for the lineage-ready execution activity queue,
so later review work does not need to reconstruct its own template.

Added:

- [build_execution_activity_review_scaffold.py](/vol1/1000/projects/ChatgptREST/ops/build_execution_activity_review_scaffold.py)
- [test_build_execution_activity_review_scaffold.py](/vol1/1000/projects/ChatgptREST/tests/test_build_execution_activity_review_scaffold.py)

## What It Writes

The scaffold exports a TSV with these columns:

- `atom_id`
- `source`
- `episode_type`
- `atom_type`
- `task_ref`
- `trace_id`
- `canonical_question`
- `answer_preview`
- `suggested_bucket`
- `final_bucket`
- `reviewer`
- `review_notes`

This stays explicitly below extraction and below promotion. It only turns the
existing review queue into a ready-to-fill decision surface.

## Live Result

Command:

```bash
PYTHONPATH=. ./.venv/bin/python \
  ops/build_execution_activity_review_scaffold.py \
  --limit 50 \
  --output-tsv artifacts/monitor/execution_activity_review_bundle/latest/review_decisions_template.tsv
```

Result:

- `selected_atoms = 25`
- output:
  - `artifacts/monitor/execution_activity_review_bundle/latest/review_decisions_template.tsv`

## Interpretation

The execution review surface now has:

- a state audit
- a lineage-ready queue
- a portable review bundle
- a deterministic decision template

That is enough structure to stop before automatic review or promotion and keep
the next layer explicitly human/model-review-first.
