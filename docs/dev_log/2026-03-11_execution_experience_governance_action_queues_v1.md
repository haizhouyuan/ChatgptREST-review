---
title: Execution Experience Governance Action Queues
version: v1
updated: 2026-03-11
status: completed
---

# Goal

Remove one more manual filtering step from controller-side review work.

The governance queue exporter already split the decision scaffold by governance
state, but `decision_ready` rows could still mix different suggested actions
such as `accept_candidate`, `revise_candidate`, and `reject_candidate`.

This round keeps the same review-plane state model and simply adds action-level
queue files.

# Added

- extended `ops/export_execution_experience_governance_queues.py`
- extended `tests/test_export_execution_experience_governance_queues.py`

# What Changed

In addition to state-based queue files, the exporter now writes:

- `governance_queues/by_action/accept_candidate.json|tsv`
- `governance_queues/by_action/revise_candidate.json|tsv`
- `governance_queues/by_action/reject_candidate.json|tsv`
- any other present suggested action bucket

`summary.json` now includes an `action_files` map alongside the existing
`queue_files` and `by_action` counters.

# Boundary

This round does **not**:

- change governance classification
- change cycle wiring
- modify runtime retrieval
- promote active knowledge
- add orchestration behavior

# Verification

Focused tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_export_execution_experience_governance_queues.py
```
