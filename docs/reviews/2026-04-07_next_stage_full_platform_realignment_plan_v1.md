# Next Stage Full Platform Realignment Plan V1

Date: 2026-04-07

## 1. Purpose

This is the next-stage implementation plan after the completed `A-F` rollout.

This plan is intentionally **not** another fragmented patch list.

Its goal is to finish the product shape that the review cycle clarified:

1. `ChatgptREST` should be web-first for mature coding agents.
2. `OpenClaw` should be an entry-layer orchestrator, not the project brain.
3. `OpenMind plugins` should be thin bridges.
4. Project truth should be governed explicitly.
5. Promotion should be observable, safe, and operationally maintained.

This is a full realignment plan with implementation detail and acceptance targets.

## 2. Final target state

At the end of the next stage, the platform should have the following shape.

### 2.1 Coding-agent surface

For `Codex / Claude Code / Antigravity`, the default northbound surface should feel like:

- submit a web-backed task
- wait on it
- fetch final answer
- fetch conversation/export/artifacts if needed
- cancel if needed

This surface must be:

- result-first
- finality-aware
- artifact-aware
- low-cognitive-load

Coding agents should not need to understand:

- internal job lineage
- controller quirks
- broad advisor semantics
- internal control-plane structure

unless they explicitly opt into advanced mode.

### 2.2 OpenClaw entry layer

For `OpenClaw`, the entry layer should reliably do:

- project association
- continue/branch/status determination
- clarification when needed
- handoff into OpenMind/ChatgptREST backend
- user-facing answer shaping

It should not be responsible for:

- long-term project reasoning
- maintaining project truth
- independently solving complex multi-round planning

### 2.3 Project truth model

Project truth should be explicitly layered:

1. **Authority anchor**
   - human-governed
   - frozen facts
   - style rules
   - pinned authority inputs

2. **Project memory**
   - working context
   - open loops
   - recent decisions
   - branch/continue state

3. **Project knowledge**
   - EvoMap / structured atoms
   - cross-session reusable knowledge

4. **Runtime context**
   - dynamic assembly for the current request

Priority must remain:

`authority anchor > project memory > project knowledge > runtime heuristics`

### 2.4 Promotion and maintenance

Promotion should not become unsafe auto-promotion.

Instead, the platform should provide:

- stable inventory
- repeatable reviewed maintenance
- explicit release/readiness evidence
- harness-backed replay/evaluation

## 3. Work packages

This stage should be executed as **four large work packages**, not dozens of unrelated microtasks.

## 4. Work package 1: Coding-agent surface realignment

### Objective

Turn the current public agent MCP into a capability-graded surface whose default shape matches mature coding-agent needs.

### Required changes

#### 4.1 Add an explicit lightweight web/result-first mode

Implementation direction:

- keep the existing `agent_mcp.py` surface
- add a coding-agent-friendly lightweight mode instead of forcing every client through full advisor semantics

Two acceptable implementation shapes:

1. `advisor_agent_turn(..., mode="lightweight")`
2. `advisor_agent_turn(..., bypass_advisor=true)` with a strongly defined result contract

Whichever shape is chosen, the behavior must be:

- minimal required fields
- finality-aware answer handling
- explicit `answer_state`
- explicit authoritative answer fetch path

#### 4.2 Normalize answer retrieval contract

Required public semantics:

- `turn`
- `wait`
- `answer`
- `cancel`

With clear distinction between:

- inline short answer
- final artifact-backed answer
- provisional completion

This requires tightening:

- public session surface
- agent MCP wrapper behavior
- any coding-agent helper wrappers that still assume `last_answer`

#### 4.3 Separate default and advanced behavior

Default coding-agent docs and examples must only teach:

- lightweight mode
- result-first flow

Advanced advisor semantics remain available, but must be documented as:

- advanced
- optional
- not required for routine coding-agent use

### Files likely involved

