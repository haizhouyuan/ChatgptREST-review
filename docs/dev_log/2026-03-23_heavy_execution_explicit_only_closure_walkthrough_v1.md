# 2026-03-23 Heavy Execution Explicit-Only Closure Walkthrough v1

## Why this round existed

Earlier closeout already made the product decision clear:

- do not promote heavy execution
- keep it gated/experimental

But the controller runtime still had one residual mismatch:

- `funnel/build_feature` could still silently fall into `team`

That meant the docs were stricter than the runtime.

## What was changed

The controller was narrowed in two places:

1. execution selection
   - `_resolve_execution_kind()` now requires explicit team intent

2. objective planning
   - `_build_objective_plan()` now only emits `team_delivery` when team intent is explicit

This avoids the inconsistent state where:

- execution is really a normal job
- but objective plan still claims `team_delivery`

## What stayed intentionally unchanged

- explicit team/admin/operator surfaces
- scenario-pack `execution_preference=team`
- explicit `team` / `topology_id` / `executor_lane=team`
- overall `NO-GO` decision for promoting heavy execution

## Validation path

Unit and eval coverage now prove the intended state:

- implicit funnel fallback removed
- explicit topology request still reaches `team`
- parity/coverage packs remain green

This means the heavy-execution boundary is now runtime-correct, not just document-correct.
