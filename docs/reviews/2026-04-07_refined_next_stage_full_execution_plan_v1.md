# Refined Next-Stage Full Execution Plan V1

Date: 2026-04-07

## 1. Program intent

This plan replaces the earlier broad next-stage plan with one refined execution program shaped by:

- post `A-F` reflection
- the external `ChatGPT Pro` review
- the `Gemini` runtime evidence
- current platform boundaries and remaining drift risks

This is not a patch list.

It is one full execution program whose purpose is:

> make `ChatgptREST` finally feel correct to mature coding agents and to `OpenClaw`, while hardening the project-truth boundary and release discipline.

## 2. End-state to achieve

At the end of this program, the platform must have this shape.

### 2.1 Coding-agent shape

For `Codex / Claude Code / Antigravity`, the default public story must be:

- `turn`
- `wait`
- `answer`
- `cancel`

Optionally:

- `conversation`
- `export`
- `artifacts`

The default lane must be:

- web-first
- result-first
- finality-aware
- low-cognitive-load

### 2.2 OpenClaw shape

`OpenClaw` must be the entry-layer orchestrator that:

- associates project
- determines `continue / branch / status / clarify`
- routes into the backend
- shapes the response for the user

It must not be the hidden project brain.

### 2.3 Project truth shape

Project truth must be visibly layered:

1. authority anchor
2. project memory
3. project knowledge
4. runtime heuristics

And the runtime must enforce:

`authority anchor > project memory > project knowledge > runtime heuristics`

### 2.4 Operations shape

The release process must have one gate pack that verifies:

- coding-agent default lane
- OpenClaw entry behavior
- authority precedence
- promotion-maintenance safety

## 3. Scope included

This program includes:

1. coding-agent public contract realignment
2. OpenClaw entry-policy completion
3. authority-anchor structural governance
4. release-blocking harness pack
5. only the promotion work needed to support safe release and future maintenance

## 4. Scope explicitly excluded

This program does **not** include:

- broad promotion throughput optimization
- generalized self-improving automation
- another expansion of advisor semantics
- another independent project-context subsystem
- broad platform rebranding without contract changes

## 5. Deliverable A: `coding-agent-v1` default contract

### Objective

Freeze a separate, explicit default contract for mature coding agents.

### Required behavior

The default contract must support:

- submit a web-backed task
- wait for finality
- fetch authoritative answer
- cancel

The default contract must not require:

- broad advisor understanding
- control-plane literacy
- workspace semantics
- manual interpretation of intermediate lifecycle fields

### Implementation requirements

#### 5.1 Public surface

Either:

- dedicated `coding_agent_*` tool names

or:

- a dedicated `coding-agent-v1` mode inside the existing public MCP

But whichever implementation is chosen, the default docs and wrappers must treat it as a genuinely separate contract.

It must be impossible for the default coding-agent path to silently fall back into broad advisor semantics.

#### 5.2 Request schema

The default contract should allow only a narrow request shape.

At minimum:

- message
- optional session_id
- optional project_id
- optional attachments / repo pointer
- small execution profile enum

The default path must reject, not silently ignore, advisor-only fields such as:

- workspace_request
- contract_patch
- memory_capture
- broad control-plane overrides

#### 5.3 Response contract

The default path must return:

- status
- answer_state
- answer_ready
- authoritative answer handle
- recommended next action

Short inline text may remain a convenience.

But finality must be defined by:

- `answer_state`
- authoritative answer source

Never by legacy `last_answer`.

#### 5.4 Wrapper alignment

All coding-agent wrappers and examples must switch to this default lane.

No default example should teach:

- low-level `/v1/jobs`
- broad advisor patching
- raw `/v3/agent/*` mental model

### Files likely involved

