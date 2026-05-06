# 2026-03-17 Unified Advisor Agent Surface Walkthrough v1

## Summary

This walkthrough documents the implementation of the public advisor-agent facade that consolidates multiple entry points into a unified high-level agent interaction surface.

## What was done

### 1. Public HTTP Facade (v3/agent)

Created new REST endpoints at `/v3/agent/*`:

- **POST /v3/agent/turn** - Execute a single agent turn with message, session_id, goal_hint, depth, and context
- **GET /v3/agent/session/{session_id}** - Retrieve session state (fallback)
- **POST /v3/agent/cancel** - Cancel a running session
- **GET /v3/agent/health** - Health check

Key features:
- Abstracts away job/wait/answer machinery from clients
- Supports session continuity via session_id
- Returns final answer directly without client managing jobs
- Includes provenance (route, provider_path), delivery info, and recovery status

Files:
- `chatgptrest/api/routes_agent_v3.py` - New route file
- `chatgptrest/api/app.py` - Registered the new router

### 2. Public MCP Facade

Created a lightweight public MCP server with only 2-3 high-level tools:

- **advisor_agent_turn** - Execute agent turn
- **advisor_agent_cancel** - Cancel session
- **advisor_agent_status** - Get session status (optional)

Also added these tools to the existing `chatgptrest-mcp` for backward compatibility.

Files:
- `chatgptrest/mcp/agent_mcp.py` - New standalone MCP server
- `chatgptrest/mcp/server.py` - Added new tools to existing MCP

### 3. CLI Convergence

Added new CLI commands:

- `chatgptrest agent turn --message ... --goal-hint ... --depth ...`
- `chatgptrest agent status <session_id>`
- `chatgptrest agent cancel <session_id>`

Files:
- `chatgptrest/cli.py` - Added agent subparser and commands

### 4. Wrapper CLI Agent-First

Updated `chatgptrest_call.py` to be agent-first by default:

- Added `--agent` flag (default True) for agent-first mode
- Added `--no-agent` for legacy provider-first mode
- Added `--session-id`, `--goal-hint`, `--depth` for agent mode features

Files:
- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

### 5. Documentation

Updated `docs/contract_v1.md` with the new v3/agent contract including:
- Request/response schemas
- Endpoint descriptions

## Backward Compatibility

All existing interfaces continue to work:
- `/v1/jobs/*` - Low-level job queue (internal)
- `/v2/advisor/ask`, `/v2/advisor/advise` - Advisor endpoints (internal)
- `chatgptrest-mcp` - Full MCP server (internal/admin)
- Legacy CLI commands remain functional

## Tests

All required tests pass:
- `test_mcp_advisor_tool.py` - PASSED
- `test_advisor_v3_end_to_end.py` - PASSED
- `test_openclaw_cognitive_plugins.py` - PASSED
- `test_skill_chatgptrest_call.py` - PASSED (with --no-agent for legacy tests)

## What was NOT implemented (future work)

The v3 spec mentions:
- **Planner**: Facade-level plan generation with strong-model planning - Currently handled by ControllerEngine
- **Judge**: Deterministic quality gate + semantic judge - Partially handled by quality_threshold
- **Recovery-aware finalization**: Re-run judge before final delivery - Partially handled by retry logic

These features are partially covered by the existing ControllerEngine but could be enhanced in future iterations.

## Changed Files

- `chatgptrest/api/routes_agent_v3.py` (new)
- `chatgptrest/api/app.py` (modified)
- `chatgptrest/mcp/agent_mcp.py` (new)
- `chatgptrest/mcp/server.py` (modified)
- `chatgptrest/cli.py` (modified)
- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py` (modified)
- `docs/contract_v1.md` (modified)
- `tests/test_skill_chatgptrest_call.py` (modified - test fix)

## Commits

```
67a3fe9 feat(agent): add v3/agent public facade routes
4424165 feat(mcp): add public agent MCP tools
7a89a3a feat(cli): add chatgptrest agent turn|status|cancel commands
c114907 feat(call): make chatgptrest_call.py agent-first by default
c5cf820 docs: add v3/Agent contract to REST API contract
71d9dbb test: fix chatgptrest_call tests for agent-first mode
```
