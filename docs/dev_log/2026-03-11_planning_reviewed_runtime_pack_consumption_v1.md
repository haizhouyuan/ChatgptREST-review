# 2026-03-11 Planning Reviewed Runtime Pack Consumption v1

## Purpose

This note explains how the mainline runtime can **explicitly** consume the planning reviewed runtime pack later.

It does **not** imply that planning is enabled in default retrieval today.

## Expected Input

The pack produced by [export_planning_reviewed_runtime_pack.py](/vol1/1000/projects/ChatgptREST/ops/export_planning_reviewed_runtime_pack.py):

- `manifest.json`
- `docs.tsv`
- `atoms.tsv`
- `retrieval_pack.json`
- `smoke_manifest.json`

## Explicit Consumption Contract

Mainline runtime should treat the pack as an **external reviewed slice** and only consume it when a dedicated opt-in hook is enabled.

Recommended consumption flow:

1. Read `manifest.json`
2. Assert:
   - `scope.opt_in_only == true`
   - `scope.default_runtime_cutover == false`
   - `checks.allowlist_live_coverage_ok == true`
   - `checks.bootstrap_allowlist_alignment_ok == true`
   - `checks.staged_atoms_excluded_ok == true`
3. Read `retrieval_pack.json`
4. Restrict planning retrieval to:
   - `doc_ids` from the pack
   - `atom_ids` from the pack
5. Label the resulting source as explicit planning reviewed slice, not generic planning corpus

## Non-Goals

This pack is **not** intended to:

- change default retrieval behavior
- import all reviewed planning docs into default runtime context
- expose staged-only planning atoms
- replace the review-plane or bootstrap maintenance workflow

## Smoke Path

Before wiring a runtime hook, mainline can run an explicit smoke against:

- `manifest.json`
- `retrieval_pack.json`
- `smoke_manifest.json`

The smoke should verify:

- all exported docs are allowlisted
- all exported atoms are `active/candidate`
- no staged-only planning atoms are introduced through the pack