- [chatgptrest/mcp/agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py)
- [chatgptrest/api/routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [skills-src/chatgptrest-call/scripts/chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py)
- [docs/contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/contract_v1.md)
- [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)
- relevant MCP validation/eval files

### Acceptance

1. A Deep Research task can be completed by a coding agent with only:
   - turn
   - wait
   - answer
2. No default coding-agent doc teaches advisor/control-plane internals.
3. `completed + empty answer + unclear next step` is impossible in the default lane.
4. Public contract tests fail if default examples drift back into advisor-heavy behavior.

## 6. Deliverable B: OpenClaw entry-policy contract

### Objective

Freeze OpenClaw’s role as the rules-first project associator and request-mode selector.

### Required behavior

For known project traffic, OpenClaw must explicitly determine:

- `project_id`
- `association_source`
- `task_mode`

Where:

- `association_source ∈ {explicit, rule, cache, none}`
- `task_mode ∈ {continue, branch, status, new, clarify}`

### Implementation requirements

#### 6.1 Rules-first association

Project association must be driven primarily by:

- explicit project references
- stable alias tables
- conservative deterministic rules

Model inference can help, but it cannot be the sole owner of project association.

#### 6.2 Conservative mode selection

OpenClaw must not over-assume.

If it cannot confidently distinguish:

- continue
- branch
- status

it must enter `clarify` or neutral handling rather than guess.

#### 6.3 Plugin simplification

Project-brain logic should not remain hidden in plugin heuristics.

Plugins may implement the entry-policy contract.

They should not define that contract implicitly by scattered regex/caching behavior.

### Files likely involved

- OpenClaw main workspace prompts/config
- [openclaw_extensions/openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
- [openclaw_extensions/openmind-memory/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-memory/index.ts)
- [openclaw_extensions/openmind-telemetry/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts)
- replay/eval tooling for OpenClaw routing

### Acceptance

1. Known project requests carry `project_id`, `association_source`, and `task_mode`.
2. Deterministic continue/branch/status fixtures replay green.
3. Ambiguous project fixtures fail closed into clarification.
4. OpenClaw no longer falls back into local file-search or local project-brain behavior for routed project work.

## 7. Deliverable C: Structural authority governance

### Objective

Turn authority precedence from a prompt convention into a structural runtime contract.

### Required behavior

The runtime must expose a first-class authority layer, not just inject authority text late in the prompt.

### Implementation requirements

#### 7.1 Authority anchor schema

Each project authority anchor must minimally include:

- owner
- last_reviewed_at
- frozen_facts
- style_rules
- pinned_authority_inputs
- current_phase_framing

#### 7.2 Structural context representation

Runtime context assembly must have a dedicated authority source with:

- higher ordering than project memory/knowledge
- reserved token budget
- non-evictable or strongly protected trimming behavior

#### 7.3 Conflict visibility

Operators must be able to inspect:

- stale authority anchors
- conflicts between authority and lower layers
- runtime context composition preview

#### 7.4 Project-scoped fallback labeling

If global/unscoped content appears in a project-scoped assembly, it must be labeled as supplemental and remain lower priority than authority.

### Files likely involved

- authority-anchor files in planning/project roots
- [chatgptrest/kernel/context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)
- [chatgptrest/cognitive/context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
- [chatgptrest/advisor/prompt_builder.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/prompt_builder.py)
- project-memory / retrieval entrypoints
- operator utilities and review commands

### Acceptance

1. Authority always outranks lower layers in runtime assembly.
2. Context previews make the layer ordering visible.
3. Stale/conflicting authority is detectable before release.
4. Replay fixtures prove authority wins over conflicting project memory/knowledge.

## 8. Deliverable D: One release-blocking gate pack

### Objective

Turn the next stage into a release with hard architectural gates rather than “best effort” validation.

### Required behavior

There must be one manifest-driven gate pack that blocks release if any core invariant regresses.

### Required gate planes

#### 8.1 Coding-agent lane gate

Must verify:

- default submit/wait/answer flow
- long-result finality
- no terminal ambiguity
- wrapper/default docs alignment

#### 8.2 OpenClaw entry gate

Must verify:

- project association correctness
- task_mode correctness
- clarify fail-closed behavior
- no fallback to local ad hoc handling

#### 8.3 Authority precedence gate

Must verify:

- authority beats project memory
- authority beats project knowledge
- lower-layer conflicts are visible
- token trimming does not evict authority first

#### 8.4 Promotion-maintenance safety gate

Must verify:

- inventory generation
- refresh-only maintenance cycle
- pre/post evidence pack generation
- no unsafe live promotion side effects

### Files likely involved

- [chatgptrest/eval/harness.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/harness.py)
- existing public-surface launch gates
- OpenClaw replay tooling
- promotion maintenance ops scripts
- new manifest/orchestration docs

### Acceptance

1. One command or one runner manifest can exercise all four gate planes.
2. Any invariant regression fails the release.
3. Evidence artifacts are persisted per run.
4. Release readiness is inspectable without re-reading ad hoc logs.

## 9. Program sequencing

This is one full program, but the build order still matters.

### Build order

1. Deliverable A
2. Deliverable B and C in parallel once A’s contract shape is frozen
3. Deliverable D across the already-built surfaces

### Why this order

- A defines the user-facing default contract
- B and C define the two highest-risk boundary contracts around that default
- D freezes those contracts into operational reality

## 10. Program-level acceptance

The full program is complete only when all of the following are true.

### Product acceptance

- mature coding agents default into a web/result-first contract
- OpenClaw reliably behaves as an entry orchestrator, not a project brain

### Truth acceptance

- authority anchor is structurally dominant and operationally governed

### Operations acceptance

- one release gate pack can reject regressions in the three boundaries above

### Drift resistance acceptance

- the platform no longer depends on prose intent alone to preserve these boundaries

## 11. What success should feel like

When this program is complete:

- coding agents should feel that ChatgptREST is simpler, not merely more correct
- OpenClaw should feel more predictable, not merely more powerful
- project truth should feel governable, not merely documented
- releases should feel auditable, not merely tested

## 12. Final note

This program intentionally avoids another long tail of unrelated micro-fixes.

Its purpose is to finish the platform shape that is already visible after `A-F`, not to reopen the architecture.
