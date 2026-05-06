# Refined Next-Stage Full Execution Plan V2

Date: 2026-04-08

Supersedes:

- [Refined Next-Stage Full Execution Plan V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_refined_next_stage_full_execution_plan_v1.md)

Related decision records:

- [Dual-Model External Review Synthesis And Platform Decision V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_dual_model_external_review_synthesis_and_platform_decision_v1.md)
- [Post A-F Gap Analysis And Reflection V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_post_A_to_F_gap_analysis_and_reflection_v1.md)

## 1. What changed in V2

V2 keeps the same strategic direction as V1, but makes the program more executable in four ways:

1. it adds a mandatory **preflight evidence package** before the main implementation work
2. it explicitly absorbs the useful `claudegac` side-work suggestions into the main plan
3. it turns each deliverable into a detailed implementation contract with acceptance gates
4. it defines a single end-state and release-exit standard instead of a loose “improvement program”

This is now the authoritative full execution plan for the next stage.

## 2. Program intent

The next stage is a **boundary-consolidation release**.

Its purpose is:

> make `ChatgptREST` finally feel correct at its two real product edges:
> 
> - mature coding agents
> - `OpenClaw`

while hardening:

- project truth
- authority precedence
- release gating
- safe promotion operations

This stage is **not** a new substrate-expansion phase.

## 3. Final end-state to achieve

At the end of this program, the platform must have the following shape.

### 3.1 Coding-agent shape

For `Codex / Claude Code / Antigravity`, the default public story must be:

- `turn`
- `wait`
- `answer`
- `cancel`

Optional but non-default supporting actions:

- `conversation`
- `export`
- `artifacts`
- `status`

The default coding-agent lane must be:

- web-first
- result-first
- finality-aware
- low-cognitive-load

### 3.2 OpenClaw shape

`OpenClaw` must act as an **entry-layer orchestrator** that:

- associates project
- determines `continue / branch / status / clarify`
- routes into the backend
- shapes the user-facing response

It must not regrow into:

- a hidden project brain
- a local business-logic silo
- a local project file-search loop

### 3.3 Project truth shape

Project truth must be visibly layered:

1. authority anchor
2. project memory
3. project knowledge
4. runtime heuristics

And runtime precedence must be:

`authority anchor > project memory > project knowledge > runtime heuristics`

### 3.4 Release/operations shape

The release process must have **one gate pack** that verifies:

- coding-agent default lane
- OpenClaw entry behavior
- authority precedence
- promotion-maintenance safety

## 4. Scope decisions

### 4.1 Included in this stage

This program includes:

1. coding-agent public contract realignment
2. OpenClaw entry-policy completion
3. authority-anchor structural governance
4. release-blocking gate pack
5. only the promotion work needed to support safe release and future maintenance
6. the preflight audit and benchmark work needed to make the above safe

### 4.2 Explicitly excluded from this stage

This program does **not** include:

- broad promotion throughput optimization
- generic self-improving automation
- another expansion of advisor semantics
- a standalone new project-context subsystem
- large-scale document cleanup or archive migrations
- broad platform rebranding without contract change

## 5. Accepted and rejected side-work from review

The following `claudegac` side-work items are now part of the program:

### 5.1 Accepted as mandatory preflight or acceptance inputs

- `P1` scope_project data audit
- `P2` promotion pipeline diagnosis
- `P6` authority-doc integrity validation
- `P8` project-scoped retrieval baseline/replay set
- `P7` acceptance test scenarios, but integrated into the main deliverables rather than floating as detached skeletons

### 5.2 Accepted but downgraded to auxiliary audit

- `P3` documents-table audit
- `P5` planning runtime pack quality audit

These remain read-only analysis tasks in this stage. They do **not** become cleanup or mutation tracks here.

### 5.3 Removed from the plan

- `P4` PRS `_project_context.md` creation

Reason:

- this is already complete
- the file exists and is already referenced by the plugin/runtime path

## 6. Program structure

This stage will be executed as **five large work packages**.

They are sequenced so that later contracts are not built on bad assumptions.

### Work package 0: Preflight evidence pack
### Work package 1: `coding-agent-v1` default contract
### Work package 2: OpenClaw entry-policy contract
### Work package 3: Structural authority governance
### Work package 4: Unified release gate pack

