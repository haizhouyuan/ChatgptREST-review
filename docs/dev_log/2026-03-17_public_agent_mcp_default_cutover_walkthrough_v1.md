# Public Agent MCP Default Cutover Walkthrough v1

Date: 2026-03-17

## Why

The repo already had a dedicated small-surface MCP implementation in `chatgptrest/mcp/agent_mcp.py`, but the default start path and systemd unit still launched the legacy broad MCP surface. As a result, Codex / Claude Code / Antigravity still enumerated dozens of low-level tools by default.

## What Changed

1. Switched the default public MCP entrypoint to the agent surface.
   - `chatgptrest_mcp_server.py` now imports `chatgptrest.mcp.agent_mcp`.
   - added explicit alias `chatgptrest_agent_mcp_server.py`.
2. Preserved the old broad surface behind an explicit admin entrypoint.
   - added `chatgptrest_admin_mcp_server.py`.
3. Switched the default start + systemd path to the public agent MCP.
   - updated `ops/start_mcp.sh`
   - updated `ops/systemd/chatgptrest-mcp.service`
   - updated `ops/systemd/enable_maint_self_heal.sh`
4. Added a separate admin start + systemd path for the broad surface.
   - added `ops/start_admin_mcp.sh`
   - added `ops/systemd/chatgptrest-admin-mcp.service`
5. Updated the native Claude executor’s default `chatgptrest-mcp` stdio rewrite.
   - `chatgptrest/kernel/cc_native.py` now launches `chatgptrest_agent_mcp_server.py`.
6. Updated the operator docs.
   - `README.md`
   - `docs/runbook.md`
   - `docs/client_interactions_v3.md`
   - `docs/2026-03-17_public_agent_mcp_default_cutover_v1.md`

## Verification

Ran:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_agent_mcp.py tests/test_mcp_server_entrypoints.py
```

Expected user-facing result:

- default `chatgptrest-mcp` now maps to the 3-tool public agent surface
- legacy broad MCP remains available, but only through the explicit admin entrypoint/service
