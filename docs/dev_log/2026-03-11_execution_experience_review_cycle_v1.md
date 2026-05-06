---
title: Execution Experience Review Cycle
version: v1
updated: 2026-03-11
status: completed
---

# Goal

Turn execution `experience_candidates` from a one-off export into a real
candidate/review-plane closure loop:

- export reviewed atom-derived candidates
- build a reviewer-ready pack
- emit a reviewer manifest for fixed reviewer lanes
- merge reviewer JSON outputs into a versioned baseline
- materialize reviewed experience candidates without promoting to active

This stays below active knowledge and does not alter runtime retrieval.

# Added

- `ops/build_execution_experience_review_pack.py`
- `ops/compose_execution_experience_review_decisions.py`
- `ops/merge_execution_experience_review_outputs.py`
- `ops/run_execution_experience_review_cycle.py`

# What Changed

## 1. Candidate export now has a real consumer

The previous execution cycle could emit:

- `experience_candidates.json`
- `experience_candidates.tsv`

but there was no stable next step for reviewers.

This round adds a dedicated review pack builder that writes:

- `execution_experience_review_pack_v1.json`
- `execution_experience_review_pack_v1_prompt.txt`
- `summary.json`

## 2. Reviewer lanes now have a fixed contract

`run_execution_experience_review_cycle.py` emits a reviewer manifest for:

- `gemini_no_mcp`
- `claudeminmax`
- `codex_auth_only`

The review contract is intentionally candidate-plane only:

- `accept`
- `revise`
- `reject`
- `defer`

with explicit fields for:

- `experience_kind`
- `title`
- `summary`
- `groundedness`
- `time_sensitivity`
- `note`

## 3. Review outputs now close back into reviewed artifacts

Reviewer JSON outputs are merged into:

- `execution_experience_review_decisions_delta_v1.tsv`
- `execution_experience_review_decisions_vN.tsv`

Then the cycle materializes:

- `reviewed_experience_candidates.json`
- `reviewed_experience_candidates.tsv`
- `accepted_review_candidates.json`
- `accepted_review_candidates.tsv`

These remain review-plane artifacts. They are not imported into active
knowledge.

# Boundary

This round does **not**:

- modify the live `TraceEvent` contract
- alter execution atom promotion rules
- promote reviewed experiences into active knowledge
- change runtime retrieval defaults
- create a second live event standard

# Verification

Focused tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_build_execution_experience_review_pack.py \
  tests/test_compose_execution_experience_review_decisions.py \
  tests/test_merge_execution_experience_review_outputs.py \
  tests/test_run_execution_experience_review_cycle.py
```

# Operational Note

Unlike the underlying execution activity review cycle, this experience cycle
depends on an existing `execution_review_decisions_v*.tsv` baseline. If no such
baseline exists yet, pass `--decisions` explicitly or create the first
execution review decision TSV before running the experience loop on live data.
