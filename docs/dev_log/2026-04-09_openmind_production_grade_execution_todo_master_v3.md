# 2026-04-09 OpenMind Production-Grade Execution TODO Master v3

## Purpose

Freeze the final execution ledger after completing the full production-grade plan wave.

## Final status

- `canary-ready`
- `watch-window active`
- `graduation gate executed`
- `graduation decision = hold`

## Phase 0: Merge And Cleanliness Front

- [x] inspect all open PRs
- [x] compare PR intent against actual branch delta
- [x] selectively land safe repo work on `master`
- [x] classify dirty work and leave unrelated residue untouched
- [x] restore bounded master cleanliness

## Phase G0: Language And Exit-Criteria Freeze

- [x] create canonical graduation contract doc
- [x] align launch vs graduation wording
- [x] update runbook/operator wording

## Phase G1: Watch-Window Automation And Graduation Ledger

- [x] add watch-window ledger runner
- [x] add graduation gate runner
- [x] re-run first live ledger + gate artifacts on current code

## Phase G2: Packet Completeness Hardening

- [x] audit degraded packet sources
- [x] narrow canary packet degradation causes
- [x] re-run packet batch harness
- [x] achieve `degraded_ratio = 0.0` for the current canary packet contract

## Phase G3: Live Crystal Evidence

- [x] verify `user_correction` writeback
- [x] generate live-shadow crystal evidence
- [x] keep governance posture `shadow`

## Phase G4: Recall Expansion To Cohort-Reliable

- [x] expand recall benchmark beyond the original three cases
- [x] add positive / negative / boundary / stress cases
- [x] harden posture scoring for dossier-style and generic visit-prep boundary asks
- [x] re-run live recall benchmark
- [x] reach `recall = pass`

## Phase G5: Promotion Backlog Reduction

- [x] freeze critical rollout source/bucket view
- [x] report critical rollout separately from general backlog
- [x] add narrow `planning_controlled` active-promotion runner
- [x] guard `planning_controlled` active atoms from leaking outside `PLANNING_EXPLICIT_PATH`
- [x] run live controlled promotion
- [x] clear `critical_rollout.buckets_without_active_atoms`
- [x] reduce promotion warning to `bounded_to_noncritical_only = true`

## Phase G6: Graduation Gate

- [x] rerun regression
- [x] rerun production health
- [x] rerun canary scorecard
- [x] rerun watch-window ledger
- [x] rerun graduation gate
- [x] verify latest honest decision remains `hold` only because watch window is incomplete

## Validation checklist

- [x] focused pytest suites pass for the corrective wave
- [x] live DB movement exists for the narrow controlled promotion wave
- [x] before/after rollout evidence exists for packet / recall / promotion / crystal
- [x] latest health rollup is:
  - `packet = pass`
  - `recall = pass`
  - `promotion = warn` with `bounded_to_noncritical_only = true`
  - `crystal = pass`
- [x] final closeout still respects unrelated dirty work outside this wave
