---
title: Execution Experience Materialized Decision Splits
version: v1
updated: 2026-03-11
status: completed
---

# Goal

Improve the extraction side of execution experience review-plane outputs.

The cycle already materialized:

- all reviewed candidates
- one combined `accepted_review_candidates` set

But that still mixed `accept` and `revise` into the same downstream artifact.
This round keeps the existing files and adds explicit decision-level splits.

# Added

- extended `ops/merge_execution_experience_review_outputs.py`
- extended `tests/test_merge_execution_experience_review_outputs.py`

# What Changed

`materialize_reviewed_candidates(...)` now writes an additional
`by_decision/` directory under the reviewed output root.

For each decision present in the current reviewed set, it emits:

- `by_decision/<decision>.json`
- `by_decision/<decision>.tsv`

The materialization summary now also carries:

- `by_decision`
- `decision_files`

# Why This Matters

Controller and downstream review-plane consumers can now read:

- `accept`
- `revise`
- `reject`
- `defer`

as separate materialized candidate sets, without re-splitting the combined TSV
themselves.

# Boundary

This round does **not**:

- change merge voting logic
- change runtime retrieval defaults
- promote any reviewed experience into active knowledge
- change live telemetry contracts

# Verification

Focused tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_merge_execution_experience_review_outputs.py
```
