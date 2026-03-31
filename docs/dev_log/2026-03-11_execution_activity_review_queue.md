# 2026-03-11 Execution Activity Review Queue

## Goal

Add a narrow export for the execution-activity review layer, without widening
runtime retrieval or promoting anything into active knowledge.

Added:

- [export_execution_activity_review_queue.py](/vol1/1000/projects/ChatgptREST/ops/export_execution_activity_review_queue.py)
- [test_export_execution_activity_review_queue.py](/vol1/1000/projects/ChatgptREST/tests/test_export_execution_activity_review_queue.py)

## Selection Rule

This queue is intentionally narrow. It only exports atoms that are already:

- `promotion_reason = activity_ingest`
- `promotion_status = staged`
- `canonical_question != ''`
- `task_ref != ''`
- `trace_id != ''`

This keeps the queue focused on lineage-ready execution atoms that are suitable
for later candidate/review work.

## Why This Matters

The earlier execution activity state audit showed that the current canonical
slice is broad enough to inspect, but still dominated by older archive-heavy
data with sparse execution extensions.

This queue export is the next step up from raw audit:

- not yet experience extraction
- not yet service-visible knowledge
- but already a deterministic review surface for the lineage-ready subset

## Boundary

This round does **not**:

- change runtime retrieval
- change promotion behavior
- widen active knowledge
- touch planning review-plane maintenance

## Live Result

Command:

```bash
PYTHONPATH=. ./.venv/bin/python ops/export_execution_activity_review_queue.py --limit 50
```

Current canonical DB snapshot:

- `selected_atoms = 25`
- `sources = {agent_activity=25}`
- `episode_types = {team.run.created=9, workflow.completed=7, tool.completed=5, team.run.completed=3, workflow.failed=1}`
- `atom_types = {lesson=25}`

## Interpretation

The first lineage-ready queue is intentionally narrow:

- it selects only staged execution atoms that already have both `task_ref` and
  `trace_id`
- it still does **not** require richer execution extensions like `lane_id` or
  `role_id`
- at the current live state, the queue is dominated by the newer
  `agent_activity` workflow/tool/team events rather than the older archive-only
  commit/closeout bulk

That makes it a suitable next-layer review surface without turning it into
active runtime knowledge.
