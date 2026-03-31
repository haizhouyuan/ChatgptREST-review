---
title: Execution Experience Reviewer Identity Normalization
version: v1
updated: 2026-03-11
status: completed
---

# Goal

Reduce review-plane friction caused by reviewer identity being inferred only from
temporary file names.

The immediate symptom was that a valid reviewer JSON stored as something like
`reviewer.json` would be treated as reviewer `reviewer`, which polluted:

- `provided_reviewers`
- `missing_reviewers`
- `unexpected_reviewers`
- merged reviewer provenance in the decision TSV

# Added

- `ops/execution_experience_review_reviewer_identity.py`

# Changed

- `ops/validate_execution_experience_review_outputs.py`
- `ops/merge_execution_experience_review_outputs.py`
- `ops/run_execution_experience_review_cycle.py`
- `tests/test_validate_execution_experience_review_outputs.py`
- `tests/test_merge_execution_experience_review_outputs.py`

# What Changed

## 1. Reviewer identity now prefers canonical sources

Reviewer names are now resolved in this order:

1. explicit payload fields such as `reviewer` / `reviewer_name` / `lane`
2. exact manifest match
3. single unambiguous manifest substring match inside the file name
4. fallback to file stem

## 2. Validation and merge now share the same identity rule

Both validator and merge paths now use the same helper, so review governance and
merged provenance no longer drift apart.

## 3. The cycle now passes reviewer manifest context into merge

`run_execution_experience_review_cycle.py` now gives the merge step the same
manifest context that validation already had, so reviewer provenance in merged
TSV rows stays canonical.

# Boundary

This round does **not**:

- change review decision semantics
- modify the live `TraceEvent` contract
- alter runtime retrieval defaults
- promote anything into active knowledge
- add reviewer orchestration

# Verification

Focused tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_validate_execution_experience_review_outputs.py \
  tests/test_merge_execution_experience_review_outputs.py \
  tests/test_run_execution_experience_review_cycle.py \
  tests/test_report_execution_experience_review_backlog.py \
  tests/test_build_execution_experience_review_pack.py \
  tests/test_compose_execution_experience_review_decisions.py
```

The new regression coverage verifies:

- generic reviewer file names can still resolve to canonical reviewer lanes
- validation can mark a run complete when payload reviewer identity matches the manifest
- merged TSV reviewer provenance uses canonical reviewer names instead of temp file stems
