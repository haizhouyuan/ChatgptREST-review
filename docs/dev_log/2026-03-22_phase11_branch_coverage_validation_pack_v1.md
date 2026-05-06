# Phase 11 Branch Coverage Validation Pack v1

## Goal

Validate the branch families that were explicitly outside earlier pack-route
 and public-route validation phases:

- `clarify`
- `kb_direct`
- `no scenario_pack` fallback
- `team fallback`

This phase exists to close the most important remaining route-shape holes before
 declaring the current validation package launch-ready.

## Scope

This phase validates four targeted branch surfaces:

1. `/v3/agent/turn` clarify branch for a covered planning sample
2. `ControllerEngine.ask()` KB direct-answer branch
3. controller planning fallback without a canonical `scenario_pack`
4. controller execution-kind fallback to `team`

## What This Phase Is

- `targeted branch-family validation`
- a complement to Phase 9 and Phase 10
- focused on omitted control-flow families, not broad happy-path samples

## What This Phase Is Not

- not full-stack business-sample validation
- not dynamic OpenClaw replay
- not artifact delivery or knowledge writeback validation

## Dataset

Dataset file:

- [phase11_branch_coverage_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase11_branch_coverage_samples_v1.json)

Covered cases:

1. `agent_v3_clarify`
2. `controller_kb_direct`
3. `controller_no_pack_fallback`
4. `controller_team_fallback`

## Implementation

Core validator:

- [branch_coverage_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/branch_coverage_validation.py)

Runner:

- [run_branch_coverage_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_branch_coverage_validation.py)

Tests:

- [test_branch_coverage_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_branch_coverage_validation.py)

## Acceptance

Phase 11 passes only when:

- clarify samples remain on the public `needs_followup/clarify` seam
- KB direct samples complete with `provider=kb`
- no-pack fallback samples match the current controller fallback route
- team fallback samples resolve to `execution_kind=team`
