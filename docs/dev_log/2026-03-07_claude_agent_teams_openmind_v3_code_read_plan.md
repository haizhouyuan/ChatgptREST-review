# Claude Code Agent Teams + OpenMind V3

Date: 2026-03-07
Author: Codex
Scope: code reading only; no runtime or business code changes in this pass

## Purpose

This note records the current implementation reality for "Claude Code agent teams that get smarter over time", based on direct code reading with GitNexus and source inspection. It is written as a development handoff, not as a speculative architecture note.

## Executive Summary

The correct runtime seam is `ChatgptREST`, not the standalone `openmind/` package.

Why:

- `ChatgptREST` already has a live execution path for Claude tasks and team dispatch:
  - `chatgptrest/api/routes_advisor_v3.py`
  - `chatgptrest/kernel/cc_native.py`
  - `chatgptrest/kernel/cc_executor.py`
- `ChatgptREST` already emits or stores the three feedback primitives needed for learning:
  - `TraceEvent`
  - `EvoMapObserver`
  - `MemoryManager` / routing outcome feedback
- `openmind/` is still useful as the design and governance reference, but its package-level `evomap/` and `workflows/` modules are still placeholder-level in practice; the current real writeback pattern is export/doc driven.

Therefore:

- team execution and learning feedback should be implemented in `ChatgptREST`
- `openmind/` should remain the policy/model reference and export sink
- do not start by building a second runtime in `openmind/`

## Code Reality

### 1. HTTP team entrypoint already exists

`chatgptrest/api/routes_advisor_v3.py:1180`

Route:

- `POST /cc-dispatch-team`

Current behavior:

- calls `_init_once()`
- gets `state["cc_native"]`
- constructs `CcTask`
- requires `team`
- calls `await cc.dispatch_team(task, team=team)`

This means team dispatch is already exposed through the API surface.

### 2. The active runtime path is `CcNativeExecutor`, not `CcExecutor`

`chatgptrest/api/routes_advisor_v3.py:188`
`chatgptrest/api/routes_advisor_v3.py:1180`
`chatgptrest/kernel/cc_native.py:139`

Important correction:

- the route does not currently run through CLI-style `CcExecutor`
- it runs through `CcNativeExecutor`

This matters because the implementation constraints are different:

- `CcExecutor` is a CLI/subprocess/hcom-oriented path
- `CcNativeExecutor` is an Anthropic-native Python ReAct loop with MCP client integration

### 3. Team mode exists, but the implementation is thin

`chatgptrest/kernel/cc_native.py:384`
`chatgptrest/kernel/cc_executor.py:398`

Current behavior in both native and CLI executors:

- `dispatch_team()` only injects `team` into `task.agents_json`
- then it falls back to the same single dispatch path as non-team execution

In other words:

- there is already a transport for `team`
- there is not yet a real team lifecycle model

What is missing today:

- no `team_run_id`
- no per-role lifecycle events
- no teammate-level scorecard
- no persistent "best team for task X in repo Y" memory
- no routing/policy feedback at team granularity

### 4. The learning primitives already exist

#### 4.1 Event envelope

`chatgptrest/kernel/event_bus.py`
`openmind/openmind/kernel/event_bus.py`

Both sides use `TraceEvent` as the event envelope. This is the correct shared contract.

#### 4.2 EvoMap signal sink

`chatgptrest/evomap/observer.py:47`

`EvoMapObserver` is real, backed by SQLite, and already supports:

- `record()`
- `record_event()`
- `emit()`
- query and aggregation

This is a usable persistence layer for execution feedback.

#### 4.3 Memory and routing feedback

`chatgptrest/kernel/cc_native.py:182`
`chatgptrest/kernel/cc_native.py:204`
`chatgptrest/kernel/cc_native.py:308`

`CcNativeExecutor` already does three useful things:

- emits `TraceEvent` through `_emit_event(...)`
- records EvoMap signals through `_record_signal(...)`
- stores episodic memory through `_remember_episodic(...)`
- reports execution outcomes to routing through `_report_routing_outcome(...)`

This is the right foundation. The missing part is not "memory exists" but "memory is not team-aware".

### 5. OpenMind V3 is still reference/governance, not runtime

`/vol1/1000/projects/openmind/AGENTS.md`
`/vol1/1000/projects/openmind/GEMINI.md`
`/vol1/1000/projects/openmind/openmind/kernel/event_bus.py`

OpenMind already defines the intended architecture:

- `TraceEvent` as the sole event envelope
- EvoMap as the evolution layer
- workflows/policies/memory as the higher-order control plane

But the repo itself still documents these constraints:

- `openmind/evomap/__init__.py` is placeholder-level for practical purposes
- `openmind/workflows/__init__.py` is placeholder-level for practical purposes
- current real writeback is still document/export driven through `exports/*.jsonl`

So the correct interpretation is:

- OpenMind V3 gives the conceptual contract
- ChatgptREST holds the production-adjacent runtime path

## Current Gaps

### Gap A. No real team contract

The current `team` payload is only passed through. There is no validated structure for:

- role definitions
- responsibilities
- handoff rules
- artifact requirements
- success criteria

### Gap B. No team-level trace model

Today the system can observe task-level and tool-level events, but not:

- team created
- role assigned
- role started
- role completed
- role blocked
- role output accepted/rejected

Without this, "team learning" is not possible in a precise way.

### Gap C. No scorecard / outcome memory at team granularity

The system can remember task outcomes, but not:

- which team composition worked
- which role prompts were effective
- which repo/task combination prefers which team topology
- which runner mode is stable or unstable

### Gap D. No policy feedback loop for future team selection

There is currently no component that answers:

- for repo `homeagent`, task `android_feature`, what team should be used?
- when should the system run single-agent vs team mode?
- which roles should be skipped because they are historically low value?

### Gap E. Runner stability is still mixed across Claude paths

This pass did not change runner behavior, but prior local evidence matters:

- `hcom + official claude` is not a stable automation baseline on this machine
- `hcom + claudeminmax` also has readiness issues

That makes the native/runtime path more important than trying to force everything through interactive wrappers.

## Recommended Development Direction

### Principle 1. Build on `CcNativeExecutor` first

Reason:

- it is already the API-backed path behind `/cc-dispatch-team`
- it already emits events and records signals
- its blast radius is smaller than making `CcExecutor` the primary learning seam

### Principle 2. Treat team learning as four layers

#### Layer 1. Team contract

Add a validated `TeamSpec` for:

- `team_id`
- `roles`
- `prompt_pack`
- `context_pack`
- `output_contract`
- `success_contract`

#### Layer 2. Team event model

Add structured events such as:

- `team.run.created`
- `team.role.assigned`
- `team.role.started`
- `team.role.completed`
- `team.role.failed`
- `team.output.accepted`
- `team.output.rejected`

Each event should carry:

- `trace_id`
- `team_run_id`
- `repo`
- `task_type`
- `role`
- `model`
- `prompt_hash`
- `context_pack_id`
- `latency`
- `artifact_paths`

#### Layer 3. Team scorecard

Store and aggregate:

- completion rate
- latency
- retry count
- test pass rate
- review acceptance rate
- rollback rate
- human override frequency

This should be queryable by:

- repo
- task type
- team template
- role

#### Layer 4. Policy/routing feedback

Use scorecard data to inform future dispatch:

- whether to use team mode
- which team template to use
- which runner mode to prefer
- whether to degrade to single-agent mode

### Principle 3. Keep OpenMind as reference/export sink, not the first runtime target

Practical implication:

- implementation lands in `ChatgptREST`
- summarized outcomes can be exported into `openmind/exports/*.jsonl`
- do not begin by adding a second live execution runtime inside `openmind/`

## Proposed Work Breakdown

### Issue A. Define `TeamSpec` and `TeamRunRecord`

Goal:

- turn `team` from an opaque dict into a validated contract

Files likely involved:

- `chatgptrest/kernel/cc_native.py`
- `chatgptrest/kernel/cc_executor.py`
- `chatgptrest/api/routes_advisor_v3.py`
- new types module under `chatgptrest/kernel/` or `chatgptrest/evomap/`

### Issue B. Add team lifecycle events and EvoMap persistence

Goal:

- record real team/role events instead of only task-level completion

Files likely involved:

- `chatgptrest/kernel/cc_native.py`
- `chatgptrest/evomap/observer.py`
- `chatgptrest/kernel/event_bus.py`

### Issue C. Build team score aggregation and selection memory

Goal:

- compute "which team is best for which task/repo"

Files likely involved:

- `chatgptrest/evomap/observer.py`
- `chatgptrest/kernel/model_router.py`
- new aggregation module

### Issue D. Add policy-aware team routing

Goal:

- use the stored scorecard to choose:
  - single-agent vs team
  - team template
  - runner mode

Files likely involved:

- `chatgptrest/api/routes_advisor_v3.py`
- `chatgptrest/executors/advisor_orchestrate.py`
- routing fabric modules

## What Should Not Be Done First

Do not start with:

- a generic "multi-agent framework" rewrite
- moving execution runtime into `openmind/`
- hcom-first automation on this machine
- automatic prompt mutation without auditability

Those directions are higher risk and less grounded in the code that already exists.

## Operational Notes

- This branch/worktree is for design and handoff only in the current pass.
- No runtime code change is required to hand development to another agent.
- Because `CcNativeExecutor` is already in the API path, changes here should be treated as high impact and rolled out incrementally.

## Recommended Next Action

Open a development issue in `ChatgptREST` with this scope:

- confirm `CcNativeExecutor` as the primary team-learning seam
- implement `TeamSpec`
- implement team lifecycle events
- implement team scorecard persistence
- implement routing/policy feedback
- keep OpenMind integration export-driven until the runtime closes the loop

## Evidence

Primary code references used in this pass:

- `chatgptrest/api/routes_advisor_v3.py:188`
- `chatgptrest/api/routes_advisor_v3.py:1180`
- `chatgptrest/kernel/cc_native.py:139`
- `chatgptrest/kernel/cc_native.py:384`
- `chatgptrest/kernel/cc_executor.py:123`
- `chatgptrest/kernel/cc_executor.py:398`
- `chatgptrest/evomap/observer.py:47`
- `openmind/AGENTS.md:25`
- `openmind/AGENTS.md:29`
- `openmind/GEMINI.md:26`
- `openmind/GEMINI.md:27`
