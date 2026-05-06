# 2026-03-11 Planning Runtime Pack Sensitivity Manual Review v1

## Why

The planning reviewed runtime pack was structurally ready for explicit
consumption, but the live release bundle still stayed blocked by a very small
manual-review hold:

- `flagged_atoms = 2`
- `blocking_findings = ["sensitivity_manual_review_required"]`

Those hits were not personal data or secret material leaks. They were internal
planning atoms that happened to contain the token `合同`.

## What Changed

Added a reviewed disposition file:

- `ops/data/planning_runtime_pack_sensitivity_review_v1.json`

Extended the sensitivity audit so it now distinguishes:

- raw token hits
- manually approved internal-opt-in hits
- unresolved blocking hits

Raw hits are still recorded. Only unresolved hits keep the pack blocked.

## Result

After re-running the live audit against:

- `artifacts/monitor/planning_reviewed_runtime_pack/20260311T083052Z`

the new audit summary became:

- `flagged_atoms = 2`
- `approved_flagged_atoms = 2`
- `unresolved_flagged_atoms = 0`
- `ok = true`

Then the release bundle was rebuilt and turned green:

- `artifacts/monitor/planning_runtime_pack_release_bundle/20260311T110948Z`
- `ready_for_explicit_consumption = true`
- `blocking_findings = []`

## Boundary

This change does not alter default retrieval.

It only turns a documented manual-review hold into an explicit reviewed
disposition so the planning runtime pack can move from blocked sidecar state to
approved explicit-consumption state.
