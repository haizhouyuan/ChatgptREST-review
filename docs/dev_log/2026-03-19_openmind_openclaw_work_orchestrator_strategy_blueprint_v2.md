# 2026-03-19 OpenMind OpenClaw Work Orchestrator Strategy Blueprint v2

## 1. Updated Baseline

This version is based on the repo state after the 2026-03-19 stabilization work:

- public MCP recovery is durable enough to survive transport/API restart
- wait-phase cancel now terminates much faster
- `cc-sessiond` residue pool is clean enough for evidence/debug use
- premium ingress now has a real strategist mainline instead of only
  `AskContract + threshold clarify + template prompt_builder`

That matters because the next architecture plan should be built on what is
already working, not on the old `cc-sessiond` rescue narrative.

## 2. Strategic Decision

Do **not** treat ChatgptREST as the future universal platform kernel.

Do **not** treat OpenClaw as the business brain.

Do **not** keep investing in `cc-sessiond` as a general execution core.

Instead, make the long-term system explicit:

`OpenClaw -> OpenMind -> Work Orchestrator -> Execution Lanes`

with `ChatgptREST` retained as one important lane and one public-agent ingress
surface, not as the whole operating system.

## 3. Layer Roles

### 3.1 OpenClaw

Role:

- entry shell
- user-facing interaction surface
- Feishu / bot / plugin extensibility
- notifications, follow-up, long-running visibility

Should not own:

- core planning policy
- knowledge governance
- multi-task quality control

### 3.2 OpenMind

Role:

- requirement analysis
- intent analysis
- funnel / worth-it judgment
- model routing policy
- planning and clarification policy
- KB retrieval and memory grounding
- EvoMap feedback interpretation

OpenMind is the cognitive control plane.

### 3.3 Work Orchestrator

Role:

- multi-task management
- multi-role assignment
- long-running supervision
- quality gates and checkpoints
- escalation / retry / stopline handling
- low-attention background watching so the user does not have to stare at CLI
- scenario-bound skill orchestration

This is the missing middle.

It is stronger than a thin runner bridge, but narrower than a universal
agent platform.

### 3.4 Execution Lanes

Execution Lanes are concrete substrates, not product brains:

- `ChatgptREST` lane
  - public agent ingress
  - web/deep research
  - durable async jobs
  - controlled live ChatGPT/Gemini execution
- `CC/Codex` coding lane
  - implementation-heavy work
  - repo execution
  - tool-rich coding tasks
- later specialized lanes
  - browser-heavy
  - document-heavy
  - data-analysis-heavy

### 3.5 Finbot

Finbot remains a parallel vertical application.

It may consume OpenMind or Work Orchestrator capabilities, but it should not
define the main architecture of the general work system.

## 4. What Has Been Learned

### 4.1 What actually needs strong architecture

The hardest part is not “one more agent runtime”.

The hard part is:

- who analyzes the request
- who decides whether to clarify
- who decomposes the work
- who supervises long-running tasks
- who checks quality before the user sees the result
- who notices blocked work without human babysitting

That is why the correct core is `OpenMind + Work Orchestrator`, not
`OpenClaw + old session service`.

### 4.2 Why `cc-sessiond` is not the future core

`cc-sessiond` proved useful as an experiment, but it encoded the wrong unit:

- session-centric
- prompt-path-centric
- backend-wrapper-centric

The durable unit of the future system should instead be:

- `WorkItem`
- `ScenarioPack`
- `Run`
- `RoleAssignment`
- `Checkpoint`
- `QualityGate`
- `Artifact`
- `Signal`

## 5. Long-Term Domain Focus

The main system should optimize for two high-value work families:

- `planning`
  - business planning
  - HR planning
  - meeting synthesis
  - interview records
  - investigation summaries
- `research`
  - topic studies
  - technical route analysis
  - component/theme tracking
  - evidence-led synthesis

These are the scenarios that actually need:

- history grounding
- knowledge reuse
- clarification
- structured planning
- role-driven review
- low-attention supervision

## 6. Work Orchestrator Scope

The Work Orchestrator should explicitly own:

- task queue and priority
- scenario routing
- role policy
- skill invocation policy
- supervisor loops
- human checkpoints
- quality gates
- delivery readiness

It should **not** own:

- raw bot ingress
- primary knowledge storage
- low-level browser automation internals
- every specialized executor implementation

## 7. Skills Strategy

Do not build a giant undifferentiated skill marketplace.

Split skills into two layers:

- `Scenario Skills`
  - planning report pack
  - meeting synthesis pack
  - topic research pack
  - interview review pack
- `Runtime Skills`
  - ChatgptREST lane
  - CC/Codex coding lane
  - browser automation lane
  - document ingestion lane

Scenario skills belong to Work Orchestrator policy.
Runtime skills belong to execution lanes.

## 8. Near-Term Roadmap

### Phase 0: Stabilized Base

Already substantially done in ChatgptREST:

- public MCP recovery
- wait cancel fast terminalization
- strategist mainline
- residue cleanup

### Phase 1: Formalize the Work Object Model

Create a shared domain model outside of `cc-sessiond` semantics:

- `WorkItem`
- `ScenarioPack`
- `RoleAssignment`
- `Run`
- `Checkpoint`
- `QualityGate`
- `Artifact`
- `Signal`

### Phase 2: Extract Orchestrator Policy

Start with only two scenario packs:

- `Planning Pack`
- `Research Pack`

Each pack should define:

- intake checklist
- clarify policy
- role chain
- quality gates
- publish criteria

### Phase 3: Connect Execution Lanes

Wire the orchestrator to:

- ChatgptREST lane
- CC/Codex coding lane

Do not start with arbitrary team topology.
Start with a few fixed role templates.

### Phase 4: Add Low-Attention Supervision

Build background supervision so the system can:

- notice blocked tasks
- request user input only at real checkpoints
- escalate quality failures
- remind or resume without user babysitting

## 9. Concrete Next Steps

1. Freeze new platform naming churn for one cycle.
2. Keep premium ingress strategist in ChatgptREST as the current production-facing ask brain.
3. Write the shared `WorkItem / Checkpoint / QualityGate` contracts.
4. Define `Planning Pack` and `Research Pack` as the first two orchestrated scenario packs.
5. Decide which existing OpenMind funnel/model-routing pieces move into the new shared control plane and which stay local.
6. Treat `cc-sessiond` as legacy experimental infrastructure, not roadmap center.

## 10. Bottom Line

The future system should not be “a better cc-sessiond”.

It should be:

- `OpenClaw` for entry and interaction
- `OpenMind` for cognition and planning
- `Work Orchestrator` for supervision and quality-controlled multi-task execution
- `ChatgptREST` as one powerful execution lane plus a public ask surface

That gives a path that is both narrower and stronger:

- narrower because it stops pretending one service should become everything
- stronger because it finally gives multi-task, role, quality, and supervision
  a real home
