# 2026-04-09 OpenMind Project-Scope And Authority Execution Plan v1

> Status on 2026-04-09:
> - the execution scope in this roadmap has already been completed and closed via [phase closeout ledger](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-09_openmind_phase_execution_todo_and_closeout_v2.md)
> - the follow-on canonical roadmap for production readiness is now [2026-04-09_openmind_production_readiness_execution_plan_v1.md](/vol1/1000/projects/ChatgptREST/docs/roadmaps/2026-04-09_openmind_production_readiness_execution_plan_v1.md)

## Purpose

This document freezes the execution plan for the next architecture cleanup cycle across:

- OpenClaw front-end runtime
- OpenMind plugin layer / policy layer
- ChatgptREST substrate and public agent runtime

The plan includes:

- all currently validated architecture findings
- borrowable ideas worth adopting
- phase-by-phase execution
- explicit acceptance gates
- a strict rule that **Phase N+1 does not start until Phase N is closed**

## Scope

### In scope

- authority boundary freeze
- project-scoped substrate threading
- wake-up packet design and rollout
- recall / entity / ranking quality improvements
- promotion / digestion throughput improvements
- OpenMind scope narrowing and audit-surface cleanup
- document drift cleanup and canonical doc routing

### Out of scope

- replacing OpenClaw with a new front-end shell
- deleting legacy ChatgptREST surfaces in one step
- turning `openmind-*` plugins into a separate durable-memory runtime
- shipping Hermes-style autonomous self-evolution before authority, packet, and project-scope contracts are stable

## Verified current facts

### Runtime topology

- ChatgptREST packages the OpenClaw plugins in `openclaw_extensions/`.
- `openmind-advisor` currently bridges to `POST /v3/agent/turn` plus planning/session helper APIs.
- `openmind-memory` currently bridges `before_agent_start` and `agent_end` to `/v2/context/resolve` and `/v2/memory/capture`.
- `openmind-graph` calls `/v2/graph/query`.
- `openmind-telemetry` calls `/v2/telemetry/ingest`.

### Existing substrate strengths

- EvoMap is real and populated.
- MemoryManager / WorkMemoryManager / context assembly already exist.
- OpenClaw memory hooks are already wired.
- planning task, checkpoint, handoff, and coding-agent lanes already exist in ChatgptREST.

### Existing substrate weaknesses

- project scope is still partial on the hot path
- promotion / digestion throughput is too low
- authority anchor is not yet codified as a stable contract
- canonical docs still drift across `/v2/advisor/*`, `/v3/agent/*`, and plugin role descriptions

## Borrowable points worth adopting

### A. MemPalace: wake-up packet discipline

Adopt:

- L0-L3 wake-up packet layering
- explicit packet compiler
- separation between durable truth and prompt-ready packet

Do **not** adopt blindly:

- a separate memory authority that competes with the existing ChatgptREST substrate

Correct landing zone:

- ChatgptREST advisor/runtime packet compiler

### B. Hermes: skill crystallization and cross-session learning

Adopt later:

- crystallized skills / reusable high-quality patterns
- bounded cross-session learning from stable artifacts

Do **not** adopt in the first wave:

- premature automatic self-evolution without authority freeze, packet discipline, and auditable writeback

Correct landing zone:

- post-packet, post-project-scope, post-promotion-improvement phase

### C. Existing internal lessons already validated

- `_project_context.md` must be treated as a human authority anchor, not a disposable cache
- project scope is a threading problem across existing substrate, not a brand-new platform
- OpenClaw should be a front-end orchestration and consumption shell, not the durable project brain
- ChatgptREST should stay the structured truth layer
- mature long-session coding agents remain the best candidate for deep project execution, but they must consume packetized substrate truth

## Phase model

## Phase 0: Authority Freeze And Document Alignment

### Goal

Freeze the authority model and stop canonical docs from lying about the current runtime.

### Work

- write ADR for authority boundary
- create a canonical current-state integration doc for the OpenClaw plugin runtime
- mark older integration narrative as historical by redirecting canonical pointers, not by silently rewriting history
- define the canonical vocabulary:
  - fact production authority
  - fact consumption authority
  - constitutional / audit authority
  - authority anchor
  - wake-up packet

### Deliverables

- ADR-005
- current-state OpenClaw integration/runtime contract doc
- updated plugin README and canonical pointers
- walkthrough/dev-log for this freeze

### Acceptance

- no canonical current-state doc claims `openmind-advisor` still primarily bridges `/v2/advisor/ask` or `/v2/advisor/advise`
- no canonical current-state doc describes `openmind-memory` as the durable-memory authority
- the authority table is explicit and stable enough that later phases can refer to it without redefining ownership

### Closeout gate

Phase 0 is closed only when:

- docs are committed
- canonical pointers are updated
- historical docs are not silently overwritten

## Phase 1: Project Authority Anchor And Scope Threading

### Goal

Make project scope a first-class substrate dimension without turning `_project_context.md` into a bloated cache.

### Work

- define `_project_context.md` contract:
  - frozen facts
  - pinned authority docs
  - style rules
  - current human direction
- thread `project_id` / `projectRef` through:
  - context resolve request/options
  - context assembler
  - memory manager / work memory manager
  - retrieval mainline
  - relevant signals / writeback paths
- preserve the priority order:

