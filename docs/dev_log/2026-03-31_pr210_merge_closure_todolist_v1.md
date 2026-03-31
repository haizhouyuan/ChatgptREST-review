# PR 210 Merge Closure Todo

**Date:** 2026-03-31
**PR:** `#210`
**Owner:** Codex re-review / merge closure

## Goal

Bring PR 210 to a mergeable, truthful, and clean foundation state against current `master`.

## Standards

1. Branch must merge cleanly onto current `master`.
2. Task runtime code must import and route correctly on the merged result.
3. Tests must pass on the merged result, not only on a detached PR snapshot.
4. Runtime-generated task workspace residue must not be committed or leaked into repo root during tests.
5. Scope claims must match implementation:
   - Phases 0-3 may be claimed as implemented if verified.
   - Phase 4/5 may only be claimed as scaffold/projection until real completion and work-memory integration exists.

## Checklist

- [x] Re-review latest PR head after author fixes
- [x] Confirm prior import, router, field drift, and DB init issues are fixed
- [ ] Merge current `master` into PR branch and resolve conflicts
- [ ] Remove committed runtime task workspace artifacts from PR
- [ ] Stop tests from dirtying repo with task workspace residue
- [ ] Add API-level route smoke for `/v1/tasks`
- [ ] Correct walkthrough wording so scope is truthful
- [ ] Re-run task runtime tests on merged branch
- [ ] Re-run targeted app import / route registration checks
- [ ] Push repaired PR branch
- [ ] Update PR review verdict
- [ ] Merge PR
- [ ] Sync post-merge `master` and record closure

## Acceptance Gate

PR 210 is mergeable only if all of the following are true:

- `pytest -q tests/test_task_runtime.py` passes on the merged result
- `create_app()` exposes `/v1/tasks` routes on the merged result
- No tracked `tasks/<task_id>/...` runtime artifacts remain in the diff
- Walkthrough and PR title/body do not overclaim Phase 4/5
- Merge conflicts against `master` are resolved without dropping current `master` fixes
