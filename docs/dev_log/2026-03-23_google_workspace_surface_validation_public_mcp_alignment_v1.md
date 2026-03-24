# 2026-03-23 Google Workspace Surface Validation Public MCP Alignment v1

## Problem

`google_workspace_surface_validation` still assumed the CLI workspace path used direct REST.

After the coding-agent CLI default cutover, `chatgptrest agent turn` now uses the public MCP surface by default. The validation helper and its test double were still patching the old REST call path, so the validation pack drifted even though the live product behavior was already correct.

## Fix

Aligned the validation helper with the current CLI contract:

- `_cli_workspace_request_check()` now patches `chatgptrest.cli._call_public_mcp_tool`
- the helper accepts the current MCP helper signature:
  - `mcp_url`
  - `tool_name`
  - `arguments`
  - `timeout_seconds`
- the test path can inject a helper while still preserving the validation helper's own captured call details

## Validation

- `./.venv/bin/pytest -q tests/test_google_workspace_surface_validation.py`
- `python3 -m py_compile chatgptrest/eval/google_workspace_surface_validation.py tests/test_google_workspace_surface_validation.py`
- `PYTHONPATH=. ./.venv/bin/python ops/run_google_workspace_surface_validation.py`

## Outcome

`google_workspace_surface_validation` is green again under the public-MCP-default CLI behavior.

Accepted live evidence:

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/google_workspace_surface_validation_20260323/report_v1.json)
- [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/google_workspace_surface_validation_20260323/report_v1.md)
