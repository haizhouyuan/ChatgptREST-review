# 2026-04-09 PR 200 Selective Merge Review v1

## Scope

Review and merge decision for GitHub PR `#200`.

Canonical PR metadata observed during review:

- title: `feat(finbot): Phase 1-3 — Market Truth, Belief Integrity, Lane Parallelization`
- head branch: `feature/routing-funnel-improvements`
- base branch: `master`
- mergeable state: `CONFLICTING`

## Key finding

The PR metadata and the actual live branch delta had materially diverged.

The PR body still described older finbot/routing work, but the current branch tip relative to `origin/master` only carried four additive governance commits:

1. `55e82b60` `feat(governance): Phase 1b — manifest backfill script`
2. `0c747ffc` `feat(governance): Phase 2 — 6-stage governance daemon`
3. `45223142` `feat(governance): Phase 3 — controlled promotion gate`
4. `0998a3a9` `docs(devlog): artifact governance implementation walkthrough v1`

Attempting to merge the PR wholesale would have been incorrect because:

- the GitHub title/body no longer matched the live branch payload
- the branch was `CONFLICTING`
- the branch carried a stale identity and did not represent a clean, reviewable delta against current `master`

## Decision

Do **not** merge PR `#200` wholesale.

Instead:

- selectively land the still-valid governance commits onto `master`
- preserve the review trail in repo docs
- treat the GitHub PR branch as stale/superseded after the selective land

## Landed commits

The valid governance deltas were cherry-picked onto `master` as-is:

- `5737b264` from `55e82b60`
- `30336426` from `0c747ffc`
- `af000b77` from `45223142`
- `83f18fdc` from `0998a3a9`

These added:

- `ops/manifest_backfill.py`
- `ops/artifact_governance_daemon.py`
- `chatgptrest/governance/promotion.py`
- corresponding tests and walkthrough doc

## Validation

Focused governance validation after selective land:

```bash
./.venv/bin/pytest -q \
  tests/test_manifest_backfill.py \
  tests/test_governance_daemon.py \
  tests/test_governance_promotion.py \
  tests/test_governance_manifest.py \
  tests/test_governance_batch.py
```

Observed result:

- `72 passed`

## Final judgment

PR `#200` should be considered **superseded by selective merge** rather than merged directly.

That is the only honest way to keep:

- `master` reviewable
- the landed governance work traceable
- GitHub PR state aligned with the actual codebase
