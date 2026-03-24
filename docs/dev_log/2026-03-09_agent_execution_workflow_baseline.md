# 2026-03-09 Agent Execution Workflow Baseline

## Why this was added

Recent work exposed a repeated pattern:

- the controller model was doing too much serial reading and evidence chasing
- some tasks were long enough that they should have been detached
- multiple auxiliary execution lanes existed, but their maturity levels were mixed

The mistake would be to treat all of them as equally trustworthy.

Instead, the workflow is now documented with an explicit maturity model.

## New baseline

Added:

- `docs/ops/agent_execution_workflow_20260309.md`

Key decisions:

- Codex main model remains the controller
- Codex subagents are the default parallel sidecar lane
- ClaudeCode runner is an async worker lane, not a controller
- Gemini CLI and Gemini CLI MCP are useful but still under iterative evaluation
- hcom agent teams are conditional, not default
- long-lived role or persona agents are no longer the default operating pattern
- long-answer async lanes must fail closed unless the result reaches `completion_quality=final`
- local Gemini lanes and ChatgptREST queued web transport are related but distinct tools, and should be documented separately

## Operational impact

This changes future execution behavior in a practical way:

- avoid overusing long-lived or heavy multi-agent setups
- avoid maintaining standing role agents when an on-demand lane is enough
- prefer subagents for short local parallel work
- prefer ClaudeCode runner for long detached tasks
- use Gemini lanes for cheap breadth, not final authority
- treat `completion_quality=final` as the acceptance gate for long-form async outputs
- record failures and tighten the lane through repeated use

## Decision

The repository now has an explicit execution workflow baseline instead of relying on ad-hoc coordination choices.
