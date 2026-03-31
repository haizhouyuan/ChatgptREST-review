---
title: Execution Experience Governance Queues
version: v1
updated: 2026-03-11
status: completed
---

# Goal

Make the new execution experience decision scaffold directly consumable by
controller/maintainer lanes without requiring manual spreadsheet filtering.

The scaffold already expresses governance state for each candidate. This round
turns that single TSV into queue artifacts grouped by state, still entirely in
review-plane.

# Added

- `ops/export_execution_experience_governance_queues.py`
- `tests/test_export_execution_experience_governance_queues.py`
- extended `ops/run_execution_experience_review_cycle.py`

# What Changed

The cycle now exports a `governance_queues/` directory next to
`review_decision_scaffold.tsv`.

It writes one JSON + TSV pair per governance state present in the current
cycle, for example:

- `review_pending.json` / `.tsv`
- `under_reviewed.json` / `.tsv`
- `decision_ready.json` / `.tsv`
- `disputed.json` / `.tsv`
- `deferred.json` / `.tsv`

and a `summary.json` that captures counts by:

- governance state
- suggested governance action

# Why This Matters

The scaffold gives a stable tabular contract, but controller still had to
manually slice it into actionable buckets. These queue files remove that extra
step and keep future automation anchored to review-plane artifacts rather than
runtime mutation.

# Boundary

This round does **not**:

- change governance classification logic
- modify live `TraceEvent` canonical payloads
- change runtime retrieval defaults
- promote reviewed experiences into active knowledge
- add reviewer orchestration or platform behavior

# Verification

Focused tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_export_execution_experience_governance_queues.py \
  tests/test_run_execution_experience_review_cycle.py
```
