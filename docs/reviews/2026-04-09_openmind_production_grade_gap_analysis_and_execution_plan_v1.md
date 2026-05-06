# 2026-04-09 OpenMind Production-Grade Gap Analysis And Execution Plan v1

## Purpose

This document answers one narrower and stricter question than the earlier closeout set:

> What still separates the current stack from a high-standard production-grade state, and what exact work must be completed to close that gap?

This document treats the current system honestly as:

- `canary-readiness achieved`
- `watch window launched`
- `full production-grade usability not yet achieved`

It is intentionally stricter than the PR-1..PR-8 closeout ledger.

## Current audited state

As of 2026-04-09, the current stack has these verified properties:

- scope and authority naming are materially cleaner:
  - `docs/contracts/ADR-005-openmind-openclaw-chatgptrest-authority-boundary-v1.md`
  - `docs/contracts/2026-04-09_openmind_scope_surface_inventory_v2.md`
  - `docs/integrations/2026-04-09_openclaw_cognitive_substrate_runtime_contract_v4.md`
- the canary launch state is real, not aspirational:
  - `decision=launch_canary_watch`
  - `go_live_ready=false`
  - `warn_domains=["promotion"]`
  - no current failing domains
- operator-facing health and rollback surfaces exist and can be re-run:
  - packet batch harness
  - recall benchmark
  - promotion inventory
  - crystallized-learning governance
  - production health rollup
  - canary scorecard
- the current bridge model is explicit:
  - OpenClaw `openmind-*` plugins are bridge surfaces
  - ChatgptREST is the production/truth substrate
  - OpenMind is currently constitutional / audit / naming scope, not a standalone advisor runtime

## Current state is not enough

The current state is not yet a high-standard production-grade state for five reasons.

### 1. The current result is `canary-readiness`, not `full go-live`

The present rollout decision is still:

- `launch_canary_watch`
- `go_live_ready=false`

This means engineering closure exists, but the required wall-clock evidence window has not completed.

### 2. Packet is contract-pass, not completeness-pass

Current packet status is `pass`, but the packet harness still reports:

- `degraded_ratio = 1.0`
- `adjusted_degraded_ratio = 0.0`

This is acceptable for canary because all current degraded cases are attributed to declared external gaps, but it is not the same as saying the packet layer is complete.

The missing capabilities are still real:

- `personal_graph_empty`
- `memory_identity_missing`
- `captured_memory_identity_missing`
- `work_memory_identity_partial`

### 3. Crystal is governance-safe, but not yet proving live value

Current crystal status is `pass`, but the live governance report still shows:

- `records_scanned = 0`
- `active_crystal_count = 0`
- `projection_mode = shadow`

So the current crystal layer proves that the boundary is safe, not that live cross-session learning is already providing production value.

### 4. Recall is improved, but still narrow and benchmark-scoped

The recall benchmark is real, but it is currently:

- limited to three benchmark cases
- focused on planning/project canary asks
- not yet broad enough to justify a claim that the wider OpenMind substrate has stable recall under diverse business asks

Current recall is sufficient for the defined canary cohort, not yet sufficient for a strong full-surface claim.

### 5. Promotion is healthy enough for canary, but not healthy enough for production-grade truth maintenance

The current `promotion=warn` state is meaningful:

- blank promotion-reason ratio is already controlled
- but backlog is still structurally high
- multiple sources and projects still have large staged populations and zero active atoms

This is acceptable as a watch-window warning. It is not acceptable as a terminal steady-state for a production-grade cognitive substrate.

## Production-grade target

For this stack, a high-standard production-grade state means all of the following are true at the same time.

### A. Naming and authority are frozen

- no canonical doc claims that OpenMind already owns a standalone advisor / memory / graph runtime
- no canonical doc confuses bridge plugins with durable truth ownership
- all operator and integration docs use the same authority model

### B. Watch-window graduation is complete

- the watch window elapsed cleanly
- the latest regression bundle remains green
- there are no disallowed warning domains
- there is an explicit `go_live` decision artifact

### C. Packet moves from "safe canary" to "substantively complete"

- packet still compiles cleanly
- adjusted degraded ratio remains within contract
- raw degraded ratio materially declines
- identity and memory gaps are no longer dominant for the canary cohort

### D. Crystal moves from "safe shadow" to "live shadow with evidence"

- live interaction-learning records exist
- shadow crystal generation occurs on real data
- no denied preference leakage occurs
- false-positive rate remains below contract threshold

### E. Recall moves from benchmark-good to cohort-reliable

