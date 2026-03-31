# 2026-03-13 Issue 174 Planning Groundedness Fast-Path Fix v2

This version supersedes `..._v1` after reviewer-side rerun verification.

## Additional Finding From PR Review

`v1` fixed the fresh no-anchor bootstrap path, but it did not clean up atoms
that had already been incorrectly promoted by the old fast path.

Reproduced behavior before this patch:

- atom already stored as:
  - `promotion_status=active`
  - `promotion_reason=planning_bootstrap_review_verified`
  - `groundedness=1.0`
- rerunning `apply_bootstrap_allowlist()` on the same no-anchor content
  demoted the atom back to `candidate`
- but left `groundedness=1.0` behind

That left stale groundedness in canonical state and could still mislead later
reporting or retrieval logic that reads the numeric score.

## Additional Change

For the `no runtime grounding anchors` branch:

- explicitly rewrite the atom row to:
  - `promotion_status=candidate`
  - `promotion_reason=planning_bootstrap:service_candidate`
  - `groundedness=0.0`

The deferred TSV still records:

- `reason=groundedness_unknown_no_runtime_anchors`
- `groundedness=unknown`

This keeps human-readable output as `unknown` while normalizing the stored
numeric score back to the safe floor.

## Added Regression Coverage

New test:

- `test_apply_bootstrap_allowlist_clears_stale_groundedness_on_no_anchor_rerun`

It seeds the exact bad historical state from the old fast path and verifies that
the rerun leaves:

- `promotion_status=candidate`
- `promotion_reason=planning_bootstrap:service_candidate`
- `groundedness=0.0`

## Validation

```bash
python3 -m py_compile chatgptrest/evomap/knowledge/planning_review_plane.py tests/test_planning_review_plane.py
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_planning_review_plane.py tests/test_report_planning_review_state.py tests/test_export_planning_reviewed_runtime_pack.py tests/test_report_planning_review_consistency.py tests/test_run_planning_review_priority_cycle.py
```

Both commands passed after the patch.
