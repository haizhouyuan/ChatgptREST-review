# Planning Runtime Pack Release Bundle V1

## Scope

This is a coordination-only sidecar launch-readiness artifact. It does not change runtime defaults, retrieval behavior, or `#114` boundaries.

## Added

- `ops/build_planning_runtime_pack_release_bundle.py`
- `tests/test_build_planning_runtime_pack_release_bundle.py`

## Purpose

Assemble one offline release bundle for the planning reviewed runtime pack by combining:

- the current reviewed runtime pack export
- the latest offline golden-query validation
- the latest sensitivity/content-safety audit
- the latest observability sample pack

## Outputs

The bundle writes:

- `release_bundle_manifest.json`
- `component_paths.json`
- `rollback_runbook.md`
- `README.md`

## Decision semantics

The bundle is intentionally conservative.

- `release_readiness_ready` must be green
- `offline_validation_ok` must be green
- `observability_schema_present` must be green
- `sensitivity_clear` must be green

If sensitivity still flags reviewed atoms or docs, the bundle stays `ready_for_explicit_consumption=false` and records `sensitivity_manual_review_required` in `blocking_findings`.

## Current live result

The live run currently stays blocked by sensitivity review, not by pack structure:

- release-readiness: green
- offline validation: green
- observability schema: present
- sensitivity: not green (`2` flagged atoms)

That is the intended outcome for a sidecar release bundle: it surfaces the hold point without changing runtime behavior.
