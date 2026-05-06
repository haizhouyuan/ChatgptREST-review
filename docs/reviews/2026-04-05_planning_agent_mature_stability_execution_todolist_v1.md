# 2026-04-05 Planning Agent Mature Stability Execution Todo List v1

## Goal

Close the remaining gap between `W1-W6 completed` and a defensible `mature stability` claim.

This batch is only complete if:

1. fresh live evidence exists on current code
2. old synthetic/partial packs are rebound on current code
3. northbound planning truth is authority-first on server and CLI surfaces
4. planning memory writeback becomes durable handoff truth
5. one unified manifest can fail-close the mature-stability claim

## Todo

### T1. Freeze Red-Team Review Into Repo

Work:

1. Preserve the `Claude G AC` red-team review in repo docs.
2. Freeze the tightened tranche and acceptance rules.

Acceptance:

1. Repo contains a versioned review doc with run id, verdict, corrections, and adopted decisions.
2. Repo contains this executable todo list as the sole batch contract for the closure work.

### T2. Add Authority-First Planning Query To Server And CLI

Work:

1. REST `GET /v3/agent/session/{session_id}` must expose `planning_query.snapshot` when a planning task is present.
2. REST `GET /v3/agent/planning/task/{task_id}` must expose `planning_query.snapshot`.
3. REST `GET /v3/agent/planning/tasks` must expose `planning_query.items`.
4. CLI query scripts must expose the same `planning_query` contract.
5. Compatibility mirrors `planning_task` / `planning_tasks` must remain.

Acceptance:

1. Every northbound planning read surface explicitly exposes:
   - `authority`
   - `read_mode`
   - `canonical_field`
2. REST/CLI tests prove the contract exists and points to `planning_query.*`.
3. Existing compatibility fields remain intact for older callers.

### T3. Make Planning Memory Writeback Durable Handoff Truth

Work:

1. Persist a narrowed `memory_writeback_receipt` into the planning checkpoint/handoff path.
2. Surface that receipt through:
   - planning task REST read
   - planning task CLI read
   - session planning snapshot when present
3. Persist no-op / skipped / failed receipts with explicit reasons instead of silently dropping them.

Acceptance:

1. A cross-end handoff can answer:
   - was writeback attempted
   - what categories were requested
   - what writes were applied
   - why it was skipped or failed
2. Tests cover successful and non-successful receipt projection.

### T4. Re-Run Fresh Current-Code Live Evidence

Work:

1. Re-run the canonical `Gemini` live completion gate on current code.
2. Re-run the canonical `ChatGPT` live completion gate on current code.
3. Re-run a current-code cancel consistency probe.

Acceptance:

1. Fresh versioned artifact directories exist and are committed.
2. Review docs freeze exact run ids / artifact paths / pass-fail boundaries.
3. If `ChatGPT` cannot be freshly revalidated, the manifest must explicitly exclude it from the mature-stability claim.

### T5. Re-Bind Current-Code Offline Packs

Work:

1. Re-export fresh `7/7 + branch` acceptance evidence on current code and commit it.
2. Re-export fresh `3/3` continuity evidence on current code and commit it.
3. Re-export fresh `5/5` P0 evidence on current code.
4. Ensure at least one `P0` scenario runs without patched knowledge ingress / memory writeback.

Acceptance:

1. New versioned artifact directories exist for all three packs.
2. `3/3` is committed to git for the first audited baseline in this closure line.
3. `5/5` report explicitly marks which scenario is unmocked for `W4` ingress/writeback.
4. Synthetic scope is still allowed where intended, but each pack declares its exact scope.

### T6. Export Unified Mature-Stability Gate

Work:

1. Add a unified exporter that binds:
   - fresh live gate evidence
   - fresh cancel probe evidence
   - fresh `7/7 + branch`
   - fresh `3/3`
   - fresh `5/5`
   - authority-first server truth coverage
   - durable writeback truth coverage
2. Fail-closed when any required evidence is missing or stale.
3. Emit one manifest and one markdown report.

Acceptance:

1. One manifest can answer pass/fail without reading multiple reviews manually.
2. The gate clearly states provider scope:
   - both `Gemini` and `ChatGPT`, or
   - only the provider(s) freshly revalidated in this batch
3. The report explicitly distinguishes:
   - live evidence
   - synthetic contract packs
   - unmocked `W4` proof points

### T7. Freeze Documentation And Program Status

Work:

1. Write execution review(s) for this closure batch.
2. Write walkthrough(s) with commands, artifact paths, and decisions.
3. Update the master status doc to the new frozen version.
4. Record the exact mature-stability claim boundary and exclusions.

Acceptance:

1. A new master doc supersedes `v59`.
2. Review docs and walkthroughs are versioned and link to committed artifacts.
3. The frozen claim cannot be mistaken for a broader claim than the evidence supports.

### T8. Validation And Closeout

Work:

1. Run targeted tests for the touched surfaces.
2. Run `py_compile` on touched Python modules.
3. Run `check_doc_obligations.py` on the changed files.
4. Run `gitnexus_detect_changes(scope=\"staged\")` before each commit batch.
5. Execute repo closeout wrapper at the end.

Acceptance:

1. Every meaningful code/doc batch is committed independently.
2. Closeout completes successfully against this batch's diff.
3. No unrelated dirty files are reverted or absorbed.

## Completion Rule

This todo list is complete only when `T1-T8` are all done and the unified mature-stability manifest is green with an explicit frozen provider scope.
