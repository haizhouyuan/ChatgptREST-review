# 2026-03-09 OpenClaw OpenMind Review Hardening Round 13

## Trigger

The latest public-branch review still found one remaining review-facing inconsistency:

- `ops/nginx_openmind.conf` still proxied `/v2/advisor/` to `127.0.0.1:18713`
- the blueprint still listed stale `18713` integrated-host wording as an open gap

That was enough to keep the public branch from being a single, self-consistent source of truth for the integrated-host baseline.

## Changes

- aligned `ops/nginx_openmind.conf` to the integrated-host endpoint `127.0.0.1:18711`
- extended `tests/test_openclaw_cognitive_plugins.py` so review-facing OpenMind entrypoints now include the nginx sample config in the `18711` assertion
- removed the now-resolved `18713` wording from the blueprint gap list
- updated the public review bundle to cite the nginx ingress sample as part of the review evidence set

## Validation

Run:

```bash
./.venv/bin/pytest -q \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_sync_review_repo.py \
  tests/test_verify_openclaw_openmind_stack.py
```

Then re-sync the public review repo and restart the external review against the new branch bundle.

## Validation Result

The targeted public-branch regressions passed:

```bash
./.venv/bin/pytest -q \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_sync_review_repo.py \
  tests/test_verify_openclaw_openmind_stack.py
```

This round intentionally did not require another live topology rebuild because the change set only touched:

- review-facing nginx ingress sample configuration
- review bundle / blueprint wording
- the regression test that locks the integrated-host port contract
