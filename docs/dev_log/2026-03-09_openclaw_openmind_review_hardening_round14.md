# 2026-03-09 OpenClaw OpenMind Review Hardening Round 14

## Trigger

Gemini review still failed after the public branch became self-consistent, but the failure was input-path specific:

- raw GitHub URLs were reported as unreadable from Gemini
- Gemini code import appears to operate on the review repo root/default branch rather than a timestamp review branch URL
- the public review repo default branch was still an old timestamp branch, so repo-root import could lag behind the newest review package

## Changes

- updated `ops/sync_review_repo.py` so each sync now publishes the same package to:
  - the timestamped `review-*` branch for branch-pinned external review
  - a stable import branch (`main`) for Gemini code import
- added a best-effort GitHub API step to set the review repo default branch to the stable import branch
- updated the topology review bundle to state that Gemini should read the latest package from the review repo root/default import branch
- added a regression test covering the dual-push + default-branch update contract

## Validation Plan

Run:

```bash
./.venv/bin/pytest -q tests/test_sync_review_repo.py
./.venv/bin/python -m py_compile ops/sync_review_repo.py
```

Then:

1. re-sync the public review repo
2. verify the review repo default branch is `main`
3. re-submit Gemini review using the repo root import path instead of a branch tree URL
