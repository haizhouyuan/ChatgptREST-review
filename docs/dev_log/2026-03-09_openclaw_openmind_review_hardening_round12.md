# 2026-03-09 OpenClaw OpenMind Review Hardening Round 12

## Trigger

The previous ChatGPT review on public branch `review-20260309-121950` still failed for two real reasons:

1. the mirror did not include `skills-src/`, so agent skill behavior could not be audited from branch contents
2. the rebuild baseline still inherited arbitrary plugin `allow/load/install` state from the current host, so the public branch was not a fully deterministic source of truth

It also pointed out stale `18713` defaults still embedded in OpenMind plugin entrypoints/manifests.

## Changes

- added `skills-src` to `ops/sync_review_repo.py` mirror sources
- made `build_plugins_section()` deterministic in `scripts/rebuild_openclaw_openmind_stack.py`
  - stop inheriting arbitrary `current_plugins.allow`
  - stop carrying forward arbitrary `current_plugins.load`
  - stop carrying forward arbitrary `current_plugins.installs`
  - keep only explicitly managed baseline provenance
- aligned OpenMind plugin defaults to the integrated host endpoint `http://127.0.0.1:18711`
  - `openmind-advisor/index.ts`
  - `openmind-memory/index.ts`
  - `openmind-graph/index.ts`
  - `openmind-telemetry/index.ts`
  - `openmind-advisor/openclaw.plugin.json`
- updated review-facing docs to state the new reproducibility contract

## Validation Plan

This round should be validated with:

```bash
./.venv/bin/pytest -q \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_sync_review_repo.py \
  tests/test_openclaw_cognitive_plugins.py

./.venv/bin/python -m py_compile \
  scripts/rebuild_openclaw_openmind_stack.py \
  ops/sync_review_repo.py
```

Then re-sync the public review repo and re-run the external review against the new branch bundle.

## Validation Result

The targeted regressions passed:

```bash
./.venv/bin/pytest -q \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_sync_review_repo.py \
  tests/test_openclaw_cognitive_plugins.py
./.venv/bin/python -m py_compile \
  scripts/rebuild_openclaw_openmind_stack.py \
  ops/sync_review_repo.py
```

The rebuilt baseline also remained live-green after the deterministic plugin change:

- ops proof: `artifacts/verify_openclaw_openmind/20260309T045824Z`
- lean proof: `artifacts/verify_openclaw_openmind/20260309T050038Z`

Both live verifier runs passed after:

- removing arbitrary inherited plugin `allow/load/install` drift
- adopting already-present OpenMind extensions into explicit install records during rebuild
- switching OpenMind plugin defaults to the integrated host endpoint `http://127.0.0.1:18711`
