# 2026-03-11 Execution Experience Review Validation-Failure Fixture Bundle v1

## Goal

Add a tracked fixture bundle for the two strict validation-failure gates that
mainline just added to the execution experience review cycle:

- `--require-complete-reviews`
- `--require-valid-reviews`

This round stays in `fixture / test / docs` only.

## Artifact root

- `docs/dev_log/artifacts/execution_experience_review_validation_failure_fixture_bundle_20260311/`

## Included files

1. `experience_candidates_v1.json`
2. `reviewer_manifest_v1.json`
3. `gemini_no_mcp_only_v1.json`
4. `gemini_no_mcp_invalid_decision_v1.json`
5. `validation_failed_complete_required_summary_v1.json`
6. `validation_failed_valid_required_summary_v1.json`
7. `README.md`

## What this bundle encodes

The bundle anchors a single deterministic candidate set and then records two
different fail-fast outcomes:

1. `require_complete_reviews=True`
   with only `gemini_no_mcp` replying
2. `require_valid_reviews=True`
   with `gemini_no_mcp` replying using an invalid decision value

The tracked expected summaries store both:

- normalized `cycle_summary.json`
- normalized `review_output_validation_summary.json`

That keeps the bundle useful both for gate behavior and for downstream
inspection of validator details.

## Why this matters

Mainline already owns the execution review validation gates themselves. What
was still missing was a tracked, reviewable sample bundle that demonstrates how
the cycle fails when those gates are enabled.

This bundle fills that gap without touching cycle/orchestration/runtime code.

## Validation

The bundle is consumed by:

- [test_execution_experience_review_validation_failure_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_review_validation_failure_fixture_bundle.py)

The regression:

1. seeds the same one-candidate knowledge DB used by the existing cycle tests
2. runs `run_cycle(...)` once in refresh-only mode
3. compares the generated candidate export and normalized reviewer manifest
   against the tracked fixtures
4. re-runs the cycle with tracked failing reviewer JSON
5. compares the normalized failure summaries against the tracked expected JSON

## Boundary

This round does **not**:

- modify `ops/run_execution_experience_review_cycle.py`
- modify `ops/validate_execution_experience_review_outputs.py`
- change the live `TraceEvent` contract
- add reviewer orchestration
- do runtime adoption
- promote anything into active knowledge