- [chatgptrest/mcp/agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py)
- [chatgptrest/api/routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [skills-src/chatgptrest-call/scripts/chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py)
- [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)
- [docs/contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/contract_v1.md)
- client-entry docs

### Acceptance targets

1. A coding agent can complete a Deep Research flow using only:
   - submit
   - wait
   - answer
2. The default docs for coding agents no longer require understanding control-plane internals.
3. Short tasks remain easy, but long tasks are always finality-aware.
4. There is no `completed + empty answer + unclear next step` path left in the lightweight mode.

## 5. Work package 2: OpenClaw entry-layer completion

### Objective

Finish OpenClaw’s role as the entry-layer project associator and orchestrator.

### Required changes

#### 5.1 Project association rules

Make project association deterministic enough that OpenClaw does not drift into local ad hoc behavior.

Required behavior:

- detect known project references
- attach `projectRef/project_id`
- choose continue/branch/status mode conservatively
- ask clarification only when needed

Important principle:

- **rules first**
- model inference second

#### 5.2 Continue/branch/status behavior

OpenClaw needs a stable policy for:

- "continue the same project task"
- "branch from the current work"
- "check the current status"

This policy must be explicit in:

- prompt/routing rules
- plugin handoff shape
- runtime projection

#### 5.3 Entry-layer fail-closed behavior

When project association is ambiguous, the system should:

- ask a short clarification
- or fall back to neutral mode

It must not:

- hallucinate a project
- self-handle a complex project request locally when it should route

### Files likely involved

- OpenClaw workspace prompts/config
- [openclaw_extensions/openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
- [openclaw_extensions/openmind-memory/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-memory/index.ts)
- [openclaw_extensions/openmind-telemetry/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts)
- OpenClaw rebuild/verify scripts

### Acceptance targets

1. Feishu/OpenClaw project requests route correctly without falling into local file-search behavior.
2. `continue / branch / status` are distinguished correctly in known project scenarios.
3. Ambiguous cases fail closed with clarification rather than bad routing.
4. OpenClaw no longer needs to behave like the project brain to be useful.

## 6. Work package 3: Project truth governance

### Objective

Turn the authority/project-scope model into a governed operating system rather than just a semantic convention.

### Required changes

#### 6.1 Authority anchor schema and governance

Define the durable authority anchor contract:

- required fields
- optional fields
- ownership
- refresh triggers
- stale detection
- review cadence

The authority anchor must explicitly cover:

- frozen facts
- style rules
- pinned authority docs
- current phase guidance

#### 6.2 Project-scoped runtime consistency

Ensure the entire hot path consistently respects:

- `project_id`
- authority priority
- prompt section ordering
- token budgeting protection for authority content

This is not just about retrieval.

It must include:

- prompt builder ordering
- available inputs ordering
- memory recall ordering
- telemetry visibility

#### 6.3 Admin/operator utilities

Provide simple operator-facing tools for:

- checking a project’s authority anchor freshness
- previewing the runtime context composition for a project
- spotting conflicts between authority and automatic knowledge

### Files likely involved

- [chatgptrest/advisor/prompt_builder.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/prompt_builder.py)
- [chatgptrest/advisor/task_intake.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_intake.py)
- [chatgptrest/kernel/context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)
- [chatgptrest/kernel/memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/memory_manager.py)
- planning authority-anchor files
- new ops/admin scripts

### Acceptance targets

1. Authority-anchor freshness can be checked operationally.
2. A project’s runtime context can be inspected and explained.
3. Automatic knowledge never overrides frozen facts/style rules.
4. Project-scoped retrieval behaves consistently across session boundaries.

## 7. Work package 4: Promotion operations and harness hardening

### Objective

Take promotion from "maintainable but shallow" to "operationally healthy and harness-governed".

### Required changes

#### 7.1 Promotion operations stabilization

Use the newly added inventory and maintenance harness as the operator backbone, then extend them with:

- scheduled reviewed refresh
- explicit promotion maintenance runbook
- release/readiness linkage where relevant
- clearer operator distinctions between:
  - refresh-only
  - apply-copy
  - live reviewed apply

#### 7.2 Promotion bottleneck diagnosis and recovery

Do not jump directly to a global active-rate target without diagnosis.

Required work:

- identify why active coverage remains so low
- confirm whether the dominant issue is:
  - no scheduled reviewed promotion
  - too-strict gates
  - missing runtime anchors
  - missing operator flow
- choose remediation based on evidence

#### 7.3 Harness-backed replay/eval

Add a formal harness layer that can replay:

- coding-agent lightweight flows
- OpenClaw project-routing flows
- project-scoped retrieval flows
- promotion maintenance flows

Harness output must become a gate for future changes in these planes.

### Files likely involved

- [ops/report_evomap_promotion_inventory.py](/vol1/1000/projects/ChatgptREST/ops/report_evomap_promotion_inventory.py)
- [ops/run_planning_review_maintenance.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_maintenance.py)
- planning review / runtime pack ops scripts
- systemd timer/service templates
- harness scripts and acceptance packs

### Acceptance targets

1. Promotion operations have a documented safe maintenance loop.
2. Active coverage bottlenecks are diagnosed with evidence, not guesses.
3. Harness can replay and evaluate the four critical planes:
   - coding-agent result path
   - OpenClaw routing path
   - project-scoped context path
   - promotion maintenance path
4. Future regressions in these planes become observable quickly.

## 8. Execution order

This stage should execute in this order:

1. Work package 1
2. Work package 2
3. Work package 3
4. Work package 4

Reason:

- package 1 fixes the most visible user-facing boundary
- package 2 fixes entry behavior
- package 3 stabilizes project truth governance
- package 4 hardens operations and future evolution

## 9. What not to do

The next stage should explicitly avoid these failure modes.

### 9.1 Do not create another broad product surface by accident

If a lightweight coding-agent mode is added, it must remain lightweight.

Do not let it silently regrow:

- broad advisor semantics
- unrelated product metadata
- internal controller complexity

### 9.2 Do not let OpenClaw become the project brain

Its value is correct association and routing, not deep multi-round business reasoning.

### 9.3 Do not let authority governance drift back into a loose convention

The authority anchor must become an operating rule, not just a well-written document.

### 9.4 Do not make promotion "smarter" before it becomes reliably operable

More automation without governance will reproduce the earlier drift problem at a new layer.

## 10. Definition of done for the whole next stage

The next stage is complete only when all of the following are true.

### 10.1 Coding-agent UX

- A mature coding agent can use ChatgptREST in the default path without learning advisor internals.
- Deep Research and long web tasks have a clear finality-and-answer flow.

### 10.2 OpenClaw UX

- OpenClaw reliably routes project requests instead of locally improvising.
- Continue/branch/status behavior is stable and explainable.

### 10.3 Project truth

- Authority-anchor governance is explicit and usable.
- Project-scoped runtime context is consistent and inspectable.

### 10.4 Operations

- Promotion maintenance has a stable operational loop.
- Harness replay covers the major product planes.

### 10.5 Platform clarity

- The default product surfaces now match the intended architecture:
  - coding agents get web/result-first behavior
  - OpenClaw gets plugin/backend orchestration
  - internal substrate remains internal

## 11. Bottom line

The `A-F` rollout created the foundation.

The next stage should finish the shape.

This means:

> fewer ambiguous surfaces, stronger defaults, governed project truth, and operationally mature promotion/harness support

That is the shortest path from the current `~70` state to the intended platform end-state.
