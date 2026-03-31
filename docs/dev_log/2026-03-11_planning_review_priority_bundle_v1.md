# 2026-03-11 Planning Review Priority Bundle v1

## Scope

Turn the planning backlog visibility layer into a deterministic review bundle, without widening the reviewed baseline.

Added:

- [build_planning_review_priority_bundle.py](/vol1/1000/projects/ChatgptREST/ops/build_planning_review_priority_bundle.py)
- [test_build_planning_review_priority_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_build_planning_review_priority_bundle.py)

## What It Writes

Given the canonical DB, the builder emits:

- `review_queue.json`
- `review_queue.tsv`
- `summary.json`
- `README.md`

The queue is intentionally narrower than the full backlog. It only selects unreviewed planning docs that still look review-worthy after deterministic filtering:

- exclude already reviewed docs
- exclude `archive_only / controlled`
- prefer:
  - `planning_latest_output`
  - `planning_outputs`
  - `planning_strategy`
  - `planning_budget`
  - `planning_kb`
  - `planning_skills`
  - `planning_aios`
- hard-exclude obvious noise like:
  - `README`
  - `runlog`
  - `request`
  - `answer`
  - `问 Pro`

## Live Result

Command:

```bash
./.venv/bin/python \
  ops/build_planning_review_priority_bundle.py \
  --limit 50 \
  --output-dir artifacts/monitor/planning_review_priority_bundle/latest
```

Result:

- `selected_docs = 50`
- `candidate_pool_docs = 1483`

By domain:

- `business_104 = 21`
- `governance = 14`
- `strategy = 8`
- `reducer = 3`
- `business_60 = 2`
- `budget = 2`

By source bucket:

- `planning_outputs = 18`
- `planning_aios = 14`
- `planning_latest_output = 8`
- `planning_strategy = 8`
- `planning_budget = 2`

Output dir:

- [latest bundle](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_priority_bundle/latest)

## Interpretation

This bundle is the first deterministic answer to:

`If we do another review round, which unreviewed planning docs are actually worth spending reviewer capacity on first?`

The result is useful because it avoids two common mistakes:

1. treating all `latest_output` docs as high value
2. pushing the entire `3194` backlog into reviewer lanes

Instead, it isolates a smaller queue that is dominated by:

- real deliverable outputs
- governance/AIOS artifacts
- strategy/budget materials

while leaving obvious packaging/readme/runlog/question residue out of the queue.

## Boundary

This round did **not**:

- expand the reviewed slice
- apply new planning decisions
- change runtime retrieval defaults
- alter promotion rules

It only converts the backlog audit into a deterministic review handoff bundle.
