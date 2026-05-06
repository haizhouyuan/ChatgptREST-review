# EvoMap Promotion Inventory And Maintenance Harness Walkthrough V1

Date: 2026-04-07

## What changed

I added a low-risk `F` line for EvoMap promotion maintenance that avoids changing the existing reviewed promotion algorithm.

New code:

- [ops/report_evomap_promotion_inventory.py](/vol1/1000/projects/ChatgptREST/ops/report_evomap_promotion_inventory.py)
- [ops/run_planning_review_maintenance.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_maintenance.py)
- [ops/systemd/chatgptrest-planning-review-maintenance.service](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-review-maintenance.service)
- [ops/systemd/chatgptrest-planning-review-maintenance.timer](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-review-maintenance.timer)

New tests:

- [tests/test_report_evomap_promotion_inventory.py](/vol1/1000/projects/ChatgptREST/tests/test_report_evomap_promotion_inventory.py)
- [tests/test_run_planning_review_maintenance.py](/vol1/1000/projects/ChatgptREST/tests/test_run_planning_review_maintenance.py)

Docs updated:

- [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)
- [docs/runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md)

## Why this shape

The real bottleneck is not a missing promotion algorithm. The real bottleneck is:

- production ingest writes mostly `staged` atoms
- reviewed promotion exists for planning, but it is not wrapped in a stable maintenance loop
- there was no compact inventory view showing source/project/status/reason distribution and likely blockers

So this change does three things:

1. Adds a generic promotion inventory report.
2. Adds a planning review maintenance harness that captures pre/post evidence.
3. Adds a refresh-only timer template so the safe reviewed path can run periodically without enabling live apply.

This deliberately does **not** introduce generic auto-promotion.

## Live evidence

I ran:

```bash
python3 ops/report_evomap_promotion_inventory.py \
  --db data/evomap_knowledge.db \
  --output-dir artifacts/monitor/evomap/promotion_inventory_20260407_fline
```

The live inventory reported:

- `atoms = 103941`
- `active = 202`
- `candidate = 25`
- `staged = 103172`
- `promotion_audit = 505`
- `groundedness_audit = 164`
- `projects = 91`
- `active_ratio = 0.001943`

Artifacts:

- [promotion inventory json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap/promotion_inventory_20260407_fline/promotion_inventory_20260407T120552Z.json)
- [promotion blockers md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap/promotion_inventory_20260407_fline/promotion_blockers_20260407T120552Z.md)

I also ran the refresh-only maintenance harness:

```bash
python3 ops/run_planning_review_maintenance.py \
  --db data/evomap_knowledge.db \
  --output-root artifacts/monitor/planning_review_maintenance_20260407_fline
```

Result:

- `mode = refresh_only`
- `checks.ok = true`
- `promotion_delta.active = 0`
- `promotion_delta.candidate = 0`
- `promotion_delta.staged = 0`

That is expected for refresh-only mode.

Artifacts:

- [maintenance summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_maintenance_20260407_fline/20260407T120524Z/summary.json)
- [maintenance readme](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_maintenance_20260407_fline/20260407T120524Z/README.md)
- [cycle payload](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_maintenance_20260407_fline/20260407T120524Z/cycle_payload.json)

## Validation

Targeted tests:

```bash
./.venv/bin/pytest -q \
  tests/test_report_evomap_promotion_inventory.py \
  tests/test_run_planning_review_maintenance.py \
  tests/test_run_planning_review_cycle.py \
  tests/test_report_planning_review_state.py
```

Passed.

Focused rerun after the CLI import-path fix:

```bash
./.venv/bin/pytest -q \
  tests/test_report_evomap_promotion_inventory.py \
  tests/test_run_planning_review_maintenance.py
```

Passed.

## Review note

I attempted to use the user-provided `claudegac` session via resume/fork for an external review, but the mirror returned:

- `API Error: 402 {"error":"Insufficient credits"}`

So this batch currently has:

- code + tests
- live evidence artifacts
- self-review

but no successful external GAC review result for this specific `F` patch.
