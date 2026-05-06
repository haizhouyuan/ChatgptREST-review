# 2026-03-24 Public Agent Deliberation And Maint Unification Blueprint v1

## Status

This blueprint defines the next architectural layer above the already-completed:

- public agent contract-first control plane
- public agent effects/delivery surface
- Codex Maint Controller on `sre.fix_request` lanes

The purpose of this blueprint is to prevent the next stage from fragmenting into:

- one northbound brain for general agent work
- a second northbound brain for review/deliberation
- a third watchdog brain for maintenance

That outcome would produce multiple parallel controller universes instead of a unified cognitive control plane.

## Goal

Create one coherent architecture where:

1. **Public Agent** remains the single northbound task entry for external agents and clients
2. **deliberation** becomes an internal advanced reasoning plane under Public Agent, not a second public controller
3. **Maint Controller** remains the only separate controller because it has different privileges, action boundaries, and risk model
4. **OpenClaw `maintagent`** becomes the maintenance brain holding canonical machine context from `/vol1/maint`
5. **`guardian` is removed** and its responsibilities are absorbed into `maint_daemon` and `maintagent`

## Non-Goals

This blueprint does **not**:

- create a second public northbound surface parallel to Public Agent
- turn every agent into a full-machine-context operator
- replace deterministic packaging/validation with LLM reasoning
- merge maintenance control into ordinary public task execution
- productize a full tmux/TUI operator UX in this phase

## Core Decisions

### 1. Public Agent Stays The Only General Northbound Entry

External coding agents and wrappers should still treat:

- public MCP
- `/v3/agent/*`

as the canonical northbound agent surface.

Review, debate, dual-review, and report-generation-with-hard-channel-rules must be added as **internal execution modes** under Public Agent.

### 2. Review Is A Mode, Not A Peer Controller

`Review Controller` should **not** become a second public entry peer to Public Agent.

Instead:

- Public Agent handles intake, contract normalization, status/delivery
- a dedicated **deliberation plane** under Public Agent handles:
  - `single_review`
  - `dual_review`
  - `red_blue_debate`
  - report synthesis after review

### 3. Maint Controller Remains Separate

Maintenance work cannot be treated as ordinary public-agent execution because it has different:

- authority
- runbook constraints
- action allowlists
- escalation semantics
- operator takeover expectations

So Maint Controller stays separate.

### 4. `maintagent` Owns Machine Context

The canonical machine and workspace context should live in `/vol1/maint`, and `OpenClaw maintagent` should be the default reader of that context.

Normal business/task agents should only know the pointer to the canonical machine context, not preload the entire machine state.

### 5. `guardian` Is Removed

`guardian` is no longer allowed to remain as a third semi-independent maintenance brain.

Its responsibilities are absorbed as follows:

- deterministic sweep, issue housekeeping, trigger/notify plumbing -> `maint_daemon`
- judgment, cross-system reasoning, escalation to `main` -> `maintagent`

## Target Architecture

### A. Public Agent Control Plane

Public Agent remains responsible for:

- canonical task intake
- contract normalization
- clarify/followup handling
- session continuity
- lifecycle/delivery/effects projection
- northbound MCP and `/v3/agent/*` semantics

### B. Public Agent Deliberation Plane

Deliberation is an internal Public Agent execution plane for high-value review work.

It is used for:

- codebase review
- brainstorming
- plan/strategy review
- framework/methodology review
- research material review
- material-to-report tasks with explicit review semantics
- red/blue debate

### C. Deterministic Work-Package Plane

Deterministic package/channel operations must live in a non-LLM tool plane under the same MCP server.

This plane owns:

- local parameter normalization
- pack compilation
- `master_single` validation
- source manifest validation
- repo-first vs attachment-first channel compilation
- file-count limit enforcement
- upload-chip fail-closed validation
- idempotency normalization

These are deterministic compiler/gate tasks, not reasoning tasks.

### D. Maint Controller

Maint Controller remains the dedicated maintenance control plane implemented on top of `sre.fix_request` lanes.

It owns:

- maintenance run ledger
- repair/autofix orchestration
- guarded action execution
- incident-linked Codex escalation
- operator attach on maintenance lanes

### E. OpenClaw `maintagent`

`maintagent` becomes the maintenance brain and default holder of machine context.

It owns:

- whole-machine baseline awareness
- OpenClaw topology awareness
- repo/worktree/service baseline awareness
- reasoning over detector output
- escalating actionable deltas to `main`

### F. `maint_daemon`

`maint_daemon` becomes the deterministic sensor/evidence plane.

It owns:

- periodic probes
- issue sweeps
- incident generation
- evidence capture
- repair.check triggers
- notify triggers

