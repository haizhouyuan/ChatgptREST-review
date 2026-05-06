# EvoMap Promotion Inventory And Maintenance Harness Review Packet For Claude V1

Date: 2026-04-07

## Scope

This packet covers the `F` line only:

- promotion inventory reporting
- planning review maintenance harness
- refresh-only systemd timer template

It does **not** change:

- generic promotion rules
- groundedness thresholds
- reviewed planning bootstrap logic
- runtime retrieval policy

## Files

Code:

- [ops/report_evomap_promotion_inventory.py](/vol1/1000/projects/ChatgptREST/ops/report_evomap_promotion_inventory.py)
- [ops/run_planning_review_maintenance.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_maintenance.py)
- [ops/systemd/chatgptrest-planning-review-maintenance.service](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-review-maintenance.service)
- [ops/systemd/chatgptrest-planning-review-maintenance.timer](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-review-maintenance.timer)

Tests:

- [tests/test_report_evomap_promotion_inventory.py](/vol1/1000/projects/ChatgptREST/tests/test_report_evomap_promotion_inventory.py)
- [tests/test_run_planning_review_maintenance.py](/vol1/1000/projects/ChatgptREST/tests/test_run_planning_review_maintenance.py)

Docs:

- [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)
- [docs/runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md)

## Intended behavior

### 1. Promotion inventory

`ops/report_evomap_promotion_inventory.py` should expose:

- global counts
- source/status breakdown
- project/status breakdown
- source/reason breakdown
- likely blockers:
  - blank staged promotion reasons
  - sources without active atoms
  - projects without active atoms

This is intended as a diagnosis surface, not an activation engine.

### 2. Maintenance harness

`ops/run_planning_review_maintenance.py` should:

- capture `pre_inventory`
- run the existing planning reviewed maintenance path via `run_cycle`
- capture `post_inventory`
- if allowlists exist, capture `pre/post state` and `pre/post consistency`
- write a single evidence directory with `summary.json`, `cycle_payload.json`, and inventory artifacts

Default mode is refresh-only.

### 3. Systemd timer

`chatgptrest-planning-review-maintenance.timer` should only schedule the refresh-only harness. It should not imply live apply.

## Known live findings

From the live inventory run:

- atoms: `103941`
- active: `202`
- candidate: `25`
- staged: `103172`
- active ratio: `0.001943`
- blank staged promotion reasons: `94759`

Artifacts:

- [promotion inventory json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap/promotion_inventory_20260407_fline/promotion_inventory_20260407T120552Z.json)
- [maintenance summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_maintenance_20260407_fline/20260407T120524Z/summary.json)

## Review questions

1. Does the inventory report expose the right blocker dimensions, or is there a higher-value breakdown missing?
2. Is the harness boundary sufficiently safe, especially around `allowlist_after` discovery and `apply_db_copy` vs `apply_live` semantics?
3. Is refresh-only the correct default for the new timer, or is another cadence/boundary safer?
4. Are the tests sufficient for:
   - refresh-only mode
   - merge + apply-copy mode
   - artifact production
5. Is there any place where this harness could accidentally be misread as a generic auto-promotion mechanism?

## External review status

An external `claudegac` review was attempted through the user-provided resumed session, but the mirror returned:

- `API Error: 402 {"error":"Insufficient credits"}`

So the current review packet is ready for a later rerun once credits are available.