Work package 4 includes the limited promotion-maintenance release plane needed for this stage.

## 7. Work package 0: Preflight evidence pack

### Objective

Produce the data and baseline evidence needed so the rest of the program is implemented on verified reality instead of assumptions.

### Required outputs

#### 7.1 Scope-project data audit

Must answer:

- how many `atoms.scope_project` values disagree with `documents.project`
- whether orphan atoms/episodes/documents exist
- whether project names contain obvious garbage/test values

### Output artifact

- one audit report with SQL evidence
- one normalization recommendation table
- one migration-safety note for future backfill/update logic

### Implementation surface

- EvoMap DB inspection scripts or notebooks
- read-only SQL reports under `ops/` or `docs/dev_log/artifacts/`

### Acceptance

1. The report quantifies mismatches, not just describes them.
2. The report includes a list of candidate invalid/noisy project identifiers.
3. The report clearly states whether a future `scope_project` backfill is safe, conditional, or blocked.

#### 7.2 Promotion pipeline diagnosis

Must answer:

- how often promotion actually runs
- which reviewed/active/staged paths are active today
- whether low active coverage is mainly:
  - gate strictness
  - absent scheduling
  - missing promotion calls
  - bad source quality

### Output artifact

- one promotion diagnosis report
- one table of current stage counts and time distribution
- one recommendation section limited to this stage’s safe operational needs

### Acceptance

1. The report identifies the dominant failure mode with evidence.
2. The report distinguishes runtime scheduling absence from content-quality rejection.
3. The report does **not** recommend broad throughput work as part of this stage unless data proves it is blocking the current release shape.

#### 7.3 Authority-doc integrity scan

Must validate all project authority anchors and their pinned authority docs for:

- path existence
- non-empty content
- last-modified time
- stale status

### Output artifact

- one integrity report
- one list of stale/missing authority references

### Acceptance

1. The report covers every known project authority anchor.
2. Missing or stale authority inputs are explicitly listed.
3. The report is machine-rerunnable.

#### 7.4 Project-scoped retrieval baseline/replay set

Must define a minimal but stable query set across multiple projects to compare retrieval behavior before and after scope hardening.

### Output artifact

- one benchmark corpus definition
- one baseline result snapshot
- one replay instruction/runner reference

### Acceptance

1. At least three project-distinguishing query families exist.
2. Each query has expected project-specific relevance behavior.
3. The baseline is saved and reusable in later release gates.

#### 7.5 Auxiliary read-only audits

Two read-only auxiliary audits are included:

- documents-table audit
- planning runtime pack audit

These exist to expose noise and stale pack risk, not to trigger cleanup projects inside this stage.

### Acceptance

1. Both audits are read-only.
2. Both produce actionable reports.
3. Neither expands into cleanup/archival execution within this program.

## 8. Work package 1: `coding-agent-v1` default contract

### Objective

Freeze a narrow, explicit, default contract for mature coding agents.

### Required product behavior

The default contract must support:

- submit a web-backed task
- wait for finality
- fetch the authoritative answer
- cancel

The default contract must not require:

- advisor literacy
- workspace/control-plane understanding
- manual interpretation of intermediate session payloads

### Implementation requirements

#### 8.1 Public surface shape

Either:

- dedicated `coding_agent_*` tool names

or:

- a dedicated `coding-agent-v1` mode on the existing public surface

But whichever implementation is chosen, the following must be true:

- wrappers treat it as a separate contract
- docs teach it as the default coding-agent path
- validation gates test it as a separate contract
- broad advisor mode is not the default story

#### 8.2 Request schema

The default lane must accept only a narrow request shape.

At minimum:

- `message`
- optional `session_id`
- optional `project_id`
- optional attachments/repo hint
- constrained execution profile enum

The default lane must reject, not merely ignore, advisor-only fields such as:

- `workspace_request`
- `contract_patch`
- `memory_capture`
- broad control-plane knobs

#### 8.3 Response schema

The default lane must return:

- `status`
- `answer_state`
- `answer_ready`
- authoritative answer handle/path
- recommended next action

Inline preview text may remain as convenience only.

Authoritative completion must be based on:

- `answer_state`
- authoritative answer source

Never on `last_answer`.

