# 2026-03-17 Public Advisor Agent Facade Integration Test Plan v1

## 1. Scope

This test plan covers real-business integration flows across the public advisor-agent facade system, including:

- `/v3/agent/*` public facade endpoints
- MCP facade tools (`chatgptrest-agent-mcp`)
- OpenClaw openmind-advisor plugin
- CLI wrapper (`chatgptrest_call.py`)
- Compatibility with legacy `/v2` and `/v1` surfaces

## 2. Environments / Prerequisites

### 2.1 Required Services

| Service | Port | Purpose |
|---------|------|---------|
| ChatgptREST API | 18711 | Core REST API |
| Advisor API (v3) | 18713 | Agent facade |
| MCP Server (agent) | 18714 | Public MCP |
| Chrome (CDP) | 9222 | Browser automation |

### 2.2 Environment Variables

```
OPENMIND_API_KEY=<test-key>
CHATGPTREST_API_TOKEN=<test-token>
OPENMIND_AUTH_MODE=strict
OPENMIND_RATE_LIMIT=10
CHATGPTREST_AGENT_MCP_BASE_URL=http://127.0.0.1:18711
```

### 2.3 Test Data

- Test user accounts (different roles)
- Sample code files for review flows
- Sample images for generation
- KB documents for knowledge lookup

## 3. Test Matrix

### 3.1 Core Endpoint Tests

| Feature | Endpoint | Method | Input | Expected Output |
|---------|----------|--------|-------|-----------------|
| Agent turn basic | `/v3/agent/turn` | POST | message | ok, answer, session_id |
| Agent turn with goal_hint | `/v3/agent/turn` | POST | goal_hint=research | routes to consult/gemini |
| Agent session status | `/v3/agent/session/{id}` | GET | session_id | ok, status, job_id |
| Agent cancel | `/v3/agent/cancel` | POST | session_id | ok, status=cancelled |
| Auth valid key | `/v3/agent/turn` | POST | X-Api-Key | 200 OK |
| Auth invalid key | `/v3/agent/turn` | POST | wrong-key | 401 Unauthorized |
| Auth missing config | `/v3/agent/turn` | POST | no-key | 503 with message |
| Rate limiting | `/v3/agent/turn` | POST | >10 req/min | 429 Too Many Requests |

### 3.2 Goal Hint Routing Tests

| Goal Hint | Expected Provider | Expected Kind |
|-----------|-------------------|---------------|
| (none/default) | chatgpt | chatgpt_web.ask |
| code_review | chatgpt | chatgpt_web.ask |
| research | chatgpt | chatgpt_web.ask |
| report | chatgpt | chatgpt_web.ask |
| image | gemini | gemini_web.generate_image |
| consult | consult | consult |
| dual_review | consult | consult |
| gemini_research | gemini | gemini_web.ask |
| gemini_deep_research | gemini | gemini_web.ask |

### 3.3 Parameter Forwarding Tests

| Parameter | CLI Flag | MCP Parameter | API Field | Test |
|-----------|----------|---------------|-----------|------|
| role_id | --role-id | roleId | role_id | verify sent to backend |
| user_id | --user-id | - | user_id | verify in context |
| trace_id | --trace-id | - | trace_id | verify in logs |
| session_id | --session-id | sessionId | session_id | verify continuity |
| goal_hint | --goal-hint | goalHint | goal_hint | verify routing |
| depth | --depth | depth | depth | verify execution |
| timeout_seconds | --timeout-seconds | timeoutSeconds | timeout_seconds | verify timeout |

### 3.4 OpenClaw Plugin Tests

| Test | Description |
|------|-------------|
| Plugin loads | Verify openmind-advisor loads in OpenClaw |
| Tool registered | Verify openmind_advisor_ask is available |
| Calls v3/turn | Verify plugin calls /v3/agent/turn |
| Session continuity | Verify session_id passed through |
| Goal hint support | Verify goalHint translated to goal_hint |
| Response parsing | Verify agent response parsed correctly |

### 3.5 MCP Tool Tests

| Tool | Input | Expected |
|------|-------|----------|
| advisor_agent_turn | message, session_id, goal_hint | Full agent response |
| advisor_agent_cancel | session_id | Cancelled status |
| advisor_agent_status | session_id | Session state |

### 3.6 Compatibility Tests

| Legacy Path | Test |
|-------------|------|
| `/v1/jobs/*` | Submit job, wait, get answer - still works |
| `/v2/advisor/ask` | Direct advisor ask - still works |
| `/v2/advisor/advise` | Direct advisor advise - still works |
| MCP (legacy) | chatgptrest-mcp - still works |

## 4. Test Scenarios

### 4.1 Basic Research Flow

```
1. POST /v3/agent/turn {message: "What is Kubernetes?", goal_hint: "research"}
2. Verify: status=completed, answer contains explanation, route=research
3. GET /v3/agent/session/{session_id}
4. Verify: status=completed, job_id present
```

