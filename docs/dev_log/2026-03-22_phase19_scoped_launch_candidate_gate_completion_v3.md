# Phase 19 Scoped Launch Candidate Gate Completion v3

## Why v3 Exists

`v2` corrected the consult-projection evidence chain, but the live default path still read fixed `v1` artifact inputs.

This version completes the cleanup:

- default Phase 19 input resolution now prefers the latest existing artifact
- current default run resolved `Phase 18` from `report_v3`
- runner output is now versioned as the next free artifact name

## Current Correct Artifact

- `docs/dev_log/artifacts/phase19_scoped_launch_candidate_gate_20260322/report_v3.json`
- `docs/dev_log/artifacts/phase19_scoped_launch_candidate_gate_20260322/report_v3.md`

## Current Formal Statement

`Phase 19 v3 = scoped launch candidate gate: GO`

And now that statement is backed by the current default artifact path, not by a manually copied override.
