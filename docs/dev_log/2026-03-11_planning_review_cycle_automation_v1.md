# 2026-03-11 Planning Review Cycle Automation v1

## Scope

Turn the earlier multi-step planning review maintenance flow into one repeatable entrypoint without changing runtime retrieval policy.

Added:

- [run_planning_review_cycle.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_cycle.py)
- [test_run_planning_review_cycle.py](/vol1/1000/projects/ChatgptREST/tests/test_run_planning_review_cycle.py)

Adjusted:

- [planning_review_refresh.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_review_refresh.py)
- [test_planning_review_refresh.py](/vol1/1000/projects/ChatgptREST/tests/test_planning_review_refresh.py)

## What Changed

### 1. Single cycle entrypoint

`ops/run_planning_review_cycle.py` now orchestrates:

1. `run_refresh()`
2. reviewer manifest generation for:
   - `gemini_no_mcp`
   - `claudeminmax`
   - `codex_auth_only`
3. optional merge of reviewer JSON outputs
4. overlay onto the latest full decision baseline
5. optional import/bootstrap apply to:
   - a temp DB copy
   - or live canonical DB

The script writes a single `cycle_summary.json` into the new snapshot dir.

### 2. Refresh now recognizes `v3+` decision baselines

`planning_review_refresh._decision_file()` used to only recognize:

- `planning_review_decisions_v2.tsv`
- `planning_review_decisions.tsv`

It now recognizes `v3+` as well, so refresh no longer silently falls back to the older `v2` baseline after live `v3` exists.

### 3. Refresh chooses the latest prior decision snapshot

`run_refresh()` now separates:

- `previous_snapshot_dir` for role / candidate diffing
- `previous_decision_dir` for decision baseline reuse

This fixes a real maintenance gap:

- if an intermediate `refresh-only` snapshot exists with no decisions,
- the next refresh no longer regresses to the old baseline root,
- it reuses the latest prior refresh snapshot that actually contains decisions.

## Validation

Targeted checks passed:

```bash
./.venv/bin/python -m py_compile \
  chatgptrest/evomap/knowledge/planning_review_refresh.py \
  ops/run_planning_review_cycle.py \
  tests/test_planning_review_refresh.py \
  tests/test_run_planning_review_cycle.py

./.venv/bin/pytest -q \
  tests/test_planning_review_refresh.py \
  tests/test_run_planning_review_cycle.py \
  tests/test_compose_planning_review_decisions.py \
  tests/test_planning_review_plane.py
```

Real refresh-only run:

```bash
./.venv/bin/python ops/run_planning_review_cycle.py
```

Result:

- snapshot: [20260311T042646Z](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T042646Z)
- `decision_source_dir = artifacts/monitor/planning_review_plane_refresh/20260311T032642Z`
- `review_needed_docs = 0`
- `pack_items = 0`

That is the intended idempotent state after the already-applied `planning_review_decisions_v3` baseline.

## Boundary

This round did **not**:

- change runtime retrieval defaults
- broaden `review_verified_fast_path`
- write new planning decisions into live canonical DB

It only hardened the maintenance loop around the existing planning reviewed slice.
