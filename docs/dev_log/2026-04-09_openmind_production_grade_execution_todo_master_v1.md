# 2026-04-09 OpenMind Production-Grade Execution TODO Master v1

## Purpose

Freeze the full execution ledger for:

1. open PR triage and selective merge
2. master cleanliness and repo governance cleanup
3. `G0` through `G6` execution from the production-grade gap plan

This file exists so the execution sequence does not depend on chat context.

## Guardrails

- Do not merge stale PR branches wholesale when GitHub metadata and actual branch delta diverge.
- Do not discard unrelated dirty work without first classifying it as:
  - landable repo work
  - local residue that should be ignored
  - user/agent work that must remain untouched
- Keep launch/go-live language honest:
  - `canary-ready`
  - `watch-window active`
  - `go-live ready`

## Phase 0: Merge And Cleanliness Front

### P0.1 Open PR audit

- [ ] inspect all open PRs
- [ ] compare PR title/body against actual branch delta
- [ ] decide:
  - reject wholesale merge
  - or selectively land safe commits
- [ ] record the decision in a versioned review/walkthrough doc

### P0.2 Dirty master classification

- [ ] classify modified tracked files
- [ ] classify untracked docs/scripts
- [ ] classify local residue (`tasks/`, screenshots, empty dirs)
- [ ] decide what should be:
  - committed
  - ignored
  - left untouched

### P0.3 Master cleanup

- [ ] land coherent dirty tracked changes if they are valid repo work
- [ ] land any untracked docs/scripts that belong in repo history
- [ ] add ignore rules for workspace-local residue if appropriate
- [ ] leave unrelated external work untouched
- [ ] reach a clean or intentionally bounded master working tree state

## Phase G0: Language And Exit-Criteria Freeze

- [ ] create canonical graduation contract doc
- [ ] update over-claiming docs/closeouts to distinguish launch vs graduation
- [ ] align operator-facing wording

## Phase G1: Watch-Window Automation And Graduation Ledger

- [ ] add daily watch-window ledger runner
- [ ] add final graduation decision runner
- [ ] add runbook steps for daily canary review
- [ ] produce first live watch-window artifact set

## Phase G2: Packet Completeness Hardening

- [ ] audit degraded packet sources
- [ ] fix or explicitly narrow:
  - `personal_graph_empty`
  - `memory_identity_missing`
  - `captured_memory_identity_missing`
  - `work_memory_identity_partial`
- [ ] extend packet harness with raw/adjusted degraded ratios and source distribution

## Phase G3: Live Crystal Evidence

- [ ] verify real `user_correction` writeback on canary cohort
- [ ] run live crystal generation review on real DB contents
- [ ] emit shadow evidence pack with manual review notes

## Phase G4: Recall Expansion To Cohort-Reliable

- [ ] expand recall goldset beyond current narrow benchmark
- [ ] add positive / negative / boundary / stress cases
- [ ] keep entity-grade vs bridge-recall labeling explicit
- [ ] continue targeted re-ingest / boost only where source material exists

## Phase G5: Promotion Backlog Reduction

- [ ] freeze rollout-critical source/project families
- [ ] add production-grade promotion SLO report
- [ ] reduce staged-only backlog for critical families
- [ ] keep warning bounded and explainable if not yet fully cleared

## Phase G6: Graduation Gate

- [ ] re-run regression, health, scorecard, watch ledger finalizer
- [ ] verify no fail domains and no unapproved warns
- [ ] emit canonical graduation artifact

## Validation Checklist

- [ ] targeted/focused pytest suites pass for each changed area
- [ ] production artifacts are regenerated from current code
- [ ] before/after DB or artifact metrics exist for bulk data movement
- [ ] final repo closeout uses scoped diff if unrelated dirty files remain outside this wave

## Notes

- This file is a living execution ledger for this wave.
- New findings should be appended as concrete check items, not held only in transient agent context.
