# MCP Smoke

## Result

The Paperclip MCP server was checked with the official MCP client over stdio.

- Server: `paperclip-labebe-demo`
- API URL: `http://127.0.0.1:3100`
- Company ID: `1cb6d439-2bdf-4f63-ad9a-b5326d5546df`
- Tool count: 34
- Required tools present:
  - `paperclipMe`
  - `paperclipListAgents`
  - `paperclipListIssues`
  - `paperclipCreateIssue`
  - `paperclipUpdateIssue`
  - `paperclipAddComment`

Machine-readable evidence:

```text
outputs/mcp-smoke-tools-list.json
pro_requests/20260425_paperclip_labebe_demo_config_review/evidence/mcp_tools_list_redacted.json
pro_requests/20260425_paperclip_labebe_demo_config_review/evidence/mcp_policy_check.json
```

## Demo Tool Policy

The demo uses a default-deny policy in `configs/mcp-tool-policy.yaml`.

- Read-only tools are allowed for health, actor, company/project/agent/skill/issue/comment/document/approval inspection.
- Mutations are allowed only for the target smoke issue `LAB-SMOKE-001`: checkout, comment, and status update.
- Agent creation, adapter updates, skill imports, secret changes, company deletion, approval decisions, arbitrary API requests, and external actions are denied for the demo lane.

## Secret Handling

The smoke command reads the real local API key from the ignored instance env file. The saved evidence records only whether a key is present; it does not record the key value.
