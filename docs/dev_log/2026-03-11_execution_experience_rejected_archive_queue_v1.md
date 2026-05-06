---
title: Execution Experience Rejected Archive Queue
version: v1
updated: 2026-03-11
status: completed
---

# Goal

Close the reject branch of execution experience review-plane governance.

The cycle already tracked when a candidate landed in `reject`, but there was no
stable queue artifact for later archive/rejection handling. This round adds
that queue without changing decision logic or runtime behavior.

# Added

- `ops/build_execution_experience_rejected_archive_queue.py`
- `tests/test_build_execution_experience_rejected_archive_queue.py`
- extended `ops/run_execution_experience_review_cycle.py`

# What Changed

The new builder reads current candidates plus an optional reviewed decision TSV
and emits `rejected_archive_queue.tsv` for `review_decision=reject` rows only.

Each row carries the current reviewed content plus blank follow-up fields:

- `archive_bucket`
- `archive_owner`
- `archive_notes`

The cycle now emits this queue in both cases:

- `refresh_only`, using an existing baseline experience decision TSV when one is
  available
- `refresh_merge_only`, using the newly composed full decision TSV

# Boundary

This round does **not**:

- change review voting or decision composition
- change runtime retrieval defaults
- promote rejected candidates into active knowledge
- alter live `TraceEvent` contracts

# Verification

Focused tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_build_execution_experience_rejected_archive_queue.py \
  tests/test_run_execution_experience_review_cycle.py
```
