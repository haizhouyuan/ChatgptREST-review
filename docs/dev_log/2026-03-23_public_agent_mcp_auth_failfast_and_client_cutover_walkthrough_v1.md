# 2026-03-23 Public Agent MCP Auth Fail-Fast And Client Cutover Walkthrough v1

## What Changed

- tightened public MCP startup so missing auth is rejected immediately
- made the launcher/service env loading more explicit
- aligned client-facing guidance to one supported coding-agent surface: `http://127.0.0.1:18712/mcp`

## Why This Is Narrow

The auth chain behind `advisor_agent_turn/status/cancel` is critical, so the implementation avoided changing request semantics.

The change only:

- reports/validates auth presence
- exits early on missing auth
- reduces configuration ambiguity
- tightens operator and client guidance

It does not change:

- `/v3/agent/*` auth semantics
- public MCP request forwarding logic
- allowlist / trace-header gates

## Validation Plan

1. targeted unit tests for public MCP auth helpers and entrypoint fail-fast
2. targeted py_compile on touched Python files
3. rerun the public MCP validation pack

## Expected Operational Outcome

- if a caller reaches the systemd-managed `18712/mcp`, auth should already be present
- if someone starts a stray public MCP process without env, it should fail immediately instead of surfacing a later 401 from `/v3/agent/*`
- coding agents should stop drifting between MCP and direct REST usage
