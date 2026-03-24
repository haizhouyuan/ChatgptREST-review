# 2026-03-11 Execution Experience Review Validation-Failure Fixture Bundle Walkthrough v1

## Purpose

This walkthrough explains how the tracked validation-failure fixture bundle maps
onto the strict execution experience review gates that mainline added.

## Files and roles

- [experience_candidates_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_validation_failure_fixture_bundle_20260311/experience_candidates_v1.json)
  records the deterministic one-candidate export used by both gate failures
- [reviewer_manifest_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_validation_failure_fixture_bundle_20260311/reviewer_manifest_v1.json)
  records the normalized three-reviewer manifest emitted by the cycle
- [gemini_no_mcp_only_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_validation_failure_fixture_bundle_20260311/gemini_no_mcp_only_v1.json)
  is the partial-but-valid reviewer output used to trigger
  `require_complete_reviews=True`
- [gemini_no_mcp_invalid_decision_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_validation_failure_fixture_bundle_20260311/gemini_no_mcp_invalid_decision_v1.json)
  is the structurally invalid reviewer output used to trigger
  `require_valid_reviews=True`
- [validation_failed_complete_required_summary_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_validation_failure_fixture_bundle_20260311/validation_failed_complete_required_summary_v1.json)
  records the normalized cycle + validation summaries for the completeness gate
- [validation_failed_valid_required_summary_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_validation_failure_fixture_bundle_20260311/validation_failed_valid_required_summary_v1.json)
  records the normalized cycle + validation summaries for the structural-validity gate

## Normalization used by the regression

The cycle writes absolute temp paths into:

- reviewer instructions
- candidate export paths
- review pack paths
- backlog summary paths

The regression normalizes those path-bearing fields down to basenames before
comparing against the tracked JSON fixtures. That keeps the bundle stable while
still exercising the real `run_cycle(...)` code path.

## Test-local shim

The validator module currently imports the public helper:

- `load_expected_reviewers`

but still calls the older private alias:

- `_load_expected_reviewers`

To stay inside the approved `fixture / test / docs` slice, this round does not
patch the validator source. Instead, the new regression adds a test-local shim:

```python
validation_module._load_expected_reviewers = load_expected_reviewers
```

That allows the strict-gate fixtures to run against the current code path
without changing runtime behavior in this slice.

## Expected governance result

The bundle demonstrates two different failure modes:

1. completeness failure:
   one reviewer replies cleanly, but two expected reviewers are missing
2. structural-validity failure:
   one reviewer replies, but the decision value is outside the allowed set

In both cases the cycle terminates with:

- `ok = false`
- `mode = validation_failed`

and writes a validator summary before raising.

## Why this is still non-conflicting

This bundle does not edit:

- `ops/run_execution_experience_review_cycle.py`
- `ops/validate_execution_experience_review_outputs.py`
- review orchestration / runtime adoption / promotion paths

It only adds tracked fixtures, one regression file, and explanatory docs around
the already-approved gate surface.
