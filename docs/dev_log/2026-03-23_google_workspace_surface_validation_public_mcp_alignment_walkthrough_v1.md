# 2026-03-23 Google Workspace Surface Validation Public MCP Alignment Walkthrough v1

## What Changed

- updated `chatgptrest/eval/google_workspace_surface_validation.py`
- updated `tests/test_google_workspace_surface_validation.py`

## Why

The coding-agent CLI now defaults to the public MCP surface. The Workspace validation helper was still stubbing the old direct REST helper, so the validation pack no longer matched the live CLI path.

## How

1. Switched the validation helper to patch `chatgptrest.cli._call_public_mcp_tool`
2. Matched the current MCP helper signature: `mcp_url`, `tool_name`, `arguments`, `timeout_seconds`
3. Preserved internal call capture even when a test injects its own fake helper
4. Re-ran the Workspace validation unit test and live runner
5. Re-ran the aggregate blueprint scoped-launch gate to refresh accepted evidence

## Outcome

- Workspace validation is green again under the current public-MCP-default CLI path
- The aggregate blueprint scoped-launch gate remains green
