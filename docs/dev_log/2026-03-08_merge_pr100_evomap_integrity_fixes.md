## 2026-03-08 Merge PR100 EvoMap Integrity Fixes

### Context

- Worktree: `/vol1/1000/projects/ChatgptREST-merge-pr100-fixes-20260308`
- Branch: `codex/merge-pr100-fixes-20260308`
- Base: `origin/master`
- Integrated feature branch: `feat/evomap-governed-promotion-wp1-6`

This branch was created to merge `PR #100` into a clean integration worktree, apply the blocking integrity fixes identified in review, and rerun the EvoMap regression suite before proposing merge.

### What Changed

#### 1. Promotion execution now respects governance gates

- `PlanExecutor._op_promote()` no longer bypasses `PromotionEngine`.
- Plan execution now routes promote/quarantine through `PromotionEngine` with `commit=False`.
- `PlanExecutor.execute()` now wraps knowledge-base writes in a savepoint and rolls back partial plan effects on failure.
- Promotion operations can now specify `params.target_status`; this makes plan semantics explicit instead of assuming direct staged → active mutation.

Files:

- `chatgptrest/evomap/evolution/executor.py`
- `chatgptrest/evomap/knowledge/promotion_engine.py`
- `chatgptrest/evomap/knowledge/groundedness_checker.py`
- `chatgptrest/evomap/knowledge/db.py`
- `tests/test_evolution_queue.py`
- `tests/test_promotion_engine.py`

#### 2. Relation and sandbox integrity gaps are closed

- `RelationManager.add_provenance()` is now first-writer-preserving (`INSERT OR IGNORE`) instead of overwriting provenance.
- `get_supersession_chain()` now breaks cycles instead of looping forever.
- `RelationManager.connect()` no longer re-initializes schema and commits on every call; schema init is one-time per manager instance.
- `sandbox.merge_back()` now merges atom bundles instead of raw atoms:
  - supporting `document`
  - supporting `episode`
  - `evidence`
  - copyable `entity` endpoints
  - connected `edges` when endpoints are resolvable
  - `provenance`
- Bundle merge is guarded by per-atom savepoints so a failed merge does not leave partial data behind.

Files:

- `chatgptrest/evomap/knowledge/relations.py`
- `chatgptrest/evomap/sandbox.py`
- `tests/test_relations.py`
- `tests/test_sandbox.py`

#### 3. Queue serialization and ingest races are hardened

- `ApprovalQueue` now stores `target_atoms`, `operations`, and approval `conditions` as JSON instead of Python repr strings.
- Queue deserialization now uses `json.loads`.
- `ActivityIngestService._ensure_entity()` now uses `INSERT OR IGNORE` + reselect so duplicate live-ingest races converge on a canonical entity row.

Files:

- `chatgptrest/evomap/evolution/queue.py`
- `chatgptrest/evomap/activity_ingest.py`
- `tests/test_activity_ingest.py`
- `tests/test_evolution_queue.py`

#### 4. Groundedness path logic is portable and symbol extraction is less noisy

- Groundedness code path resolution is now repo-relative by default and can be overridden with `EVOMAP_PROJECT_ROOT`.
- The symbol extractor was narrowed to likely code identifiers (`snake_case`, real `CamelCase`, qualified names) so ordinary sentence-leading words do not poison groundedness scores.

Files:

- `chatgptrest/evomap/knowledge/groundedness_checker.py`
- `tests/test_groundedness.py`
- `tests/test_promotion_engine.py`

### Commits

1. `df7b14f` `fix(evomap): enforce promotion gate in plan execution`
2. `534bf44` `fix(evomap): preserve relation and sandbox integrity`
3. `68a7703` `fix(evomap): tighten groundedness symbol extraction`

### Test Runs

Targeted fix batches:

- `PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_evolution_queue.py`
- `PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_promotion_engine.py`
- `PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_relations.py`
- `PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_sandbox.py`
- `PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_activity_ingest.py`

Broader EvoMap regression:

- `PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_promotion_engine.py tests/test_groundedness.py tests/test_relations.py tests/test_activity_ingest.py`
- `PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_evolution_queue.py tests/test_sandbox.py tests/test_evomap_chain.py tests/test_evomap_e2e.py tests/test_evomap_evolution.py tests/test_evomap_feedback.py tests/test_evomap_signals.py tests/test_phase4_evomap.py tests/test_routes_evomap.py`

### Notes

- GitNexus main index was stale relative to this integration worktree, so symbol-level `impact`/`detect_changes` on the newly merged EvoMap branch returned `target not found` or reflected the main repo's unrelated dirty files instead of this worktree. Change scope was therefore verified with live `git diff` in the integration worktree.
- While integrating, I also verified that the earlier `PR #98` blockers previously noted on `master` had already been fixed upstream and did not need to be reworked here.
