---
title: Execution Experience Acceptance Pack
version: v1
updated: 2026-03-11
status: completed
---

# Goal

Close the accept branch of execution experience review-plane extraction.

The cycle already knew which reviewed candidates landed in `accept`, but there
was no explicit pack artifact for downstream opt-in consumption. This round
adds a review-plane-only acceptance pack without changing runtime defaults or
active knowledge promotion.

# Added

- `ops/export_execution_experience_acceptance_pack.py`
- `tests/test_export_execution_experience_acceptance_pack.py`
- extended `ops/run_execution_experience_review_cycle.py`

# What Changed

The new exporter reads current candidates plus an optional reviewed decision TSV
and writes an `accepted_pack/` directory containing:

- `accepted_candidates.json`
- `accepted_candidates.tsv`
- `manifest.json`
- `smoke_manifest.json`

The manifest writes the intended boundary directly:

- `review_plane_only = true`
- `default_runtime_cutover = false`
- `active_knowledge_promotion = false`

The cycle now emits this acceptance pack for:

- `refresh_only`, using an existing baseline experience decision TSV when one is
  available
- `refresh_merge_only`, using the newly composed full decision TSV

# Boundary

This round does **not**:

- change review voting or merge logic
- change runtime retrieval defaults
- promote accepted experiences into active knowledge
- alter live telemetry contracts

# Verification

Focused tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_export_execution_experience_acceptance_pack.py \
  tests/test_run_execution_experience_review_cycle.py
```