- more than the current three benchmark cases are covered
- cohort projects and surfaces have stable recall under real asks
- entity-grade or dossier-grade gaps are explicitly reduced, not just bridged indirectly

### F. Promotion moves from warning backlog to governed steady state

- blank promotion reasons stay low
- staged-only backlogs for critical source/project families shrink materially
- active/candidate coverage improves for the canary-critical substrate
- operator can explain why a source/project remains staged-heavy and what the next action is

### G. Operator posture is real

- a non-author operator can run the rollup and scorecard without opening code
- rollback flags are proven on live runtime
- watch-window artifacts are produced on schedule
- failure domains have one-command evidence paths and bounded first responses

## Remaining gaps

### Gap 1: terminology still overstates the state

The phrase `OpenMind production readiness` is too broad for the current reality.

What is actually true today:

- ChatgptREST/OpenClaw substrate canary-readiness is achieved
- the OpenMind naming/policy scope is integrated into that substrate
- standalone OpenMind runtime ownership is still not a fact

### Gap 2: packet external gaps are still being tolerated, not removed

Current packet pass semantics are correct, but only because adjusted degraded logic excludes declared external gaps.

Production-grade requires reducing the actual upstream causes:

- user/session memory identity propagation
- captured identity completeness
- work-memory continuity
- personal graph population or an explicit replacement contract

### Gap 3: crystal has no live corpus yet

The current governance contract is strong, but the live data volume is effectively zero.

Production-grade requires:

- non-zero live `user_correction` writeback
- non-zero stable crystal generation
- real manual review samples from live data

### Gap 4: recall benchmark is too small

Current recall pass is useful but narrow. It is enough to prove the benchmark moved. It is not enough to prove the production surface is robust.

Production-grade requires:

- a larger goldset
- multiple query families
- negative and boundary cases
- canary project asks plus non-canary stress cases

### Gap 5: promotion backlog remains structurally high

Current promotion warning is not a cosmetic warning. It points to real source/project families that still never produce active atoms.

Production-grade requires reducing that backlog for the surfaces that actually matter to the rollout.

### Gap 6: rollout evidence is launch-grade, not graduation-grade

The system can produce a launch scorecard. It does not yet have a completed watch-window ledger that proves:

- daily health stability
- no drift across the full window
- explicit expansion or graduation decision at the end

## Implementation plan

The work should be executed in six phases.

## Phase G0: Language And Exit-Criteria Freeze

### Goal

Stop overclaiming and freeze the final graduation contract.

### Work

1. Introduce canonical terminology:
   - `canary-ready`
   - `watch-window active`
   - `go-live ready`
2. Add one canonical graduation contract document that states:
   - which domains must be `pass`
   - which warnings, if any, are temporarily allowed
   - what watch-window evidence is required
3. Update closeout-facing docs so they do not imply that launch equals graduation.

### Acceptance

- all canonical docs use the same launch vs graduation vocabulary
- a reader cannot confuse `launch_canary_watch` with `go_live`

## Phase G1: Watch-Window Automation And Graduation Ledger

### Goal

Turn the current launch snapshot into a real multi-day operational gate.

### Work

1. Add a watch-window ledger runner that records:
   - daily regression summary path
   - daily health summary path
   - current scorecard state
   - any domain transitions
2. Add a final graduation decision runner that emits:
   - `go_live`
   - `hold`
   - `rollback`
3. Add runbook steps for daily canary review.

### Acceptance

- a daily artifact exists for each watch day
- the final graduation artifact is deterministic and reproducible
- operator does not need to reconstruct watch history manually

## Phase G2: Packet Completeness Hardening

### Goal

Reduce real packet degraded causes instead of only masking them through adjusted degraded logic.

### Work

1. Audit where these degraded sources originate:
   - `personal_graph_empty`
   - `memory_identity_missing`
   - `captured_memory_identity_missing`
   - `work_memory_identity_partial`
2. For each degraded source, define one of:
   - fix the upstream data path
   - replace it with a narrower explicit contract
   - formally downgrade it from required to optional, with justification
3. Extend packet harness to report:
   - raw degraded ratio
   - adjusted degraded ratio
   - degraded-source distribution over time

### Acceptance

- raw degraded ratio materially decreases from the current canary baseline
- no packet pass relies on undeclared degraded sources
- the packet layer remains fail-open for runtime safety but no longer depends on identity gaps as the normal case

## Phase G3: Live Crystal Evidence

### Goal

Move crystal from governance-safe to evidence-bearing shadow mode.

