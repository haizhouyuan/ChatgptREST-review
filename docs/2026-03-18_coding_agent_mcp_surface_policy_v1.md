## Coding Agent MCP Surface Policy

Scope:
- Codex
- Claude Code
- Antigravity

This policy exists because humans do not use ChatgptREST MCP tools directly. The MCP surface is only for coding agents, and those agents must not be taught unstable legacy tool names.

### Rules

1. Default to the public advisor-agent surface.
   - Coding agents should interact with ChatgptREST as an agent.
   - Prefer the runtime-provided public agent tools or the public REST facade.
   - Do not design prompts around the old broad admin MCP surface.

2. Never hard-code bare legacy MCP tool names in prompts, specs, or workflows.
   - Forbidden examples:
     - `chatgptrest_ask`
     - `chatgptrest_consult`
     - `chatgptrest_result`
     - `chatgptrest_followup`
     - `chatgptrest_ops_status`
     - `chatgptrest_job_wait`
     - `chatgptrest_job_wait_background_*`
   - The actual callable tool ids depend on the runtime and may be namespaced. Prompts must not assume a bare tool name will exist.

3. When a prompt or workflow needs an explicit command, prefer wrapper or REST.
   - Wrapper:
     - `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
   - Public REST:
     - `POST /v3/agent/turn`
     - `GET /v3/agent/session/{session_id}`
     - `GET /v3/agent/session/{session_id}/stream`
     - `POST /v3/agent/cancel`

4. Treat the broad ChatgptREST MCP surface as internal/admin only.
   - It is allowed for maintenance, repair, and low-level debugging.
   - It is not the default interface for Codex, Claude Code, or Antigravity task prompts.

5. For long-running coding-agent tasks, prefer deferred/server-side coordination.
   - Use the public agent session model or wrapper outputs.
   - Do not teach agents to manually chain low-level MCP wait/result tools by name.

### Operational Consequence

If a coding agent needs ChatgptREST, the prompt should say one of these:
- use the public advisor-agent surface
- use the repo wrapper script
- use the public REST fallback

It should not say:
- call `chatgptrest_consult(...)`
- call `chatgptrest_ask(...)`
- call `chatgptrest_job_wait(...)`

### Review / Research Example

Good:

```bash
/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --provider chatgpt \
  --preset pro_extended \
  --github-repo haizhouyuan/ChatgptREST \
  --idempotency-key review-001 \
  --question "Review the codebase and identify the highest-risk regressions."
```

Good:

```bash
curl -s http://127.0.0.1:18711/v3/agent/turn \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: ${OPENMIND_API_KEY}" \
  -d '{
    "message": "Review the codebase and identify the highest-risk regressions.",
    "goal_hint": "code_review",
    "delivery_mode": "deferred"
  }'
```

Bad:

```text
Use MCP tool chatgptrest_consult(...)
```
