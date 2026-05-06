# 2026-04-09 OpenMind Production Readiness Execution Plan v1

## Purpose

This document defines the follow-on plan after the completed Phase 0-6 execution cycle.

It answers one narrower question:

> What is still required before the current OpenMind / OpenClaw / ChatgptREST stack can be used as a production-grade system instead of a strong architecture skeleton?

This plan is intentionally stricter than the earlier architecture-execution roadmap.

It adds:

- production-readiness gates
- explicit automatic vs manual acceptance criteria
- human confirmation requirements
- a recommended split between the primary implementation agent and an independent secondary reviewer lane

## Canonical prerequisites

This plan assumes the earlier execution cycle is already complete.

Required baseline:

- [ADR-005 authority boundary](/vol1/1000/projects/ChatgptREST/docs/contracts/ADR-005-openmind-openclaw-chatgptrest-authority-boundary-v1.md)
- [Phase 0-6 execution roadmap](/vol1/1000/projects/ChatgptREST/docs/roadmaps/2026-04-09_openmind_project_scope_and_authority_execution_plan_v1.md)
- [Phase 0-6 closeout ledger](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-09_openmind_phase_execution_todo_and_closeout_v2.md)
- [Wake-up packet contract](/vol1/1000/projects/ChatgptREST/docs/contracts/2026-04-09_wakeup_packet_contract_v1.md)
- [Current runtime contract](/vol1/1000/projects/ChatgptREST/docs/integrations/2026-04-09_openclaw_cognitive_substrate_runtime_contract_v3.md)
- [Independent review](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-09_openmind_phase_execution_independent_review_v1.md)

## Production-ready definition

The stack is considered production-grade only when all of the following are true:

1. Top active projects have stable, validated authority anchors instead of ad hoc `_project_context.md` quality.
2. Wake-up packet quality is measured, explainable, and operationally observable.
3. Project recall, entity recall, and promotion throughput improve real operator outcomes instead of only increasing substrate volume.
4. Crystallized learning remains advisory, auditable, and resistant to premature preference lock-in.
5. OpenMind / OpenClaw / ChatgptREST runtime claims, docs, and live surfaces match exactly.
6. Broader regression, canary rollout, monitoring, runbooks, and rollback drills are all in place.

## Sequencing rule

No phase starts before the previous phase is closed.

A phase is closed only when all of the following exist:

1. implementation landed
2. automatic acceptance evidence landed
3. manual confirmation notes landed when required
4. rollback or residual-risk notes landed
5. canonical references updated

## Human-confirmation policy

Not every phase needs direct user confirmation.

Use this rule:

- `User confirmation required` when the phase changes business semantics, acceptance thresholds, crystal governance, or rollout risk.
- `Operator confirmation required` when the phase changes observability, runbooks, rollback, or live operational behavior.
- `Independent reviewer required` when the phase claims higher quality, production readiness, or broader regression safety.

### Required human confirmations

| Area | Confirmation owner | Why it cannot be fully automated |
| --- | --- | --- |
| Top production project roster and owners | User / project owner | This is a business-priority decision, not a substrate inference problem. |
| Packet quality rubric threshold | User / project owner | "Useful enough" is partly product judgment. |
| Crystal allowlist / denylist | User / product owner | Preference dimensions and policy boundaries are product semantics. |
| Canary cohort and production go-live | User / operator | Rollout risk tolerance is managerial, not technical. |
| Runbook drill sign-off | Operator | An operator must verify the instructions are actually usable under pressure. |

### No direct user confirmation required

These should be validated automatically first and only escalated if they fail:

- `_project_context.md` lint and freshness
- packet schema correctness
- packet harness generation
- recall benchmark execution
- promotion inventory generation
- regression suite execution
- telemetry and dashboard ingestion

## Provisional quantitative thresholds

These are the default thresholds until the user or project owner explicitly overrides them.

