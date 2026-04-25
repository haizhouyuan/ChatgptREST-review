# Paperclip MCP Usage

The Paperclip MCP server is a thin wrapper over the REST API.

Required environment variables:

- `PAPERCLIP_API_URL`
- `PAPERCLIP_API_KEY`
- `PAPERCLIP_COMPANY_ID`
- `PAPERCLIP_AGENT_ID` when an agent identity is needed
- `PAPERCLIP_RUN_ID` when a mutating tool call should be tied to a heartbeat run

Security rule:

- Keep real API keys only in ignored local env files.
- Keep templates and review packets placeholder-only.
- Use local loopback URLs for this demo.
- Apply `configs/mcp-tool-policy.yaml` as the demo control contract.
- Restrict mutation to checkout, comment, and status update on `LAB-SMOKE-001`.
- Deny agent creation, adapter updates, skill imports, secret writes, company deletion, approval decisions, arbitrary API calls, and external-account actions.
