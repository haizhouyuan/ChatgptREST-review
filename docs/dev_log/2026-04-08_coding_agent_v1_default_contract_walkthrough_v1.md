# Coding-Agent-V1 Default Contract Walkthrough V1

Date: 2026-04-08

## Why

The previous public MCP story made coding agents inherit the broad advisor contract by default.

That caused two problems:

1. the default path exposed too many knobs
2. coding-agent defaults drifted away from the intended product boundary

The goal of this work package was to freeze a narrower default lane without creating a second MCP server.

## Implementation shape

One transport remains:

- `http://127.0.0.1:18712/mcp`

Two public lanes now coexist on that transport:

- `coding-agent-v1`
- `advisor-agent`

The implementation choice was:

- keep existing `advisor_agent_*`
- add `coding_agent_*` wrappers on the same surface
- make wrapper + CLI default to `coding-agent-v1`
- force explicit opt-in for broad advisor semantics

## Key implementation points

### Public MCP projection

`chatgptrest/mcp/agent_mcp.py` now exposes:

- coding-agent turn/wait/answer/status/cancel wrappers
- narrow request validation for `execution_profile`
- narrow response projection including:
  - `lane`
  - `answer_state`
  - `answer_ready`
  - `recommended_next_action`
  - canonical tool names

### Wrapper default change

`skills-src/chatgptrest-call/scripts/chatgptrest_call.py` now:

- defaults `--agent-surface` to `coding-agent-v1`
- derives tool names from the selected surface
- treats broad advisor objects as invalid unless `--agent-surface advisor-agent`
- uses the selected surface in wait/status/answer recovery hints

### CLI default change

`chatgptrest/cli.py` now:

- defaults `agent turn/status/cancel` to `coding-agent-v1`
- adds `--agent-surface`
- adds `--project-id`
- rejects broad advisor objects in the default coding-agent lane

## Test outcome

Targeted unit/integration-style acceptance passed on:

- public MCP narrow projection
- wrapper default routing
- wrapper failure behavior
- CLI default routing
- explicit advisor override

## Result

The coding-agent default story is now consistent across:

- public MCP
- repo wrapper
- CLI
- operational docs

That gives the next work packages a stable base:

- OpenClaw entry-policy completion
- authority governance hardening
- unified release gate pack