| Phase | Default threshold | Needs user override to change? |
| --- | --- | --- |
| PR-1 project anchor quality | `100%` of canary projects pass schema lint; `100%` have `owner`, `goal`, `current phase`, pinned authority docs, and open loops; active canary anchors are fresher than `7 days` | Yes |
| PR-2 packet quality | packet harness success rate `>=95%`; median packet usefulness score `>=4/5`; canary degraded ratio `<=20%` after excluding declared external gaps | Yes |
| PR-3 recall and promotion quality | top-3 hit rate improves by `>=20%` over the frozen baseline; project mis-association rate `<=5%`; blank promotion reason share for new staged atoms `<10%` or cut by `>=50%` from baseline | Yes |
| PR-4 crystal governance | `0` known authority-anchor override incidents; manual sample false-positive crystal rate `<=5%`; any support-threshold change requires explicit sign-off | Yes |
| PR-5 scope closure | `0` overstated live-surface claims in canonical docs; `100%` of claimed live surfaces map to code, contract, and operator entrypoint | No |
| PR-6 regression and rollback | critical release suites all pass or have explicit waivers; rollback drill completes successfully in one rehearsed path | No |
| PR-7 observability and runbooks | operator drill can identify the fault domain and first response path within `15 minutes`; dashboard/query layer answers the core health questions without code reading | No |
| PR-8 canary and rollout | canary watch window lasts at least `7 days`; no Sev-1 rollout incident; key quality metrics stay within the agreed failure budget during staged expansion | Yes |

## Immediate-start vs approval-gated work

### Can start immediately without waiting for the user

- PR-1 schema draft, lint implementation, freshness checks, and harness scaffolding
- PR-2 packet rubric instrumentation, packet harness batch runner, and metric plumbing
- PR-3 benchmark harness, promotion blocker inventory, and baseline score capture
- PR-4 crystal telemetry, invalidation reporting, and sample-review tooling
- PR-5 inventory refresh, scope diffing, and contract/readme drift cleanup
- PR-6 regression expansion, feature flags, and rollback drill preparation
- PR-7 telemetry ingestion, dashboard queries, and operator runbook drafting

### Must pause for user or operator confirmation before phase closeout

- final canary project roster for PR-1 and PR-2
- packet usefulness threshold if the provisional threshold is not acceptable
- benchmark query set if it no longer reflects real project usage
- crystal allowlist / denylist and any support-threshold change
- final public naming posture if PR-5 changes externally visible claims
- canary cohort, rollout watch window, and production go-live decision
- final runbook drill sign-off by the operator

## Secondary-reviewer policy

The main implementation agent owns:

- canonical contracts and roadmap docs
- runtime hot-path code changes
- migration sequencing
- final acceptance argument
- rollback notes

The independent secondary reviewer lane should be used for:

- red-team review at phase closeout
- packet sample scoring against the rubric
- regression-risk challenge review
- canary summary review
- targeted criticism of acceptance evidence

Review cadence by phase:

- optional for `PR-1` and `PR-2`
- recommended for `PR-3` and `PR-4`
- mandatory for `PR-5`
- mandatory for `PR-8`
- mandatory for any phase that changes externally visible naming or authority claims

For this roadmap, `Claude MiniMax` is recommended only as a bounded secondary-review lane.

It should **not** be the primary author of:

- canonical authority contracts
- runtime hot-path ownership changes
- final rollout decisions

## Phase PR-1: Project Authority Anchor Quality

### Goal

Turn `_project_context.md` from a fragile manual note into a governed authority-anchor input surface.

### Work

- define the canonical `_project_context.md` schema:
  - owner
  - goal
  - non-goals
  - current phase
  - pinned authority docs
  - open loops
  - decision ledger
  - freshness metadata
- add lint, freshness checks, and required-section validation
- build a `project_context_harness`
- upgrade the top active projects to the canonical schema
- make packet degradation explicit when the anchor is partial or stale
- add wrong-project and conflicting-fact precedence tests

### Automatic acceptance

- schema and freshness checks pass for the top active projects
- packet receipts expose anchor degradation explicitly
- no packet silently treats a stale or partial anchor as complete
- one harness report is archived per top project
- cross-project bleed tests remain green
- authority-anchor precedence tests remain green

### Manual confirmation

- user confirms the top production project roster
- user or project owner confirms the owner field and authority-doc set for each top project

### Evidence to archive

- project-context lint report
- harness output for each top project
- degraded-source summary before/after

### Secondary-reviewer split

- primary agent: schema, linting, harness, rollout
- secondary reviewer: spot-check top-project anchors for semantic drift and missing authority docs

### Exit gate

PR-1 is closed only when:

- the top production projects all pass lint
- degraded anchor cases are visible in receipts
- human ownership of the top-project authority anchors is recorded

## Phase PR-2: Wake-Up Packet Quality Evaluation

### Goal

Move from "packet exists" to "packet quality is measured and trustworthy."

### Work

- define a packet quality rubric:
  - L0 authority accuracy
  - L1 open-loop usefulness
  - L2 retrieval relevance
  - L3 next-step usefulness
