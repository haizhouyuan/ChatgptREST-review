# Review Repo Lifecycle Finalize Walkthrough v1

Date: 2026-03-17

## Problem

The public review repo lifecycle was incomplete:

- `ops/sync_review_repo.py --sync --push` published a full code mirror
- `--cleanup` only deleted old `review-*` branches
- the stable import branch (`main`) could continue to expose mirrored source code after the review answer had already been collected

That meant the public review repo stayed “hot” longer than intended.

## Change

Implemented a real finalize path in `ops/sync_review_repo.py`:

- new `finalize_review_bundle(...)`
- new `clear_import_branch(...)`
- new CLI mode:

```bash
python ops/sync_review_repo.py --finalize --branch-name review-YYYYMMDD-HHMMSS
```

Behavior:

1. force-pushes the stable import branch to a placeholder-only commit
2. deletes the reviewed remote `review-*` branch
3. logs lifecycle actions locally

`--finalize` now supports zero-argument branch resolution:

- it first reads `REVIEW_SOURCE.json`
- then falls back to the current local branch
- then falls back to the latest pushed `review-*` branch from `artifacts/review_branches.jsonl`

So the normal closeout no longer needs a hand-typed branch name.

Also extended TTL cleanup:

```bash
python ops/sync_review_repo.py --cleanup --clear-import-when-empty
```

So if the last stale review branch is deleted, the stable import branch can also be cleared automatically.

Added full purge mode:

```bash
python ops/sync_review_repo.py --purge-all
```

This deletes every remote `review-*` branch and clears the stable import branch immediately.

## Tests

Ran:

```bash
./.venv/bin/pytest -q tests/test_sync_review_repo.py
```

Result:

- all tests passed
- added coverage for:
  - finalize deletes reviewed branch and clears import branch
  - cleanup can clear import branch after last stale review branch is removed

## Usage Shift

Old lifecycle:

- sync
- review
- maybe later run TTL cleanup

New lifecycle:

- sync
- collect answer
- immediately run `--finalize`
- keep `--cleanup` only as stale-branch safety net

Emergency lifecycle:

- run `--purge-all`
- verify only `review/main` remains and that it is placeholder-only