```text
authority anchor > project memory > EvoMap knowledge > runtime heuristics
```

### Borrowed points used here

- existing internal project-scope analysis
- authority-anchor discipline from current `_project_context.md` discussion

### Acceptance

- project-aware requests can pass one stable project identifier through hot-path context assembly
- project-scoped memory and retrieval do not override authority-anchor facts
- at least one end-to-end project-scoped recall trace exists with evidence
- no new code path invents a competing authority order

### Closeout gate

Phase 1 is closed only when:

- the threading path is implemented end-to-end
- one project-scoped acceptance walkthrough exists
- authority precedence is visible in code or contract, not only prose

## Phase 2: Wake-Up Packet Compiler

### Goal

Compile durable substrate truth into a packet that execution agents can consume without re-owning durable memory.

### Work

- design packet layers:
  - `L0 authority anchor`
  - `L1 active project memory / open loops`
  - `L2 retrieved project knowledge / entity context`
  - `L3 runtime handoff / recommended next step`
- implement packet compiler in ChatgptREST advisor/runtime plane
- project packet into:
  - `openmind-advisor`
  - planning handoff / checkpoint surfaces
  - coding-agent execution lanes where relevant

### Borrowed points used here

- MemPalace L0-L3 packet discipline

### Acceptance

- packet sections have explicit provenance
- packet respects token budget and deterministic ordering
- OpenClaw consumes a packet projection instead of becoming the durable-memory organizer
- a single packet can be traced back to authority anchor, memory, and knowledge sources separately

### Closeout gate

Phase 2 is closed only when:

- packet schema or contract is frozen
- one real packet example is archived
- OpenClaw and at least one backend execution lane can consume it

## Phase 3: Project Recall, Entity Recall, And Ranking Quality

### Goal

Improve retrieval quality after project scope and packetization exist.

### Work

- improve entity materialization and alias handling
- improve ranking for project-scoped recall
- add offline evaluation for recurring project/entity questions
- continue current entity recall improvements instead of mixing them into authority work

### Borrowed points used here

- current internal entity-recall findings
- packet compiler outputs from Phase 2

### Acceptance

- agreed benchmark queries show measurable improvement in top-k relevance
- project mis-association rate decreases
- entity answers cite packet/knowledge provenance instead of free-floating heuristics

### Closeout gate

Phase 3 is closed only when:

- evaluation dataset and results are archived
- ranking changes are tied to repeatable evidence, not anecdotal spot checks

## Phase 4: Promotion / Digestion Throughput

### Goal

Fix the substrate bottleneck where ingestion is much stronger than promotion/digestion.

### Work

- instrument promotion stages
- identify why active promoted atoms are far below useful levels
- improve promotion gating, batching, and receipts
- make writeback and promotion auditable at packet/knowledge boundaries

### Acceptance

- promotion throughput has explicit baseline and target
- promotion audit receipts are queryable and attributable
- active/promoted coverage improves without increasing authority violations

### Closeout gate

Phase 4 is closed only when:

- before/after metrics are written down
- promotion changes have rollback notes
- packet/compiler consumers can rely on improved promoted slices

## Phase 5: Hermes-Style Crystallization And Cross-Session Learning

### Goal

Add higher-order reusable learning only after authority, packet, project-scope, and promotion are stable.

### Work

- define crystal / reusable-skill artifact type
- promote only from audited, stable outputs
- keep human authority anchor above crystallized learning
- make rollback and invalidation explicit

### Borrowed points used here

- Hermes skill crystallization
- Hermes cross-session learning

### Acceptance

- crystallized artifacts have explicit provenance and invalidation path
- no crystallized artifact can silently override authority anchor
- at least one useful pattern is reused across sessions without loss of auditability

### Closeout gate

Phase 5 is closed only when:

- crystallized artifacts are governed by a real contract
- rollback/invalidation is demonstrated
- the system still remains understandable in terms of authority boundaries

## Phase 6: OpenMind Scope Narrowing Or Runtime Expansion

### Goal

Resolve naming drift: either keep OpenMind explicitly narrow, or implement the missing runtime it claims.

### Work

- audit every current OpenMind claim in README/integration docs
- classify each surface as:
  - implemented runtime
  - bridge only
  - audit/policy only
  - reserved / not implemented
- either implement missing runtime pieces or narrow the claims

### Acceptance

- no canonical doc claims ownership that the code does not implement
- plugin/runtime naming is aligned with actual authority

### Closeout gate

Phase 6 is closed only when:

- documentation and runtime claims match
- there is no remaining ambiguity about whether OpenMind is a runtime, a bridge family, or a constitutional layer in each specific context

## Phase sequencing rule

No phase starts before the previous phase is closed.

For every phase, closure requires:

1. code and/or docs landed
2. acceptance evidence landed
3. rollback or residual-risk note landed
4. canonical references updated

## Tonight's completed scope

This document only freezes the plan and Phase 0 doc-alignment work.

It does **not** claim that later phases are already implemented.

## Operator note on `claudeminmax`

This planning/doc-alignment pass does **not** require `claudeminmax`.

Reason:

- the task is dominated by repo-local truth, contract cleanup, and historical drift handling
- using another model for primary drafting would not improve the authority of the resulting plan
- later implementation phases may still use `claudeminmax` selectively for bounded review or coding execution where it materially speeds up delivery
