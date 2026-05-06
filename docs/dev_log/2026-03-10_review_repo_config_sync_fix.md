# 2026-03-10 Review Repo Config Sync Fix

## Context

External ChatGPT Pro review on branch `review-20260310-171256` referenced
[`config/agent_roles.yaml`](../..//config/agent_roles.yaml) via the role-pack
review bundle, but the public review branch returned `404` for that file.

This was a review-input completeness bug, not a runtime bug. The sync policy in
[`ops/sync_review_repo.py`](../../ops/sync_review_repo.py) did not include the
`config/` directory, so the public mirror omitted the role-pack configuration
that the bundle asked reviewers to inspect.

## Change

- Added `config` to `SOURCE_DIRS` in `ops/sync_review_repo.py`
- Added tests to ensure:
  - `config` remains part of the default sync set
  - `config/agent_roles.yaml` is copied into the review repo

## Validation

Ran:

```bash
./.venv/bin/pytest -q tests/test_sync_review_repo.py
./.venv/bin/python -m py_compile ops/sync_review_repo.py tests/test_sync_review_repo.py
```

Both passed.

## Outcome

Future public review branches will include `config/agent_roles.yaml`, so the
role-pack bundle is self-consistent for external reviewers.
