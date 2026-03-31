## Coding Agent MCP Surface Policy v3

Scope:

- Codex
- Claude Code
- Antigravity
- repo CLI / wrappers used by those coding agents

This revision upgrades the policy from "public MCP is the default northbound surface" to
"public MCP is the default execution path for coding-agent northbound entrypoints".

### Rules

1. Default to the public advisor-agent MCP surface.
   - Canonical URL: `http://127.0.0.1:18712/mcp`
   - Canonical tools:
     - `advisor_agent_turn`
     - `advisor_agent_status`
     - `advisor_agent_cancel`

2. `chatgptrestctl agent turn|status|cancel` now defaults to public MCP.
   - CLI uses the public advisor-agent MCP by default.
   - Direct `/v3/agent/*` REST is no longer the default execution path for repo CLI.

3. Direct `/v3/agent/*` REST is maintenance/debug only.
   - Explicit override:
     - `--agent-direct-rest`
   - Valid uses:
     - internal maintenance
     - validation/debugging
     - controlled runtime experiments
   - Invalid use:
     - normal coding-agent northbound integration

4. Coding agents should not use ChatgptREST REST endpoints as their default integration surface.
   - `/v3/agent/*` remains valid for internal runtime, OpenClaw/plugin integration, maintenance, and validation.
   - It is not the preferred surface for Codex / Claude Code / Antigravity.

5. Repo wrappers must use public MCP in agent mode.
   - Wrapper:
     - `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
   - Agent mode routes through public MCP.
   - `--no-agent` legacy mode may still use lower-level REST/provider flows for controlled maintenance scenarios.

6. Do not teach coding agents legacy bare MCP tool names.
   - Forbidden examples:
     - `chatgptrest_ask`
     - `chatgptrest_consult`
     - `chatgptrest_job_wait`
     - `chatgptrest_result`

7. Treat broad/admin ChatgptREST MCP and direct REST as internal surfaces.
   - Useful for repair, maintenance, and debugging.
   - Not the default northbound contract for coding agents.

### Operational Consequence

If a coding agent needs ChatgptREST, the prompt or config should say:

- use the public advisor-agent MCP
- use the repo skill wrapper in agent mode
- use `chatgptrestctl agent ...` only in its default public-MCP mode

It should not say:

- call `/v3/agent/turn` directly
- call `/v1/jobs`
- use legacy bare MCP tool names

### Why

This keeps the coding-agent contract aligned with the higher-level control plane:

- `task_intake`
- `contract_patch`
- clarify/resubmit
- delivery/session continuity
- northbound observability

instead of forcing every client to manage low-level REST details.