### Work

1. Ensure real `user_correction` records are being written on the canary cohort
2. Run a live crystal generation review over actual memory DB contents
3. Produce a live shadow sample set with:
   - non-zero records scanned
   - non-zero candidate or active shadow crystals
   - explicit manual review notes
4. Keep the current projection mode `shadow`

### Acceptance

- `records_scanned > 0`
- non-zero live crystal sample evidence exists
- false-positive rate remains under threshold
- no denylist leakage occurs

## Phase G4: Recall Expansion To Cohort-Reliable

### Goal

Move from small benchmark correctness to broader business-query reliability.

### Work

1. Expand the recall benchmark from 3 cases to a larger frozen goldset:
   - canary project asks
   - boundary asks
   - negative asks
   - non-canary stress asks
2. Add explicit entity-grade cases where relevant:
   - company/entity dossier asks
   - competitor/company relationship asks
3. Continue targeted re-ingest and entity boost only where the source material actually exists
4. Separate:
   - bridge recall
   - entity-grade recall
   - explainable abstain / clarify posture

### Acceptance

- the frozen benchmark expands materially beyond the current three-case set
- attention cases are explicit and explainable
- no production claim depends on indirect bridge hits being mislabeled as entity-grade

## Phase G5: Promotion Backlog Reduction For Critical Families

### Goal

Reduce production warning debt on the truth substrate for the source/project families that matter to the rollout.

### Work

1. Freeze which source/project families are in-scope for rollout truth quality
2. For those families, define target improvements:
   - staged reduction
   - candidate/active growth
   - groundedness / audit throughput
3. Add a production-grade promotion SLO report:
   - not just blank reason ratio
   - also critical-family staged-only backlog
4. Keep the warning domain if needed, but make it trendable and time-bounded

### Acceptance

- the current canary-critical families show measurable backlog reduction
- operator can identify top backlog families and next actions from one report
- promotion warning is either cleared or explicitly bounded to non-critical families

## Phase G6: Graduation Gate

### Goal

Convert the current canary launch into an explicit production-grade decision.

### Work

1. Re-run:
   - regression bundle
   - production health rollup
   - canary scorecard
   - watch-window ledger finalizer
2. Verify:
   - no fail domains
   - no unapproved warnings
   - watch window complete
   - packet/crystal/recall/promotion acceptance all reference current artifacts
3. Emit a single canonical graduation document.

### Acceptance

- `decision=go_live` is backed by current artifacts
- launch and graduation artifacts are distinct
- operator can answer "why did we graduate?" without opening code

## Recommended execution order

Order matters.

1. `G0` language and exit-criteria freeze
2. `G1` watch-window automation
3. `G2` packet completeness hardening
4. `G3` live crystal evidence
5. `G4` recall expansion
6. `G5` promotion backlog reduction
7. `G6` graduation gate

The critical constraint is:

- do not widen product claims before `G1` and `G2`
- do not widen learning claims before `G3`
- do not widen recall claims before `G4`
- do not claim production-grade truth substrate until `G5`

## Suggested ownership

### Codex / primary implementation owner

- terminology freeze and canonical contract updates
- watch-window ledger and graduation runners
- packet gap audit and upstream fixes
- live crystal pipeline verification
- recall harness expansion and entity-grade labeling
- promotion SLO reporting and final gate integration

### Sidecar reviewer / secondary agent

- goldset expansion review
- packet degraded-case manual review
- crystal manual review samples
- promotion blocker triage review
- final red-team review before graduation

## Hard acceptance checklist

The system should not be described as high-standard production-grade until all of the following are true:

- canary watch window completed
- explicit `go_live` decision artifact exists
- no domain is in `fail`
- no unapproved `warn` domain remains
- packet no longer depends on identity/memory degraded sources as the default steady-state
- live crystal evidence is non-zero and governance-safe
- recall benchmark is materially broader than the current three-case set
- promotion backlog for canary-critical families is reduced to a governed steady-state
- runbook and operator rollup remain one-command executable

## Final judgment

The current stack is not failing.

It is also not yet entitled to the strongest production-grade claim.

The honest current state is:

- architecture and naming are much cleaner than before
- canary launch posture is real
- operator tooling is real
- recall and packet quality moved from ad hoc to governed
- but the system still needs:
  - watch-window completion
  - packet completeness hardening
  - live crystal evidence
  - broader recall goldset coverage
  - critical-family promotion backlog reduction

Only after those are complete should the stack be described as high-standard production-grade.