- extend the packet harness to batch-run top projects and recurring prompts
- freeze packet schema versioning and deterministic compilation expectations
- record:
  - degraded sources
  - layer coverage
  - token budget
  - provenance completeness
  - human usefulness score
- classify fail-open vs fail-closed packet behaviors
- add golden-packet tests and explicit truncation or omission receipts

### Automatic acceptance

- the harness emits comparable results across the canary projects
- packet layer ordering and provenance remain deterministic
- degraded packets are measurable rather than anecdotal
- the packet budget remains within the agreed envelope
- packet consumers remain compatible with the frozen schema version

### Manual confirmation

- user confirms the minimum packet usefulness threshold for canary projects
- operator confirms the packet harness is understandable enough to use repeatedly

### Evidence to archive

- packet rubric definition
- packet harness outputs
- degraded-source trend report
- packet usefulness review sample

### Secondary-reviewer split

- primary agent: rubric instrumentation, harness, metrics
- secondary reviewer: blind-score a packet sample set and challenge false positives

### Exit gate

PR-2 is closed only when:

- packet quality is measured instead of guessed
- the agreed packet usefulness threshold is reached for canary projects
- degraded sources are attributable and trendable

## Phase PR-3: Recall, Entity Recall, And Promotion Quality

### Goal

Ensure the system remembers the right things, not just more things.

### Work

- continue entity materialization and alias handling
- improve project-scoped ranking
- clear the biggest promotion blockers, especially blank promotion reasons
- build a frozen and repeatable recall benchmark for project and entity queries
- track whether repeated background re-explanation decreases
- define low-confidence abstain or clarify behavior

### Automatic acceptance

- benchmark queries show measured improvement in top-k relevance
- project mis-association decreases
- blank promotion-reason backlog declines
- promotion receipts remain queryable and attributable
- provenance attribution pass rate is measured and improving

### Manual confirmation

- user confirms the target benchmark query set still reflects real usage
- operator confirms the promotion blocker report is actionable

### Evidence to archive

- benchmark dataset
- benchmark score delta
- promotion inventory baseline and follow-up snapshot
- recall failure taxonomy

### Secondary-reviewer split

- primary agent: ranking changes, promotion instrumentation, benchmark runner
- secondary reviewer: challenge the benchmark set and inspect top-k false positives / false negatives

### Exit gate

PR-3 is closed only when:

- recall quality gains are repeatable
- promotion throughput changes have before/after evidence
- packet consumers can rely on better promoted slices

## Phase PR-4: Crystallized Learning Governance Hardening

### Goal

Keep cross-session learning useful without turning it into silent preference pollution.

### Work

- evaluate whether `min_support=2` should stay or rise
- define a crystal allowlist and denylist
- add conflict, supersession, and invalidation reporting
- define an invalidation SLA
- review whether crystal propagation is cached anywhere in a risky way
- sample crystals manually for incorrect early lock-in
- require a shadow-mode observation period before wider live reuse
- explicitly label crystallized-learning usage at consumption points where relevant

### Automatic acceptance

- every crystal has provenance, support, and invalidation metadata
- crystals remain lower priority than the authority anchor
- superseded crystals are queryable
- crystal generation volume and invalidation volume are measurable
- shadow-mode evidence exists before any wider reuse claim

### Manual confirmation

- user confirms the allowlist and denylist for crystalizable preference dimensions
- user approves any support-threshold change that affects product semantics

### Evidence to archive

- crystal governance contract update
- crystal/invalidation report
- manual sample review log

### Secondary-reviewer split

- primary agent: contract tightening, telemetry, invalidation logic
- secondary reviewer: red-team whether any crystal can effectively outrank L0 in practice

### Exit gate

PR-4 is closed only when:

- advisory boundaries are explicit in contract and runtime behavior
- there is no known path for silent authority-anchor override
- support-threshold and allowlist semantics are signed off

## Phase PR-5: OpenMind Scope And Surface Closure

### Goal

Remove the remaining gap between naming, docs, and real runtime ownership.

### Work

- inventory all OpenMind surfaces again
- maintain a surface inventory matrix with owner, status, and authority per claim
- classify each one as:
  - live runtime
  - bridge only
  - audit / constitutional only
  - reserved / not implemented
- either implement missing pieces or narrow the claims
- fold graph/policy placeholders into explicit reserved or future states if they remain empty
- add doc-lint or parity checks for unsupported runtime claims

### Automatic acceptance

- no canonical doc claims ownership the runtime does not implement
- every live surface has a code path, contract, and operator entrypoint
- empty graph/policy surfaces are marked honestly
- stale-claim scans remain clean

