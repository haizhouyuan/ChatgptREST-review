# 2026-03-17 Public Advisor Agent Facade Walkthrough v1

## Summary

This walkthrough documents the implementation of the public advisor-agent facade for ChatgptREST, which provides a unified high-level API surface for agent interactions.

## What Was Implemented

### 1. Public Agent API (`/v3/agent/*`)

Added new FastAPI routes in `chatgptrest/api/routes_agent_v3.py`:

- `POST /v3/agent/turn` - Execute a single agent turn
- `GET /v3/agent/session/{session_id}` - Retrieve session state
- `POST /v3/agent/cancel` - Cancel a running session
- `GET /v3/agent/health` - Health check

Key features:
- Session-based continuity without client managing job IDs
- Goal hint routing (code_review, research, image, consult, gemini_research, etc.)
- Role/user/trace ID forwarding
- Automatic answer delivery (no manual wait/answer pagination)

### 2. Auth Semantics Fix

Fixed the authentication behavior:
- **Before**: Returned 503 for missing/invalid credentials in strict mode
- **After**: Returns 401 for invalid credentials, 503 for missing configuration

Changes in `routes_agent_v3.py`:
- Clear 503 error when neither OPENMIND_API_KEY nor CHATGPTREST_API_TOKEN is set
- 401 for invalid/missing credentials when auth is configured

### 3. Cancel Functionality Fix

Fixed session cancel to actually cancel the underlying job:
- Session now stores `job_id` when created
- Cancel route retrieves stored job_id and sends cancel to `/v1/jobs/{job_id}/cancel`
- Session status endpoint surfaces job_id for verification

### 4. Wrapper Parameter Support

Added CLI wrapper parameters in `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`:
- `--role-id` - Role ID for agent context
- `--user-id` - User ID for request tracing
- `--trace-id` - Trace ID for correlation

These are forwarded to `/v3/agent/turn` in agent-first mode.

### 5. OpenClaw Plugin Convergence

Updated `openclaw_extensions/openmind-advisor/index.ts`:

**Before**: Called `/v2/advisor/ask` or `/v2/advisor/advise` with manual wait/answer pagination

**After**: Calls `/v3/agent/turn` directly with:
- Complete agent response handling (no manual pagination)
- New parameters: goal_hint, depth, session_id
- Agent-style response parsing with provenance tracking
- Backward compatibility: tool name preserved as `openmind_advisor_ask`

### 6. Improved Agent Routing

Extended route_mapping in `routes_agent_v3.py`:

| Goal Hint | Provider | Kind |
|-----------|----------|------|
| consult | consult | consult |
| dual_review | consult | consult |
| gemini_research | gemini | gemini_web.ask |
| gemini_deep_research | gemini | gemini_web.ask |

Added context flags for consult/gemini execution paths.

### 7. New Test Coverage

Added new test files:

- `tests/test_routes_agent_v3.py` - Tests for /v3/agent/* endpoints
- `tests/test_agent_mcp.py` - Tests for agent MCP tools

### 8. Integration Test Plan

Created comprehensive test plan at `docs/2026-03-17_public_advisor_agent_integration_test_plan_v1.md` covering:
- Core endpoint tests
- Goal hint routing matrix
- Parameter forwarding tests
- OpenClaw plugin tests
- MCP integration tests
- Compatibility tests

## Why These Changes

### Problem 1: Auth Semantics

The old code returned 503 for invalid credentials, which is misleading. 503 means "service unavailable" but the issue is authentication, not availability. Now returns 401 (Unauthorized) for auth failures.

### Problem 2: Cancel Not Working

The cancel endpoint marked the session as cancelled but never cancelled the underlying job because job_id wasn't stored. Now it stores and uses job_id to cancel.

### Problem 3: OpenClaw Plugin Not Using Agent Contract

The plugin was calling legacy endpoints with manual wait/answer pagination. This created unnecessary complexity and didn't benefit from the quality-first agent contract. Now it uses `/v3/agent/turn` directly.

### Problem 4: Limited Goal Routing

The original implementation only supported a few goal hints and all routed to chatgpt. Now supports consult/dual-review (multi-model) and gemini research paths.

## Files Changed

| File | Change |
|------|--------|
| `chatgptrest/api/routes_agent_v3.py` | Auth fix, cancel fix, routing improvements |
| `skills-src/chatgptrest-call/scripts/chatgptrest_call.py` | Added role_id/user_id/trace_id flags |
| `openclaw_extensions/openmind-advisor/index.ts` | Converged to /v3/agent/turn |
| `openclaw_extensions/openmind-advisor/README.md` | Updated documentation |
| `tests/test_routes_agent_v3.py` | New test file |
| `tests/test_agent_mcp.py` | New test file |
| `docs/2026-03-17_public_advisor_agent_integration_test_plan_v1.md` | New test plan |

## Testing

Run the required tests:

```bash
# Agent routes tests
pytest -q tests/test_routes_agent_v3.py

# Agent MCP tests
pytest -q tests/test_agent_mcp.py

# Security/auth tests
pytest -q tests/test_routes_advisor_v3_security.py

# Legacy tests to verify compatibility
pytest -q tests/test_skill_chatgptrest_call.py
pytest -q tests/test_openclaw_cognitive_plugins.py
```

## Next Steps

1. Run full integration test plan
2. Add more end-to-end tests with live services
3. Consider adding planner/judge nodes per the v2 blueprint
4. Monitor for any issues with the new routing paths
