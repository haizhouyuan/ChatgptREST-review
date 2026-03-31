# 2026-03-23 Other Codex Public MCP Client Config Cutover v1

## Summary

Other Codex clients were still configured to spawn a local `stdio` ChatgptREST MCP process instead of using the authenticated systemd-managed public MCP at `http://127.0.0.1:18712/mcp`. That mismatch explains why separate Codex sessions could still see `401 Unauthorized` while the public MCP validation pack stayed green.

## What Was Fixed

- Switched these Codex configs from local `stdio` launch to HTTP public MCP:
  - `/home/yuanhaizhou/.codex/config.toml`
  - `/vol1/1000/home-yuanhaizhou/.codex-shared/config.toml`
  - `/vol1/1000/home-yuanhaizhou/.home-codex-official/.codex/config.toml`
  - `/vol1/1000/home-yuanhaizhou/.codex2/config.toml`
- Added a repo-owned verifier:
  - `ops/check_public_mcp_client_configs.py`
- Added regression tests:
  - `tests/test_check_public_mcp_client_configs.py`

## Expected State

All known Codex client configs should now contain:

```toml
[mcp_servers.chatgptrest]
enabled = true
url = "http://127.0.0.1:18712/mcp"
startup_timeout_sec = 30.0
tool_timeout_sec = 7200.0
```

and should no longer contain:

- `chatgptrest_agent_mcp_server.py`
- `--transport stdio`

## Verification

- `systemctl --user status chatgptrest-mcp.service`
- `PYTHONPATH=. ./.venv/bin/python ops/run_public_agent_mcp_validation.py`
- `PYTHONPATH=. ./.venv/bin/python ops/check_public_mcp_client_configs.py`
- `./.venv/bin/pytest -q tests/test_check_public_mcp_client_configs.py`

## Remaining Boundary

This cutover fixes known Codex client configuration drift. It does not change any built-in connector that may be bundled by an external host product; those still need to be pointed at `http://127.0.0.1:18712/mcp` by that host.
