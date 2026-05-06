# Public Agent MCP Default Cutover v1

Date: 2026-03-17

## Outcome

ChatgptREST now supports a split MCP surface:

- Public/default MCP: agent-level only
  - endpoint: `http://127.0.0.1:18712/mcp`
  - tools:
    - `advisor_agent_turn`
    - `advisor_agent_status`
    - `advisor_agent_cancel`
- Admin/internal MCP: legacy broad surface
  - endpoint: `http://127.0.0.1:18715/mcp`
  - purpose: ops, debugging, repair, low-level orchestration

## Default Entry Points

- Public/default entrypoint:
  - `chatgptrest_mcp_server.py`
  - explicit alias: `chatgptrest_agent_mcp_server.py`
- Admin/internal entrypoint:
  - `chatgptrest_admin_mcp_server.py`

## Start Scripts

- Public/default MCP:
  - `ops/start_mcp.sh`
- Admin/internal MCP:
  - `ops/start_admin_mcp.sh`

## systemd Units

- Public/default MCP:
  - `ops/systemd/chatgptrest-mcp.service`
- Admin/internal MCP:
  - `ops/systemd/chatgptrest-admin-mcp.service`

## Client Guidance

- Codex / Claude Code / Antigravity should connect to the public/default MCP at `:18712`.
- Internal operator/debug clients that still need the broad tool surface should use the admin MCP at `:18715`.
- `CcNativeExecutor` now rewrites `chatgptrest-mcp` HTTP configs to the public stdio agent entrypoint, not the legacy broad server.
