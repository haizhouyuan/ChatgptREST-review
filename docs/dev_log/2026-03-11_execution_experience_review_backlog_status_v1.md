---
title: Execution Experience Review Backlog Status
version: v1
updated: 2026-03-11
status: completed
---

# Goal

Make the execution experience review loop governable after candidate export and
review-pack creation, without promoting anything to active knowledge.

The missing piece was a compact answer to:

- how many candidates are still backlog
- how many are already reviewed
- whether reviewer coverage is still incomplete
- whether any reviewed candidates are disputed or deferred
- whether a carried-forward decision row is stale relative to the current pack

# Added

- `ops/report_execution_experience_review_backlog.py`
- `tests/test_report_execution_experience_review_backlog.py`

# Changed

- `ops/run_execution_experience_review_cycle.py`
- `tests/test_run_execution_experience_review_cycle.py`

# What Changed

## 1. Experience review now emits a governance summary

The cycle already knew how to:

- export execution experience candidates
- build a reviewer pack
- merge reviewer JSON outputs
- materialize reviewed candidates

It did not emit a single report for review backlog and decision governance.

This round adds `review_backlog_summary.json`, which reports:

- `total_candidates`
- `reviewed_candidates`
- `backlog_candidates`
- `stale_reviewed_candidates`
- `by_kind`
- `reviewed_by_decision`
- `coverage_by_review_count`
- `under_reviewed_candidates`
- `disputed_candidates`
- `deferred_candidates`

## 2. Reviewer manifest coverage is now part of the report

If a reviewer manifest exists, the backlog summary reads the expected reviewer
lanes and compares them against the embedded reviewer payload in the merged
decision TSV.

That keeps this slice inside candidate/review plane while making it clear when:

- nobody has reviewed a candidate yet
- only a subset of reviewer lanes has responded
- reviewers disagree and the merged decision landed on `defer`

## 3. The report stays scoped to the current candidate pack

The report counts decision rows whose `candidate_id` is outside the current
candidate export as `stale_reviewed_candidates` instead of silently treating
them as active work.

That keeps the cycle tied to the current review pack rather than accidentally
inflating reviewed coverage with old rows.

# Boundary

This round does **not**:

- modify the live `TraceEvent` contract
- change execution promotion rules
- promote reviewed experiences into active knowledge
- change runtime retrieval defaults
- create a second live event standard
- add reviewer orchestration or runtime adoption

# Verification

Focused tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_report_execution_experience_review_backlog.py \
  tests/test_run_execution_experience_review_cycle.py \
  tests/test_merge_execution_experience_review_outputs.py \
  tests/test_build_execution_experience_review_pack.py \
  tests/test_compose_execution_experience_review_decisions.py
```

Syntax check:

```bash
PYTHONPATH=. ./.venv/bin/python -m py_compile \
  ops/report_execution_experience_review_backlog.py \
  ops/run_execution_experience_review_cycle.py \
  tests/test_report_execution_experience_review_backlog.py \
  tests/test_run_execution_experience_review_cycle.py
```

CLI verification on a temporary seeded DB and temporary decisions baseline:

```bash
PYTHONPATH=. ./.venv/bin/python ops/run_execution_experience_review_cycle.py \
  --db /tmp/.../evomap.db \
  --decisions /tmp/.../execution_review_decisions_v1.tsv \
  --output-root /tmp/.../out \
  --limit 20

PYTHONPATH=. ./.venv/bin/python ops/report_execution_experience_review_backlog.py \
  --candidates /tmp/.../candidate_export/experience_candidates.json \
  --reviewer-manifest /tmp/.../review_runs_cycle/reviewer_manifest.json
```

The temporary CLI run produced:

- `total_candidates = 1`
- `reviewed_candidates = 0`
- `backlog_candidates = 1`
- `coverage_by_review_count = {"0": 1}`
- `under_reviewed_candidates = 1`

# Operational Note

This report is intentionally descriptive. It does not assign new reviewers,
does not auto-resolve disputes, and does not trigger active-knowledge import.
