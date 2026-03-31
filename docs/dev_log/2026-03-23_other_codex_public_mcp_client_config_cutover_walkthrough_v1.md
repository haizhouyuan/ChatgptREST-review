# 2026-03-23 Other Codex Public MCP Client Config Cutover Walkthrough v1

## Why

The public MCP server on `127.0.0.1:18712` was healthy, but separate Codex sessions could still receive `401 Unauthorized`. The root cause was client-side drift: several Codex configs still launched a local unauthenticated `stdio` MCP process instead of talking to the authenticated systemd-managed public MCP.

## Steps

1. Confirmed `chatgptrest-mcp.service` was healthy and serving `/mcp` on port `18712`.
2. Inspected known Codex client configs and found multiple `stdio` launch blocks pointing at `chatgptrest_agent_mcp_server.py`.
3. Replaced those client blocks with the public MCP URL.
4. Added a repo-side verifier so future drift is detectable.
5. Re-ran public MCP validation and the new client-config verifier.

## Result

Known Codex client configs are now aligned to the same authenticated public MCP surface. Future regressions can be caught by `ops/check_public_mcp_client_configs.py`.
