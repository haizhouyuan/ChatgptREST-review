# 2026-04-09 Crystallized Learning Governance Hardening Walkthrough v1

## Purpose

Close production-readiness PR-4 by turning crystallized learning from a thin packet annotation into a governed, observable, shadow-mode surface.

## What changed

Runtime:

- expanded `chatgptrest/advisor/crystallized_learning.py`
  - explicit `projection_mode = shadow`
  - explicit allowlist / denylist
  - per-key support threshold metadata
  - superseded candidate reporting
  - invalidation SLA
  - compact `crystallized_learning_receipt()`
- updated `chatgptrest/cognitive/wakeup_packet.py`
  - packet receipts now expose `has_crystallized_learning`
  - compact crystal receipt is surfaced in `wakeup_packet_receipt`
  - rendered packet labels crystal projection as shadow observation

Ops/reporting:

- added `ops/report_crystallized_learning_governance.py`
  - scans current interaction-learning records by latest thread key
  - reports active crystal count, superseded candidates, denied preference occurrences, and review samples
  - writes JSON + MD + manual-review sample artifacts

Tests:

- expanded `tests/test_crystallized_learning.py`
- expanded `tests/test_wakeup_packet.py`
- added `tests/test_report_crystallized_learning_governance.py`

## Verification

Focused verification:

```bash
python3 -m py_compile \
  chatgptrest/advisor/crystallized_learning.py \
  chatgptrest/cognitive/wakeup_packet.py \
  ops/report_crystallized_learning_governance.py \
  tests/test_crystallized_learning.py \
  tests/test_wakeup_packet.py \
  tests/test_report_crystallized_learning_governance.py

./.venv/bin/pytest -q \
  tests/test_crystallized_learning.py \
  tests/test_wakeup_packet.py \
  tests/test_report_crystallized_learning_governance.py \
  tests/test_task_intake.py \
  tests/test_prompt_builder.py \
  tests/test_routes_agent_v3.py
```

Observed result:

- focused suite passed

## Archived evidence

Live host scan:

- `artifacts/monitor/crystallized_learning_governance/live/20260409T054241Z/crystallized_learning_governance_20260409T054241Z.json`
- `artifacts/monitor/crystallized_learning_governance/live/20260409T054241Z/crystallized_learning_governance_20260409T054241Z.md`
- `artifacts/monitor/crystallized_learning_governance/live/20260409T054241Z/crystallized_learning_manual_review_20260409T054241Z.md`

Key observation:

- live memory currently has `0` scanned interaction-learning records
- active crystal count is `0`
- false-positive rate is therefore `0.0` on the live host, but only because no live crystal has formed yet

Shadow fixture validation:

- `artifacts/monitor/crystallized_learning_governance/fixture/20260409T054241Z/crystallized_learning_governance_20260409T054241Z.json`
- `artifacts/monitor/crystallized_learning_governance/fixture/20260409T054241Z/crystallized_learning_governance_20260409T054241Z.md`
- `artifacts/monitor/crystallized_learning_governance/fixture/20260409T054241Z/crystallized_learning_manual_review_20260409T054241Z.md`

Key observation:

- `records_scanned = 2`
- `active_crystal_count = 1`
- `superseded_candidate_count = 1`
- `manual_review_false_positive_rate = 0.0`
- the only active fixture crystal has `winner_margin_min = 1`, so it remains a `medium`-risk sample and correctly stays shadow-only

## Closeout judgment

PR-4 is considered closed on the default thresholds because:

- crystals now carry provenance, support, supersession, invalidation, and governance metadata
- packet receipts explicitly reveal crystal projection instead of hiding it
- live host scan proves there is currently no silent production crystal drift on this machine
- shadow fixture evidence proves the governance/reporting path works before wider reuse

Residual note:

- the support threshold remains `2`; no semantic threshold change was made in this phase
- wider live reuse still requires later canary evidence