It is not the maintenance brain.

### G. `/vol1/maint`

`/vol1/maint` becomes the canonical machine-context repository.

At minimum, the following remain canonical:

- `/vol1/maint/docs/2026-03-15_maintagent_memory_index.md`
- `/vol1/maint/docs/2026-03-15_maintagent_machine_snapshot.md`
- `/vol1/maint/docs/2026-03-15_maintagent_repo_workspace_snapshot.md`
- `/vol1/maint/exports/maintagent_memory_packet_2026-03-15.json`

## Scenario Mapping

### Ordinary Public Agent

Use Public Agent directly for:

- planning
- consult
- report
- image
- normal research asks
- workspace actions

### Deliberation Plane Under Public Agent

Use Public Agent `deliberation` execution mode for:

- code review
- brainstorm with anti-compliance pressure
- plan review
- framework review
- direct material review
- dual model critique
- red/blue debate

### Maint Controller

Use Maint Controller for:

- runtime degradation
- repair/autofix
- blocked/cooldown recurrence
- viewer/driver/API mismatch
- issue-linked maintenance escalation

### `maintagent`

Use `maintagent` for:

- ongoing machine/watchdog cognition
- deciding whether a detector signal is actionable
- waking or briefing `main`
- cross-workspace maintenance reasoning

## Unified MCP Surface

### Public-Agent Backed MCP Tools

Keep:

- `advisor_agent_turn`
- `advisor_agent_status`
- `advisor_agent_cancel`

Add:

- `deliberation_start`
- `deliberation_status`
- `deliberation_cancel`
- `deliberation_attach`

### Deterministic MCP Tools

Add deterministic tools under the same MCP server:

- `work_package_prepare`
- `work_package_validate`
- `work_package_compile_channel`
- `work_package_submit`
- `work_package_status`
- `work_package_cancel`

### Tool Boundary Rule

`deliberation_start` may call or orchestrate the deterministic work-package tools, but deterministic compilation and fail-closed validation must not depend on model reasoning.

## Deliberation Contracts

### `deliberation_start`

Required fields:

- `task_profile`
  - `code_review`
  - `brainstorm`
  - `plan_review`
  - `framework_review`
  - `report_generation`
- `reasoning_mode`
  - `single_review`
  - `dual_review`
  - `red_blue_debate`
- `target`
  - `chatgpt_pro`
  - `gemini_dt`
  - `dual`
- `pack_dir`
- `master_single`
- `channel_policy`
  - `repo_first`
  - `attachments_first`
  - `repo_plus_attachments`
- `question`
- `must_answer`
- `acceptance`
- `delivery_mode`
- `idempotency_key`

Recommended optional fields:

- `source_manifest`
- `expected_files`
- `review_profile`
- `debate_profile`
- `notify_done`
- `attachments`

### `deliberation_status`

Must return:

- canonical session/run id
- stage
- current reviewer lane(s)
- submitted files/channels
- current lifecycle
- partial artifacts if available

### `deliberation_attach`

This is an operator-assist surface, not a full TUI controller.

It should return:

- attach instructions
- current lane/session pointers
- last stage output
- next safe intervention point

## Hard Channel Rules

These rules must be enforced as hard policy, not best-effort hints.

### GeminiDT

- `GeminiDT` must only use `gemini_web.ask`
- no silent downgrade to Gemini CLI
- no silent downgrade to generic Gemini MCP text path

### ChatGPT Pro

- `ChatGPT Pro` must use the official ChatGPT web lane
- no trivial/smoke prompts on Pro
- no low-value “confirm connectivity” asks on Pro

### File/Package Rules

- `master_single` is mandatory
- key information must not exist only in annex files
- required material not represented in `master_single` -> fail closed
- Gemini file-count overflow -> fail closed
- upload chip mismatch vs expected file list -> fail closed

### Target Rules

- `target=chatgpt_pro|gemini_dt|dual` is hard
- server is not allowed to silently swap reviewer lane

### Channel Policy Rules

- `repo_first` is default for code/text-heavy review
- `attachments_first` is reserved for raw attachment fidelity cases
- `repo_plus_attachments` is for mixed cases where repo mirror holds the corpus and a small set of raw attachments must remain visible

## Red/Blue Debate Design

### Default Role Mapping

Default:

- `Blue = ChatGPT Pro`
- `Red = GeminiDT`

This default may be overridden, but the profile must be explicit.

### Debate Stages

The debate pipeline must be:

1. `independent_pass`
2. `role_assignment`
3. `red_attack`
4. `blue_defense`
5. `arbiter_verdict`

The two models should not simply chat back and forth without structure.

### Required Structured Output

