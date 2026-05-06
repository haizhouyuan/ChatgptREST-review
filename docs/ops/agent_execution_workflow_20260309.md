# Agent Execution Workflow

Date: 2026-03-09

## Purpose

Define the default execution workflow for this repository when combining:

- Codex main model
- Codex subagents
- ClaudeCode runner
- Gemini CLI
- Gemini CLI MCP
- ChatgptREST MCP / queued web paths

This document is intentionally operational, not aspirational.

The key assumption is:

- not all execution lanes are equally mature
- some lanes are already dependable
- some lanes are useful but still need iteration during real use

The goal is not to pretend every runner is production-grade.
The goal is to use each lane where it is strong, keep weak lanes inside safe boundaries, and tighten the workflow through repeated use.

The short version is:

- controller-first
- fewer persistent agents
- more on-demand lanes

## Core rule

One controller, many optional lanes.

- The controller is the Codex main model in the active repo.
- Every other lane is subordinate.
- No auxiliary lane is allowed to become the source of truth by default.
- Long-lived role or persona agents are deprecated for normal work in this repo.

That means:

- planning, integration, final decisions, commits, and acceptance remain with the controller
- auxiliary lanes are used to remove time sinks, not to replace architectural judgment
- default to on-demand lanes with explicit scope, not standing agent personalities

## Lane ladder

Escalate in this order unless a task clearly justifies skipping a step:

1. Codex main only
2. Codex main + Codex subagents
3. Codex main + ClaudeCode runner
4. Codex main + Gemini CLI or Gemini CLI MCP
5. Codex main + hcom teams

The existence of a heavier lane does not justify using it by default.

## Current maturity model

### Tier A: stable enough for default use

- Codex main model
  - use for implementation, integration, commit discipline, and final judgment
- Codex subagents
  - use for parallel code reading, GitNexus triage, scoped test diagnosis, evidence collection, and bounded sidecar analysis

### Tier B: useful but still iterative

- ClaudeCode runner
  - found at:
    - `/vol1/1000/home-yuanhaizhou/.codex2/skills/claudecode-agent-runner/`
  - use for long-running async review / diagnosis / patch proposal tasks
  - do not treat it as authoritative without verification
  - it is a worker lane, not a controller lane

- Gemini CLI
  - use as a fast structure / draft / judge lane
  - useful for cheap broad passes, summaries, cross-checks, and fast reframing
  - do not let it own final acceptance on code-integrity tasks

- Gemini CLI MCP
  - treat as an integration seam under evaluation
  - useful when it reduces glue code and lets the controller route work quickly
  - still requires repeated real-task validation before it becomes default

### Related transport distinction

These are easy to confuse, but they are not the same thing:

| Lane | Primary use | Control surface | Default trust level |
|---|---|---|---|
| `Gemini CLI` | fast local auxiliary cognition | local CLI | assist only |
| `Gemini CLI MCP` | local MCP-shaped Gemini access | MCP | assist only |
| `ChatgptREST MCP` | queued web/model execution with artifacts | ChatgptREST server + MCP adapter | execution transport, still controller-owned |

Practical rule:

- use `Gemini CLI` or `Gemini CLI MCP` when you want a fast second read
- use `ChatgptREST MCP` when you need queued execution, stable artifacts, idempotency, or web-model access
- do not blur “local helper lane” and “queued remote execution transport”

### Tier C: experimental / conditional

- hcom agent teams
  - only use when a task genuinely decomposes into multiple independent lanes
  - do not use by default just because multi-agent orchestration exists
  - current maturity is not high enough to make it the default coordination plane on this machine

## Default execution policy

### 1. Single-lane first

Default to the controller alone if the task is:

- a focused bug fix
- a single-file or small multi-file patch
- a tight regression loop
- a contract/doc update tightly coupled to code changes

Do not spawn extra lanes just to feel “agentic”.

### 2. Add subagents before adding external runners

If the controller is blocked by reading or diagnosis overhead, add a Codex subagent first.

Best uses:

- read-only code reconnaissance
- GitNexus context and impact summaries
- failing test triage
- public review branch completeness checks
- evidence extraction from artifacts/logs

Prefer subagents over heavier runners when the task is short, local, and tightly coupled to the current thread.

### 3. Use ClaudeCode runner for long async work

Use ClaudeCode runner when the task:

- may run for a long time
- benefits from detached artifacts and logs
- does not need to block controller progress

Examples:

- long code review
- long-form patch proposal
- large output digestion
- independent refactor sketching

Operational constraints:

- always keep the controller as the integrator
- require artifacts before accepting results
- require local verification before acting on results

### 4. Use Gemini CLI / Gemini CLI MCP for fast auxiliary cognition

Use Gemini CLI lanes for:

- fast structured drafts
- quick reframing
- alternative decomposition
- cheap judge passes
- breadth-first exploration

Do not use them as the default final authority for:

- merge acceptance
- code-integrity signoff
- infra safety decisions

### 5. Use hcom teams only when the task really needs multiple independent lanes

Examples where hcom may be justified:

- debate-style cross-model review
- parallel module audits with disjoint scopes
- overnight experimentation where the controller only checks back later

Examples where hcom is not justified:

- ordinary bug fixing
- one PR hardening loop
- routine repo maintenance

## Execution recipes

### Recipe A: normal development

- controller does the implementation
- one subagent may scout code or tests
- no ClaudeCode runner
- no hcom

### Recipe B: heavy review / evidence task

- controller defines the scope
- ClaudeCode runner executes the long async review
- one subagent can collect local repo or artifact context in parallel
- controller validates and integrates results

### Recipe C: cheap cross-check

- controller implements or prepares a bundle
- Gemini CLI or Gemini CLI MCP produces a fast secondary read
- controller decides whether a deeper external review is warranted

### Recipe D: multi-lane experiment

- controller decomposes the task explicitly
- lanes are assigned bounded, non-overlapping work
- hcom is optional, not mandatory
- controller remains the only merge authority

## Fail-closed rules

- No auxiliary lane result is accepted without local verification when code or infra is affected.
- “Completed” is not equal to “correct”.
- For long-answer or review tasks, artifacts and evidence are required.
- For ClaudeCode runner and hcom-produced long tasks, `completion_quality=final` is the acceptance gate. Anything else is partial, in-progress, or review-only.
- For queued web lanes, an answer file alone is not enough when the task contract expects a full report. Keep the task open until the terminal artifact matches the requested output shape.
- If a lane is flaky, demote its responsibility instead of forcing trust.

## Iteration policy

This workflow is expected to evolve through use.

Every time an auxiliary lane is used on a real task, capture:

- task type
- lane used
- what it did well
- where it failed
- whether it saved time overall
- what guardrail or prompt change is needed next time

The important point is:

- ClaudeCode runner is not assumed mature
- Gemini CLI / Gemini CLI MCP are not assumed mature
- hcom is not assumed mature

They become useful only by repeated bounded use plus correction.

## Required retrospectives

When a non-controller lane causes churn, delay, or confusion, log a short retrospective under `docs/dev_log/` with:

- trigger
- lane used
- failure mode
- corrective change
- whether the lane should be promoted, kept experimental, or demoted

## Current decision

Use this repository with the following default stance:

- controller-first
- subagents by default for parallel local sidecar work
- ClaudeCode runner as async worker lane
- Gemini CLI / Gemini CLI MCP as fast auxiliary lanes under evaluation
- hcom only when clearly justified

This is the operating baseline until repeated real use proves a better pattern.
