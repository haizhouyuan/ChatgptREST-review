---
title: Execution Experience Review Output Validation
version: v1
updated: 2026-03-11
status: completed
---

# Goal

Make execution experience review outputs inspectable before they are merged back
into review-plane decisions.

The previous cycle could accept reviewer JSON files and merge them, but it did
not explicitly report:

- which expected reviewer lanes were still missing
- whether a reviewer output referenced unknown candidates
- whether a reviewer returned invalid decision values
- whether one reviewer repeated the same candidate more than once

# Added

- `ops/validate_execution_experience_review_outputs.py`
- `tests/test_validate_execution_experience_review_outputs.py`

# Changed

- `ops/run_execution_experience_review_cycle.py`
- `tests/test_run_execution_experience_review_cycle.py`

# What Changed

## 1. Reviewer-output validation is now a first-class step

The new validator reads:

- `experience_candidates.json`
- optional `reviewer_manifest.json`
- one or more reviewer JSON outputs

and emits a compact validation summary with:

- `expected_reviewers`
- `provided_reviewers`
- `missing_reviewers`
- `unexpected_reviewers`
- `coverage_by_review_count`
- `unknown_candidate_items`
- `invalid_decision_items`
- `duplicate_candidate_items`
- per-reviewer counts

## 2. The experience cycle now writes validation artifacts during merge

When `run_execution_experience_review_cycle.py` is called with `--review-json`,
it now writes:

- `review_output_validation_summary.json`

and also includes the validation payload in `cycle_summary.json`.

This keeps merge-time governance visible without changing runtime behavior or
introducing reviewer orchestration.

## 3. Validation distinguishes structural correctness from completeness

The summary exposes two separate booleans:

- `structurally_valid`
  - no unknown candidates
  - no invalid decisions
  - no duplicate candidate rows inside a reviewer file
- `complete`
  - all expected reviewer lanes are present when a manifest exists

That matters because a partial review round can still be structurally sound even
when not all reviewer lanes have responded yet.

# Boundary

This round does **not**:

- modify the live `TraceEvent` contract
- change runtime retrieval defaults
- promote reviewed experiences into active knowledge
- create a second live event standard
- add reviewer orchestration or runtime adoption

# Verification

Focused tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_validate_execution_experience_review_outputs.py \
  tests/test_run_execution_experience_review_cycle.py \
  tests/test_report_execution_experience_review_backlog.py \
  tests/test_merge_execution_experience_review_outputs.py \
  tests/test_build_execution_experience_review_pack.py \
  tests/test_compose_execution_experience_review_decisions.py
```

Syntax check:

```bash
PYTHONPATH=. ./.venv/bin/python -m py_compile \
  ops/validate_execution_experience_review_outputs.py \
  ops/run_execution_experience_review_cycle.py \
  tests/test_validate_execution_experience_review_outputs.py \
  tests/test_run_execution_experience_review_cycle.py
```

Temporary CLI verification:

```bash
PYTHONPATH=. ./.venv/bin/python ops/run_execution_experience_review_cycle.py \
  --db /tmp/.../evomap.db \
  --decisions /tmp/.../execution_review_decisions_v1.tsv \
  --output-root /tmp/.../out \
  --review-json /tmp/.../reviewer.json \
  --limit 20
```

The merge run wrote `review_output_validation_summary.json` and reported:

- `structurally_valid = true`
- `complete = false`
- `provided_reviewers = ["reviewer"]`
- `unexpected_reviewers = ["reviewer"]`
- `missing_reviewers = ["claudeminmax", "codex_auth_only", "gemini_no_mcp"]`

# Operational Note

This slice is descriptive and governance-oriented. It does not fail the cycle
by default, and it does not auto-correct reviewer outputs.