Every debate run must converge to:

- `shared_facts`
- `key_disagreements`
- `known_unknowns`
- `verdict`
- `recommendation_strength`
- `next_validation_actions`

### Scenario Guidance

Use `red_blue_debate` for:

- strategy review
- plan review
- framework review
- non-consensus research judgment
- high-value brainstorming where compliance bias is dangerous

Do not default to `red_blue_debate` for:

- low-risk summarization
- straight extraction
- ordinary report drafting

## Existing Module Reuse Map

### Public Agent / Deliberation Reuse

Reuse:

- `chatgptrest/api/routes_agent_v3.py`
- `chatgptrest/mcp/agent_mcp.py`
- `chatgptrest/advisor/ask_contract.py`
- `chatgptrest/advisor/prompt_builder.py`
- `chatgptrest/api/routes_consult.py`

### Deterministic Review Packaging Reuse

Reuse:

- `ops/code_review_pack.py`
- `ops/sync_review_repo.py`
- `.agents/workflows/code-review-upload.md`
- `skills-src/chatgptrest-call/SKILL.md`

### Maint Reuse

Reuse:

- `chatgptrest/executors/sre.py`
- `chatgptrest/executors/repair.py`
- `ops/maint_daemon.py`
- `chatgptrest/ops_shared/maint_memory.py`

### OpenClaw Reuse

Reuse:

- `config/topology.yaml`
- `scripts/rebuild_openclaw_openmind_stack.py`

### Remove / Absorb

`ops/openclaw_guardian_run.py` should not remain a first-class parallel maintenance brain.

It should either:

- be absorbed into `maint_daemon` and `maintagent`
- or survive only as a temporary compatibility shim during migration

## Guardian Removal Map

### Functions To Absorb Into `maint_daemon`

- periodic patrol scheduling semantics
- issue sweep / stale issue housekeeping
- deterministic health polling
- notify trigger plumbing

### Functions To Absorb Into `maintagent`

- deciding whether a signal is actionable
- deciding whether `main` needs to be disturbed
- cross-system reasoning over detector deltas
- higher-level maintenance triage

### What Must Not Survive

Do not preserve `guardian` as:

- a second maintenance cognition layer
- a second attention arbiter
- a second independent escalation policy

## Memory And Runbook Model

### Public Agent Deliberation Memory

Deliberation memory should be split into:

- `domain_memory`
- `review_memory`
- `artifact_memory`

### Maint Memory

Maint memory should continue to rely on:

- canonical `/vol1/maint` machine context
- recurring action preferences
- incident-local snapshots

### Runbooks

The system should maintain at least:

- `code_review_runbook`
- `strategy_review_runbook`
- `framework_review_runbook`
- `report_generation_runbook`
- `red_blue_debate_runbook`
- `gemini_dt_channel_runbook`
- `repo_first_review_runbook`
- maintenance runbooks already used by repair/maint flows

## Canonical Ledger Philosophy

This blueprint does **not** authorize a new independent state universe.

The architectural rule is:

- Public Agent keeps its canonical task/session ledger
- Maint Controller keeps its canonical `sre lane` ledger
- deliberation is represented as a Public Agent execution plane, not a second top-level run universe

Deterministic work-package tools may emit artifacts, but those artifacts must remain subordinate to the canonical northbound session/run state.

## Rollout Principle

The migration should happen in this order:

1. absorb `guardian` responsibilities
2. make `maintagent` the canonical maintenance brain over `/vol1/maint`
3. introduce deterministic work-package MCP tools
4. add `deliberation_start` in `single_review`
5. extend to `dual_review`
6. extend to `red_blue_debate`
7. align wrappers/docs so all coding agents know:
   - ordinary tasks -> Public Agent
   - high-value review -> Public Agent deliberation tools
   - maintenance -> `maintagent` / Maint Controller

## Acceptance Criteria

This blueprint is considered realized only when:

1. `guardian` is removed or reduced to a temporary compatibility shim
2. `maintagent` is the default holder of canonical machine context
3. `maint_daemon` is the deterministic maintenance sensor/evidence plane
4. `deliberation_start` is available on the MCP surface
5. deterministic work-package tools exist and enforce fail-closed channel policy
6. `dual_review` and `red_blue_debate` are available as structured Public Agent execution modes
7. skill/wrapper/docs all teach the same default usage model

## One-Line Summary

The system should converge to:

- **one public northbound task brain** (`Public Agent`)
- **one internal review/deliberation plane** under that brain
- **one separate maintenance brain** (`maintagent` + Maint Controller)
- **one canonical machine context** (`/vol1/maint`)

and no surviving `guardian`-style parallel cognition layer.
