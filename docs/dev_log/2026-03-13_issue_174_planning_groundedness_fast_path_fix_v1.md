# 2026-03-13 Issue 174 planning groundedness fast-path fix v1

## Context

Open issue `#174` mixed several concerns together. A code-backed review against the current repo showed:

- `chatgptrest/kernel/policy_engine.py` already blocks `confidential -> external`, so that cited bug is not current.
- `chatgptrest/evomap/knowledge/planning_review_plane.py` still contained a real correctness hole:
  when a planning atom had no runtime grounding anchors, `apply_bootstrap_allowlist()` promoted it from `candidate` to `active` and stamped `groundedness=1.0`.

That behavior overstated groundedness and bypassed the normal promotion gate.

## Blast radius

GitNexus CLI impact checks on `2026-03-13`:

- `apply_bootstrap_allowlist`: `LOW`
  - direct callers: `ops/run_planning_review_cycle.py:run_cycle`, `ops/import_planning_review_plane_to_evomap.py:main`
- `_has_runtime_grounding_anchors`: `LOW`
  - direct caller: `apply_bootstrap_allowlist`

No high-risk runtime fanout was detected.

`gitnexus_detect_changes()` was attempted before commit but the MCP call timed
out twice against the current `ChatgptREST` index on this machine. For this
slice the scope check therefore falls back to:

- low-risk symbol impact on the two touched functions
- staged diff restricted to:
  - `chatgptrest/evomap/knowledge/planning_review_plane.py`
  - `tests/test_planning_review_plane.py`
  - `docs/dev_log/2026-03-13_issue_174_planning_groundedness_fast_path_fix_v1.md`

## Change

Implemented a fail-closed behavior for the no-anchor case:

- no runtime grounding anchors no longer imply `ACTIVE`
- no synthetic `groundedness=1.0`
- the atom stays `candidate`
- the bootstrap output records a deferred row with:
  - `reason=groundedness_unknown_no_runtime_anchors`
  - `groundedness=unknown`

## Tests

Updated tests to cover both sides:

- anchored planning content can still promote through bootstrap
- generic no-anchor planning content stays deferred/candidate

Targeted test command:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_planning_review_plane.py
```

## Issue handling

Recommended queue treatment after this slice:

- close `#175` as audit record preserved in docs/artifacts
- close `#173` as blueprint/program issue, keep the narrative in docs/comments only
- keep `#174` as the remaining design anchor only if more bounded child slices are expected; otherwise close it after linking the concrete follow-up PR
