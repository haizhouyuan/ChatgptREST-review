## Coding Agent MCP Surface Policy v4

Scope:

- Codex
- Claude Code
- Antigravity
- repo CLI / wrappers used by those coding agents

This revision keeps public advisor-agent MCP as the default northbound surface and adds a direct-REST guard for coding-agent client identities.

### Rules

1. Public advisor-agent MCP remains the canonical northbound surface.
   - URL: `http://127.0.0.1:18712/mcp`
   - Tools:
     - `advisor_agent_turn`
     - `advisor_agent_status`
     - `advisor_agent_cancel`

2. `chatgptrestctl agent turn|status|cancel` defaults to public MCP.

3. Direct `/v3/agent/*` REST is blocked for normal coding-agent client identities.
   - Blocked examples:
     - `chatgptrestctl`
     - `codex`
     - `codex2`
     - `claude`
     - `claude-code`
     - `antigravity`
   - Error:
     - `coding_agent_direct_rest_blocked`

4. Direct `/v3/agent/*` REST remains available only for explicit maintenance/internal clients.
   - Allowed examples:
     - `chatgptrest-mcp`
     - `openclaw-advisor`
     - `chatgptrestctl-maint`
   - Repo CLI reaches this only when an operator explicitly sets:
     - `--agent-direct-rest`

5. Repo wrapper remains MCP-first in agent mode.
   - `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

6. Broad/admin MCP and low-level REST remain internal surfaces, not coding-agent northbound defaults.

### Operational Consequence

For normal coding-agent usage:

- use public advisor-agent MCP
- use repo wrapper in agent mode
- do not call `/v3/agent/turn` directly

For maintenance/debugging:

- explicit operator override is required
- repo CLI uses maintenance client identity

### Why

This closes the remaining governance gap between:

- documented northbound policy
- client configs/wrappers
- live server-side route enforcement

so coding agents do not silently drift back to direct REST.
