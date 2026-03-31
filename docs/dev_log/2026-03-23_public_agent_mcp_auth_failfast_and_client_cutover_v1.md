# 2026-03-23 Public Agent MCP Auth Fail-Fast And Client Cutover v1

## Summary

This change hardens the ChatgptREST public agent MCP as the single supported coding-agent entry surface.

Three things were tightened together:

1. Public MCP startup now fails fast when neither `OPENMIND_API_KEY` nor `CHATGPTREST_API_TOKEN` is present.
2. The helper launcher and systemd template now load the expected env sources more explicitly.
3. Active client-facing docs were aligned so coding agents are steered to `http://127.0.0.1:18712/mcp`, not direct ChatgptREST REST calls.

## Why

Recent 401 incidents were more consistent with callers missing the authenticated systemd-managed public MCP instance than with the public MCP surface itself being broken.

The intended runtime shape is:

- systemd-managed `chatgptrest-mcp.service`
- public MCP surface at `http://127.0.0.1:18712/mcp`
- auth sourced from `~/.config/chatgptrest/chatgptrest.env` and, in the service template, `/vol1/maint/MAIN/secrets/credentials.env`

If a client launches an ad-hoc MCP process without those env sources, the previous behavior allowed a later 401 from `/v3/agent/*`. The new behavior fails at MCP startup instead.

## Code Changes

### 1. Public MCP fail-fast

- `chatgptrest/mcp/agent_mcp.py`
  - added `public_agent_mcp_auth_state()`
  - added `ensure_public_agent_mcp_auth_configured()`
- `chatgptrest_agent_mcp_server.py`
  - public entrypoint now exits immediately if auth env is missing
- `chatgptrest_mcp_server.py`
  - default public MCP entrypoint now uses the same fail-fast behavior

### 2. Launcher and service env loading

- `ops/start_mcp.sh`
  - now loads:
    - `${HOME}/.config/chatgptrest/chatgptrest.env`
    - `/vol1/maint/MAIN/secrets/credentials.env`
- `ops/systemd/chatgptrest-mcp.service`
  - template now includes `EnvironmentFile=-/vol1/maint/MAIN/secrets/credentials.env`

### 3. Client cutover policy

The active docs now consistently state:

- coding agents should connect to `http://127.0.0.1:18712/mcp`
- direct REST `/v3/agent/*` is backend ingress, not the default coding-agent entry
- admin/broad MCP remains ops/debug only

Updated files:

- `README.md`
- `docs/client_interactions_v3.md`
- `docs/contract_v1.md`
- `docs/runbook.md`
- `docs/client_projects_registry.md`
- `skills-src/chatgptrest-call/SKILL.md`
- `AGENTS.md`

## Tests

Targeted validation for this change covers:

- public auth-source reporting
- fail-fast startup behavior
- public MCP entrypoint boot path
- public agent MCP live validation pack

## Acceptance

The change is acceptable when all of the following hold:

- the public MCP entrypoint fails before serving when both auth env vars are absent
- the systemd-managed public MCP still boots and passes the public MCP validation pack
- docs no longer steer coding agents to direct REST as their default ChatgptREST integration path