### 4.2 Code Review Flow

```
1. POST /v3/agent/turn {message: "Review this code", attachments: ["/path/to/code.py"], goal_hint: "code_review"}
2. Verify: status=completed, route=code_review
3. GET /v3/agent/session/{session_id}
4. Verify: status=completed, review feedback in answer
```

### 4.3 Image Generation Flow

```
1. POST /v3/agent/turn {message: "Generate a logo", goal_hint: "image"}
2. Verify: status=completed, route=image, artifacts contains image URL
```

### 4.4 Dual-Model Consult Flow

```
1. POST /v3/agent/turn {message: "Compare approaches", goal_hint: "consult"}
2. Verify: status=completed, route=consult
3. Verify: provenance shows multiple providers
```

### 4.5 Gemini Deep Research Flow

```
1. POST /v3/agent/turn {message: "Deep research on AI trends", goal_hint: "gemini_deep_research"}
2. Verify: status=completed, route=gemini_deep_research
3. Verify: provenance shows gemini provider
```

### 4.6 Session Cancel Flow

```
1. POST /v3/agent/turn {message: "Long running task", session_id: "test"}
2. POST /v3/agent/cancel {session_id: "test"}
3. Verify: status=cancelled in response
4. GET /v3/agent/session/test
5. Verify: status=cancelled
```

### 4.7 Role-Based Execution

```
1. POST /v3/agent/turn {message: "DevOps question", role_id: "devops"}
2. Verify: role_id passed to execution
3. Verify: response reflects devops role context
```

### 4.8 MCP Integration Flow

```
1. Call advisor_agent_turn via MCP
2. Verify: returns full agent response
3. Call advisor_agent_status
4. Verify: session status matches
5. Call advisor_agent_cancel
6. Verify: session cancelled
```

### 4.9 OpenClaw Plugin Flow

```
1. Load openmind-advisor plugin in OpenClaw
2. Call openmind_advisor_ask tool
3. Verify: calls /v3/agent/turn (not legacy endpoints)
4. Verify: returns agent-style response
5. Verify: provenance, next_action included
```

## 5. Acceptance Criteria

### 5.1 Functional Criteria

- [ ] `/v3/agent/turn` returns 200 with valid request and credentials
- [ ] `/v3/agent/turn` returns 401 with invalid credentials
- [ ] `/v3/agent/turn` returns 503 when no auth configured
- [ ] `/v3/agent/turn` returns 400 when message missing
- [ ] `/v3/agent/session/{id}` returns session state with job_id
- [ ] `/v3/agent/cancel` marks session as cancelled
- [ ] `/v3/agent/cancel` attempts to cancel underlying job
- [ ] Goal hints route to correct providers
- [ ] Role/user/trace IDs are forwarded correctly

### 5.2 Integration Criteria

- [ ] MCP tools work correctly
- [ ] OpenClaw plugin works correctly
- [ ] CLI wrapper works correctly
- [ ] Legacy surfaces still work

### 5.3 Performance Criteria

- [ ] Turn requests complete within timeout
- [ ] Rate limiting works correctly
- [ ] Session state persists correctly

## 6. Artifacts to Collect

For each test run, collect:

- HTTP request/response logs (full headers and bodies)
- Session state snapshots from `/v3/agent/session/{id}`
- Job state from `/v1/jobs/{job_id}`
- MCP tool response payloads
- OpenClaw plugin logs

## 7. Automation vs Manual

### 7.1 Automated Tests

- Unit tests for routes, MCP, CLI parser
- Auth/security tests
- Parameter forwarding tests
- Basic flow tests (mocked)

### 7.2 Manual/Live Tests

- Full end-to-end flows with real browser
- Image generation with real Gemini
- Deep research with real model calls
- OpenClaw integration tests

## 8. Rollout Order

1. **Phase 1**: Unit tests for new routes pass
2. **Phase 2**: Auth/security regression tests pass
3. **Phase 3**: Basic live flows work (turn, status, cancel)
4. **Phase 4**: Goal hint routing works (image, consult)
5. **Phase 5**: OpenClaw plugin integration works
6. **Phase 6**: MCP integration works
7. **Phase 7**: CLI wrapper works
8. **Phase 8**: Legacy compatibility verified

## 9. Regression Suites

| Change Type | Run Tests |
|-------------|-----------|
| Route changes | test_routes_agent_v3.py, test_routes_advisor_v3_security.py |
| MCP changes | test_agent_mcp.py |
| OpenClaw changes | test_openclaw_cognitive_plugins.py |
| CLI changes | test_skill_chatgptrest_call.py, test_cli_improvements.py |
| Auth changes | test_routes_advisor_v3_security.py |
| Routing changes | test_routes_agent_v3.py (goal_hint tests) |
