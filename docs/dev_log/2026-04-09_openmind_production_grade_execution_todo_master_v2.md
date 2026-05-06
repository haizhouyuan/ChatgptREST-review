# 2026-04-09 OpenMind Production-Grade Execution TODO Master v2

## Purpose

Freeze the execution ledger after completing:

1. open PR triage and selective merge
2. master cleanliness and repo governance cleanup
3. `G0` language/exit freeze
4. `G1` watch-window ledger and graduation gate scaffolding

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

- [x] inspect all open PRs
- [x] compare PR title/body against actual branch delta
- [x] decide:
  - reject wholesale merge
  - or selectively land safe commits
- [x] record the decision in a versioned review/walkthrough doc

### P0.2 Dirty master classification

- [x] classify modified tracked files
- [x] classify untracked docs/scripts
- [x] classify local residue (`tasks/`, screenshots, empty dirs)
- [x] decide what should be:
  - committed
  - ignored
  - left untouched

### P0.3 Master cleanup

- [x] land coherent dirty tracked changes if they are valid repo work
- [x] land any untracked docs/scripts that belong in repo history
- [x] add ignore rules for workspace-local residue if appropriate
- [x] leave unrelated external work untouched
- [x] reach a clean or intentionally bounded master working tree state

## Phase G0: Language And Exit-Criteria Freeze

- [x] create canonical graduation contract doc
- [x] update over-claiming docs/closeouts to distinguish launch vs graduation
- [x] align operator-facing wording

## Phase G1: Watch-Window Automation And Graduation Ledger

- [x] add daily watch-window ledger runner
- [x] add final graduation decision runner
- [x] add runbook steps for daily canary review
- [x] produce first live watch-window artifact set

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

- [x] focused pytest suites pass for G0/G1
- [x] first live watch-window artifacts regenerated from current code
- [ ] before/after DB or artifact metrics exist for remaining bulk data movement phases
- [ ] final repo closeout uses scoped diff if unrelated dirty files remain outside this wave
