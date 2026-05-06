---
title: Execution Experience Review Decision Scaffold
version: v1
updated: 2026-03-11
status: completed
---

# Goal

Add the missing controller-facing governance surface for execution experience
reviews.

The experience cycle already exported candidates, built review packs, validated
reviewer JSON, merged reviewed decisions, and reported backlog state. What it
still lacked was a deterministic TSV handoff that says which candidates are:

- still pending review
- under-reviewed
- disputed
- deferred
- ready for a final review-plane decision

This stays in candidate/review plane. It does not promote anything into active
knowledge and does not touch runtime retrieval.

# Added

- `ops/build_execution_experience_review_decision_scaffold.py`
- `tests/test_build_execution_experience_review_decision_scaffold.py`
- extended `ops/run_execution_experience_review_cycle.py`

# What Changed

## 1. Experience governance now has a stable TSV surface

The new scaffold builder writes `review_decision_scaffold.tsv` with one row per
current candidate and governance-oriented columns such as:

- `reviewer_count`
- `expected_reviewer_count`
- `provided_reviewers`
- `missing_reviewers`
- `distinct_reviewer_decisions`
- `suggested_governance_state`
- `suggested_governance_action`

It also writes a sibling `.summary.json` with counts by state/action.

## 2. Refresh-only cycles now reflect existing experience decision state

When a prior `execution_experience_review_decisions_vN.tsv` already exists, the
cycle now uses it during refresh-only runs to compute:

- backlog state against the current candidate set
- the decision scaffold against the same baseline

That means repeated maintenance runs no longer flatten everything back into
"all backlog" just because no new reviewer JSON was passed in.

## 3. Merge cycles now emit the latest governance scaffold

After reviewer JSON is validated and merged, the cycle rewrites
`review_decision_scaffold.tsv` using the newly composed full decision TSV. This
gives controller/maintainer work a direct artifact target without inventing a
new workflow.

# Boundary

This round does **not**:

- modify the live `TraceEvent` canonical contract
- alter runtime retrieval defaults
- promote reviewed experiences into active knowledge
- introduce reviewer orchestration or platform behavior
- create a second live event standard

# Verification

Focused tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_build_execution_experience_review_decision_scaffold.py \
  tests/test_run_execution_experience_review_cycle.py
```
