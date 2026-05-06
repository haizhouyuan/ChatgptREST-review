# Public MCP Conversation Tools Validation v1

Date: 2026-05-01

## Problem

The code and skill documentation already defined the URL-to-conversation recovery path:

- `automation_conversation_fetch`
- `automation_conversation_get`
- `automation_conversation_find`

However, the live `chatgptrest-mcp.service` had been running since before those tools were loaded. A fresh `tools/list` against `http://127.0.0.1:18712/mcp` advertised only the older eight-tool automation surface. This meant Claude/Codex agents could still recover a conversation through the low-level `automation_job_create(kind="chatgpt_web.conversation_export")` fallback, but they could not discover the dedicated production tools directly.

## Root Cause

The production validation gate checked only a smaller subset of public MCP tools. It did not fail when the live MCP schema was stale and omitted the conversation recovery tools.

## Change

Updated `chatgptrest/eval/public_agent_mcp_validation.py` so `REQUIRED_PUBLIC_AGENT_MCP_TOOLS` includes the full canonical public automation surface:

- `automation_ask`
- `automation_result`
- `automation_job_create`
- `automation_job_status`
- `automation_job_answer`
- `automation_job_cancel`
- `automation_job_events`
- `automation_conversation_fetch`
- `automation_conversation_get`
- `automation_conversation_find`
- `automation_gemini_generate_image_submit`

Updated tests so validation fails if the conversation tools are missing.

Updated `ops/registries/surface_policy.yaml` and `docs/contract_v1.md` so bootstrap packets and contract docs match the production tool surface.

The validation protocol expectation now follows the current streamable-HTTP MCP client default, `2025-06-18`, instead of the older `2025-03-26` probe value.

The validation client now uses the current keyword-only MCP HTTP client constructor and `call_tool` API, parses structured MCP tool errors, and treats a duplicate low-level ask response with a reusable `existing_job_id` as a duplicate handoff instead of a validation failure. This makes the probe safe to rerun without forcing new browser submissions.

Live validation after restarting only `chatgptrest-mcp.service` passed all five checks against `http://127.0.0.1:18712/mcp`. The advertised live tool set included all three conversation recovery tools.

## Operational Requirement

After deploying this change, restart `chatgptrest-mcp.service` in a maintenance-safe window and run:

```bash
PYTHONPATH=. ./.venv/bin/python ops/run_public_agent_mcp_validation.py
```

The validation must fail closed if the running MCP schema does not expose the dedicated conversation recovery tools.