### Manual confirmation

- user approves the final public naming posture if any externally visible claim changes

### Evidence to archive

- updated scope inventory
- contract / README diff
- residual-gap note for reserved surfaces

### Secondary-reviewer split

- primary agent: inventory, docs, contract cleanup
- secondary reviewer: challenge whether any claimed surface is still overstated

### Exit gate

PR-5 is closed only when:

- a newcomer reading the docs would not misread OpenMind as a fuller runtime than it is
- all public claims match code reality

## Phase PR-6: Broader Regression And Release Flags

### Goal

Upgrade from focused validation to release-safe validation.

### Work

- expand the regression suite across:
  - advisor
  - public agent
  - openclaw extensions
  - session lifecycle
  - memory bridge
- add feature flags for:
  - packet projection
  - crystal projection
  - canary-only routes if needed
- document rollback switches

### Automatic acceptance

- broader regression suite passes for the release candidate
- feature flags cleanly disable new behavior
- rollback notes are executable, not aspirational

### Manual confirmation

- operator confirms the rollback drill worked in practice
- independent reviewer confirms the broader regression summary is credible

### Evidence to archive

- regression summary
- rollback drill log
- feature-flag matrix

### Secondary-reviewer split

- primary agent: flags, test coverage, rollback docs
- secondary reviewer: regression-risk review and challenge of any skipped coverage

### Exit gate

PR-6 is closed only when:

- broader regression is green or waived with explicit residual risk
- the rollback path has been exercised

## Phase PR-7: Observability And Operator Readiness

### Goal

Make the system diagnosable and operable under normal load and degraded conditions.

### Work

- add packet metrics:
  - compile success rate
  - degraded ratio
  - layer coverage
- add recall and promotion health views
- add crystal churn and invalidation metrics
- publish operator runbooks for:
  - packet degradation
  - recall drift
  - promotion blockage
  - crystal conflicts

### Automatic acceptance

- telemetry ingests the new signal types
- dashboard or query views can answer the core health questions
- runbook commands work on the current stack

### Manual confirmation

- operator runs one tabletop or live drill from the runbook
- user confirms the dashboard answers the high-level product health questions

### Evidence to archive

- metric definitions
- runbook drill notes
- dashboard screenshots or query samples

### Secondary-reviewer split

- primary agent: metrics, runbooks, dashboard/query surfaces
- secondary reviewer: operator-readability review of the runbook and signal naming

### Exit gate

PR-7 is closed only when:

- an operator can identify packet, recall, promotion, and crystal problems without reading code
- the drill evidence is archived

## Phase PR-8: Canary And Production Rollout

### Goal

Move from controlled canary use to production-grade usage.

### Work

- define the canary cohort
- run shadow or comparative evaluation where needed
- expand from the top projects to the wider production set in stages
- keep weekly quality review and rollback readiness during rollout

### Automatic acceptance

- canary projects stay within the quality and failure budget
- packet degradation, recall drift, and crystal conflict stay below the agreed threshold
- rollout metrics remain stable across staged expansion

### Manual confirmation

- user approves canary cohort
- user and operator approve production go-live
- independent reviewer signs off on the canary summary before full expansion

### Evidence to archive

- canary scorecard
- rollout decision log
- post-rollout watch checklist

### Secondary-reviewer split

- primary agent: rollout mechanics, evidence assembly, rollback readiness
- secondary reviewer: canary readout critique and final pre-rollout review

### Exit gate

PR-8 is closed only when:

- the canary scorecard is accepted
- production go-live is explicitly approved
- a post-rollout watch window is defined

## Recommended execution order

1. PR-1 Project Authority Anchor Quality
2. PR-2 Wake-Up Packet Quality Evaluation
3. PR-3 Recall, Entity Recall, And Promotion Quality
4. PR-4 Crystallized Learning Governance Hardening
5. PR-5 OpenMind Scope And Surface Closure
6. PR-6 Broader Regression And Release Flags
7. PR-7 Observability And Operator Readiness
8. PR-8 Canary And Production Rollout

## Recommended use of Claude MiniMax

Use `Claude MiniMax` selectively at the end of phases, not at the start.

Best-fit uses:

- independent closeout review
- blind scoring of packet samples
- challenge review of regression evidence
- red-team review of crystal-governance claims
- canary summary critique

Avoid using it as:

- the primary author of canonical contracts
- the owner of runtime hot-path edits
- the decision-maker for rollout approval

## Status

This roadmap is the canonical follow-on plan for production readiness after the completed Phase 0-6 execution cycle.