#### 8.4 Wrapper and docs alignment

All coding-agent wrappers, skill docs, quickstarts, and examples must align to the default lane.

No default example should teach:

- low-level `/v1/jobs`
- broad advisor patching
- generic `/v3/agent/*` mental models

### Main code areas

- [chatgptrest/mcp/agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py)
- [chatgptrest/api/routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [skills-src/chatgptrest-call/scripts/chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py)
- [docs/contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/contract_v1.md)
- [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)
- public MCP validation/eval files

### Acceptance tests

The default lane must pass the following scenarios:

1. long Deep Research success:
   - `turn -> wait -> answer`
   - authoritative answer fetched cleanly
2. provisional completion:
   - `answer_ready=false`
   - no fake terminal success
3. no-job session:
   - answer retrieval still behaves coherently
4. short answer compatibility:
   - no regression for non-research flows

### Acceptance gate

This work package is complete only if:

1. a mature coding agent can complete a long task using only the default lane
2. the default docs/examples do not require advisor/control-plane literacy
3. `completed + empty answer + unclear next step` is impossible in the default lane
4. the public contract gate fails if examples drift back into advisor-heavy behavior

## 9. Work package 2: OpenClaw entry-policy contract

### Objective

Freeze OpenClaw’s role as the rules-first project associator and request-mode selector.

### Required runtime behavior

For known project traffic, OpenClaw must explicitly determine:

- `project_id`
- `association_source`
- `task_mode`

Where:

- `association_source ∈ {explicit, rule, cache, none}`
- `task_mode ∈ {continue, branch, status, new, clarify}`

### Implementation requirements

#### 9.1 Rules-first project association

Project association must be primarily determined by:

- explicit project references
- stable alias tables
- conservative deterministic rules

Model inference may assist, but it cannot be the sole owner of project association.

#### 9.2 Conservative mode selection

OpenClaw must not guess aggressively.

If it cannot confidently distinguish:

- continue
- branch
- status

it must choose:

- `clarify`
- or neutral fallback

never silent overcommit.

#### 9.3 Plugin ownership boundary

Plugins may implement the entry-policy contract.

They must not become hidden owners of project brain logic through scattered regex, cache, and side heuristics.

#### 9.4 Entry-layer fail-closed behavior

When project association is ambiguous, the entry layer must:

- ask a short clarification
- or fall back to neutral mode

It must not:

- hallucinate a project
- self-handle a complex project request locally
- drop into local file search instead of routing

### Main code areas

- OpenClaw main workspace prompts/config
- [openclaw_extensions/openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
- [openclaw_extensions/openmind-memory/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-memory/index.ts)
- [openclaw_extensions/openmind-telemetry/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts)
- replay/eval tooling for OpenClaw routing

### Acceptance tests

Must include:

1. deterministic known-project continue case
2. deterministic known-project branch case
3. deterministic known-project status case
4. ambiguous mixed-project case
5. non-project neutral case

### Acceptance gate

This work package is complete only if:

1. known project requests route without local ad hoc behavior
2. `continue / branch / status / clarify` are explicit and replayable
3. ambiguous cases fail closed into clarification
4. project association provenance is visible at runtime

## 10. Work package 3: Structural authority governance

### Objective

Turn authority precedence from a prompt convention into a structural runtime contract plus an operator discipline.

### Required runtime model

Each project truth stack must contain:

1. authority anchor
2. project memory
3. project knowledge
4. runtime heuristics

Authority must be structurally first-class.

### Implementation requirements

#### 10.1 Authority anchor schema

Each authority anchor must minimally expose:

- `owner`
- `last_reviewed_at`
- `frozen_facts`
- `style_rules`
- `pinned_authority_inputs`
- `current_phase_framing`

#### 10.2 First-class authority source

Runtime context assembly must represent authority as a dedicated source with:

- higher ordering than project memory and knowledge
- protected token budget
- non-evictable or strongly protected trimming behavior

#### 10.3 Conflict visibility

Operators must be able to inspect:

- stale authority anchors
- missing authority docs
- lower-layer conflicts with authority
- context composition previews

#### 10.4 Project/global fallback labeling

If global or unscoped material is used in project-scoped assembly, it must be labeled as supplemental and remain lower priority than authority.

#### 10.5 Authority-doc integrity checks

The authority-doc validation from Work package 0 must be made part of the governance loop, not left as a one-off report.

### Main code and data areas

- authority-anchor files in planning/project roots
- [chatgptrest/kernel/context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)
- [chatgptrest/cognitive/context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
- [chatgptrest/advisor/prompt_builder.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/prompt_builder.py)
- project-memory / retrieval entrypoints
- operator verification/report scripts

### Acceptance tests

Must include:

1. authority-vs-project-memory conflict fixture
2. authority-vs-project-knowledge conflict fixture
3. stale authority anchor detection case
4. missing authority-doc case
5. token trimming pressure case

### Acceptance gate

This work package is complete only if:

1. authority wins over lower layers at runtime
2. that ordering is visible in context previews
3. stale/conflicting authority is detectable before release
4. replay fixtures prove authority wins under conflict

## 11. Work package 4: Unified release gate pack

### Objective

Turn the next stage into a real release with hard architectural gates.

### Required behavior

There must be one manifest-driven gate pack that blocks release if any of the core boundary contracts regress.

### Required gate planes

#### 11.1 Coding-agent lane gate

Must verify:

- default submit/wait/answer flow
- long-result finality
- no terminal ambiguity
- wrapper and doc alignment

#### 11.2 OpenClaw entry gate

Must verify:

- project association correctness
- task_mode correctness
- clarify fail-closed behavior
- no fallback to local ad hoc handling

#### 11.3 Authority precedence gate

Must verify:

- authority beats project memory
- authority beats project knowledge
- conflicts are visible
- token trimming does not silently demote authority

#### 11.4 Promotion-maintenance safety gate

Must verify:

- promotion inventory generation
- refresh-only maintenance cycle
- pre/post evidence pack generation
- no unsafe live promotion side effects

### Promotion work explicitly included here

Only the following promotion work is included in this stage:

- diagnosis from preflight
- maintenance harness
- refresh-only safe operation
- release evidence generation

This stage does **not** include:

- broad active-coverage targets
- algorithmic throughput tuning
- broad auto-promotion work

### Main code and tooling areas

- [chatgptrest/eval/harness.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/harness.py)
- existing public-surface launch gates
- OpenClaw replay tooling
- promotion maintenance ops scripts
- manifest/orchestration docs and runner entrypoints

### Acceptance gate

This work package is complete only if:

1. one runner or manifest can execute all four gate planes
2. any invariant regression fails the release
3. evidence artifacts persist per run
4. release readiness can be inspected without re-reading ad hoc logs

## 12. Program execution order

This is one full program, but the build order must still be disciplined.

### Order

1. Work package 0
2. Work package 1
3. Work package 2 and Work package 3 in parallel after package 1 contract shape is frozen
4. Work package 4 across the completed surfaces

### Why this order

- preflight prevents building on false assumptions
- coding-agent-v1 defines the user-facing default contract
- OpenClaw and authority then lock the two main boundary contracts around that default
- the gate pack freezes all of them into release reality

## 13. Program-level acceptance matrix

The full program is complete only when **all** of the following are true.

### Product acceptance

- mature coding agents default into a web/result-first contract
- OpenClaw reliably behaves as an entry orchestrator, not a project brain

### Truth acceptance

- authority anchor is structurally dominant and operationally governed

### Operations acceptance

- one release gate pack can reject regressions in the three boundary contracts above

### Drift resistance acceptance

- the platform no longer depends on prose intent alone to preserve these boundaries

### Evidence acceptance

- preflight evidence pack exists
- gate artifacts exist
- operator-facing reports exist for authority integrity and promotion maintenance

## 14. Explicit stop conditions

The program should be considered **not done** if any of the following remain true:

1. coding agents still need advisor/control-plane literacy in the default path
2. OpenClaw still silently guesses project or task mode
3. authority precedence is enforced only by prompt wording
4. release readiness still depends on manual interpretation rather than gate artifacts

## 15. Bottom line

This stage should not be judged by how many internals were improved.

It should be judged by one question:

> After completion, does the platform visibly and reliably present the right shape to mature coding agents and to OpenClaw?

If the answer is still “mostly, but with caveats,” the program is incomplete.
