---
title: Execution Experience Revision Worklist
version: v1
updated: 2026-03-11
status: completed
---

# Goal

Close the revise branch of execution experience review-plane governance.

The system already knew which candidates landed in `revise`, but there was no
stable worklist artifact for the follow-up rewrite pass. This round adds that
artifact without changing review voting or active knowledge behavior.

# Added

- `ops/build_execution_experience_revision_worklist.py`
- `tests/test_build_execution_experience_revision_worklist.py`
- extended `ops/run_execution_experience_review_cycle.py`

# What Changed

The new builder reads current experience candidates plus an optional reviewed
decision TSV and emits `revision_worklist.tsv` for `review_decision=revise`
rows only.

Each row carries the current reviewed content plus blank follow-up fields:

- `revised_title`
- `revised_summary`
- `revision_editor`
- `revision_notes`

The cycle now emits this worklist in both cases:

- `refresh_only`, using an existing baseline experience decision TSV when one is
  available
- `refresh_merge_only`, using the newly composed full decision TSV

# Boundary

This round does **not**:

- change merge voting or decision composition
- change runtime retrieval defaults
- promote revised candidates into active knowledge
- alter live `TraceEvent` contracts

# Verification

Focused tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_build_execution_experience_revision_worklist.py \
  tests/test_run_execution_experience_review_cycle.py
```
