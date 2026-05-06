# Public Lane Lifecycle Decision v1

Date: 2026-04-08
Repo: ChatgptREST
Scope: public MCP northbound lifecycle policy
Status: accepted

## Decision

ChatgptREST public MCP now has two public contracts with different purposes:

1. `coding_agent_*`
   - Mature coding-agent default lane
   - Default for Codex, Claude Code, and Antigravity
   - Narrow contract, result-first, coding-agent-oriented

2. `advisor_agent_*`
   - Broad public advisor / compatibility lane
   - Retained for explicit advisor-level controls and compatibility
   - Not deprecated by this decision
   - Not the mature coding-agent default lane

## Why

The platform now has a real `coding-agent-v1` contract with:

- narrow request objects
- explicit canonical-answer tools
- completion-contract-aware delivery
- clearer user intent for coding agents

This means the previous "one broad advisor surface for everything" default is no longer the right default for mature coding agents.

At the same time, broad advisor capabilities still matter for:

- `task_intake`
- `contract_patch`
- `workspace_request`
- compatibility with existing public-advisor consumers
- user-facing end-to-end advisor flows

So the correct lifecycle policy is coexistence with explicit role boundaries, not immediate removal.

## Lifecycle Policy

### coding_agent_*

Use as the default public MCP lane for:

- Codex
- Claude Code
- Antigravity
- repo wrappers and skills that target mature coding-agent behavior

This lane should remain the only default mature coding-agent contract advertised in:

- repo bootstrap packets
- surface registry
- runbook
- AGENTS policy
- coding-agent wrapper docs

### advisor_agent_*

Keep available as the broad public advisor / compatibility lane for:

- explicit advisor-mode turns
- `task_intake`, `contract_patch`, `workspace_request`
- compatibility callers that still depend on the broader public contract
- user-facing OpenMind/OpenClaw-facing advisor paths

This lane is not deprecated by this decision, but it should no longer be presented as the default mature coding-agent contract.

## Required Documentation Consequences

The following repository guidance must stay aligned:

- `AGENTS.md`
- `docs/contract_v1.md`
- `docs/runbook.md`
- `ops/registries/surface_policy.yaml`
- `skills-src/chatgptrest-call/SKILL.md`

All of them must say the same thing:

- `coding_agent_*` is the mature default lane for coding agents
- `advisor_agent_*` remains available for broad advisor / compatibility scenarios

## Non-Goals

This decision does not:

- remove `advisor_agent_*`
- rename MCP tools
- force all existing advisor consumers to migrate immediately
- merge the two contracts back into one broad default lane

## Follow-On Work

This decision unlocks the next V3 items:

- live Deep Research finality gate
- explicit compatibility note for old advisor callers
- release-gate checks that validate the mature default lane separately from the broad advisor lane
