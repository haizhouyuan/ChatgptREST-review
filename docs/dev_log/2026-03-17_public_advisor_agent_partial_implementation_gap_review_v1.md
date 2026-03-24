# 2026-03-17 Public Advisor Agent Partial Implementation Gap Review v1

## Purpose

This note reviews the current implementation draft on branch `feat/public-advisor-agent-facade` against the quality-first blueprint in:

- `docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v2.md`
- `docs/dev_log/2026-03-17_unified_advisor_agent_surface_cc_task_spec_v3.md`

The goal is not to discard all current work. The goal is to distinguish:

- useful scaffolding worth keeping
- incomplete shell layers that must be upgraded before this branch can be considered review-ready

## Current draft summary

Current implementation commits on this branch:

- `67a3fe9 feat(agent): add v3/agent public facade routes`
- `4424165 feat(mcp): add public agent MCP tools`
- `7a89a3a feat(cli): add chatgptrest agent turn|status|cancel commands`

These commits establish the following first-pass surface:

- `/v3/agent/*` route namespace
- `chatgptrest/mcp/agent_mcp.py`
- `chatgptrest agent turn|status|cancel`
- initial `chatgptrest_call.py` move toward agent-first mode

That is useful. But this branch is still **shell-first**, not yet **quality-first agent-grade**.

## What can be kept

### 1. Namespace and shape

These high-level choices are still good:

- use `/v3/agent/*` as the public HTTP contract
- use a separate `agent_mcp.py` module for the public MCP façade
- add a first-class `chatgptrest agent ...` CLI group
- keep compatibility with `/v1/jobs/*` and existing advisor surfaces

### 2. Surface consolidation direction

The branch already moves toward:

- a smaller MCP surface
- a simpler CLI surface
- a clearer public API namespace

That direction should remain.

### 3. `chatgptrest_call.py` migration direction

The wrapper already appears to be moving toward `--agent` default mode. That direction is aligned with the blueprint and should continue.

## What is not yet acceptable

### 1. `routes_agent_v3.py` is a thin shell, not a true agent control loop

Current `chatgptrest/api/routes_agent_v3.py` problems:

- no explicit planner node
- no explicit judge node
- no recovery-aware re-adjudication
- hardcoded route mapping directly inside the route handler
- `recovery_status` is currently a placeholder
- `next_action` is currently static
- `session` state is stored in an in-memory dict only

This is the biggest gap. Right now it is “new route + old substrate call”, not the smarter public agent described in the revised blueprint.

### 2. Route selection is too naive

The current implementation maps `goal_hint` to a narrow `intent_hint`, then calls `ControllerEngine.ask(...)` with a hardcoded route map.

That is not enough for:

- ambiguous asks
- attachment-heavy tasks
- review / research / report differentiation
- recovery-touched sessions

The revised plan explicitly requires a planner that may use stronger model assistance where needed.

### 3. No real quality judgment

The current route handler builds a response from `ControllerEngine.ask(...)` and immediately returns it.

What is missing:

- semantic completion check
- artifact completeness check
- route adequacy re-evaluation
- escalation / retry / replan decision

Without this, the new public surface is still vulnerable to the same “completed but not actually good enough” class of failure.

### 4. Cancellation semantics are façade-only

`POST /v3/agent/cancel` currently cancels session state and best-effort calls `/v1/jobs/{id}/cancel` if a job id is present.

But the session store does not robustly track actual underlying work lineage. This is not yet a durable cancellation model.

### 5. Session model is too weak

Current session handling:

- in-memory only
- stores last message / last answer / route

Missing:

- durable session state
- last successful delivery metadata
- planner/judge history
- recovery lineage
- richer `session -> run -> artifact` model

### 6. Public MCP still needs production wiring

`chatgptrest/mcp/agent_mcp.py` is a useful start, but this branch does **not yet** include:

- `chatgptrest_agent_mcp_server.py`
- `ops/start_agent_mcp.sh`
- `ops/systemd/chatgptrest-agent-mcp.service`

So the public MCP story is incomplete.

### 7. OpenClaw convergence has not been done

The branch does **not** yet update:

- `openclaw_extensions/openmind-advisor/index.ts`

That means OpenClaw is still on the old dual `ask|advise` path, which violates the convergence goal.

### 8. Tests are still missing

This branch currently has no visible commit adding the required test coverage for:

- `/v3/agent/turn`
- session continuation
- cancel path
- public MCP tools
- OpenClaw advisor plugin convergence
- updated wrapper behavior

Until these tests exist and pass, this branch is not ready for PR review.

## Recommended implementation decision

### Keep the branch

Do **not** throw away this branch.

Reason:

- the namespace choices are fine
- the public façade shape is useful
- the CLI and MCP scaffolding save time

### But treat current code as scaffolding only

The key implementation rule should be:

- keep the external shape where reasonable
- replace the simplistic internals with the quality-first control loop from the revised blueprint

That means:

1. keep `/v3/agent/*`
2. keep `agent_mcp.py`
3. keep `chatgptrest agent ...`
4. rework internals to add:
   - planner
   - judge
   - recovery-aware finalize
   - stronger session/run model
   - real OpenClaw convergence
   - public MCP runtime wiring
   - tests

## Concrete guidance for the next implementation round

### Must rework

- `chatgptrest/api/routes_agent_v3.py`
- possibly add supporting planner/judge modules instead of bloating the route file

### Must add

- public MCP server entrypoint
- start/systemd files
- OpenClaw advisor plugin changes
- tests
- docs sync

### Must verify

- `chatgptrest_call.py` default path is truly agent-first end to end, not just parser-level

## Bottom line

This branch is a useful **phase-0 scaffold**, not a PR-ready implementation.

It should be continued, not discarded. But it should be continued under the revised quality-first blueprint, not the earlier thin-facade interpretation.
