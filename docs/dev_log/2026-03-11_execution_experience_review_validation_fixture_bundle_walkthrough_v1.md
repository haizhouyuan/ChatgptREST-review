# 2026-03-11 Execution Experience Review Validation Fixture Bundle Walkthrough v1

## Purpose

This walkthrough explains how the tracked validation fixture bundle maps onto
the current execution experience review governance surface.

## Files and roles

- [experience_candidates_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_validation_fixture_bundle_20260311/experience_candidates_v1.json)
  defines the candidate universe
- [reviewer_manifest_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_validation_fixture_bundle_20260311/reviewer_manifest_v1.json)
  defines the expected reviewer lanes
- [gemini_no_mcp_valid_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_validation_fixture_bundle_20260311/gemini_no_mcp_valid_v1.json)
  is the clean/valid reviewer example
- [claudeminmax_unknown_candidate_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_validation_fixture_bundle_20260311/claudeminmax_unknown_candidate_v1.json)
  injects an unknown candidate
- [codex_auth_only_invalid_decision_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_validation_fixture_bundle_20260311/codex_auth_only_invalid_decision_v1.json)
  injects an invalid decision value
- [codex_auth_only_duplicate_candidate_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_validation_fixture_bundle_20260311/codex_auth_only_duplicate_candidate_v1.json)
  injects a duplicate candidate row
- [validation_summary_expected_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_validation_fixture_bundle_20260311/validation_summary_expected_v1.json)
  records the expected validator output

## Normalization step used by the regression

The tracked fixture filenames are descriptive, but the validator derives the
reviewer name from the input file stem.

To keep both properties at once, the regression test:

1. copies the fixture payloads into temp files named:
   - `gemini_no_mcp.json`
   - `claudeminmax.json`
   - `codex_auth_only.json`
2. merges the two Codex-specific failure-mode fixtures into the single
   `codex_auth_only.json` reviewer payload
3. runs `validate_review_outputs(...)`
4. normalizes path fields down to basenames
5. compares the full summary against the tracked expected JSON

## Expected governance result

The tracked expected summary demonstrates:

- `complete = true`
  because all expected reviewers are present
- `structurally_valid = false`
  because unknown candidate / invalid decision / duplicate row all appear
- `coverage_by_review_count = {"0": 1, "2": 2}`
  which means one candidate remains uncovered by any valid review item
- per-reviewer validation counts remain inspectable without running the live
  experience review cycle

## Why this is still non-conflicting

This fixture bundle does not edit:

- `ops/run_execution_experience_review_cycle.py`
- merge/orchestration logic
- runtime retrieval or promotion paths

It only adds a tracked regression surface around the existing validator.
