# Coding-Agent-V1 Default Contract Implementation V1

Date: 2026-04-08

## Outcome

Work Package B is now implemented.

The public MCP at `http://127.0.0.1:18712/mcp` keeps a single transport but exposes two explicit lanes:

- `coding-agent-v1`
- `advisor-agent`

`coding-agent-v1` is now the default northbound contract for:

- Codex
- Claude Code
- Antigravity

## What changed

### 1. Public MCP default lane

Added narrow coding-agent tools on the same public MCP surface:

- `coding_agent_turn`
- `coding_agent_wait`
- `coding_agent_answer`
- `coding_agent_status`
- `coding_agent_cancel`

These tools project the existing public session semantics into a narrower contract:

- required `message`
- optional `session_id`
- optional `project_id`
- optional `goal_hint`
- optional `execution_profile`
- optional `attachments`
- optional `github_repo`
- optional `trace_id`
- `timeout_seconds`
- `delivery_mode`

### 2. Broad advisor lane remains available

The existing `advisor_agent_*` tools remain available for explicit broad workflows such as:

- `task_intake`
- `workspace_request`
- `contract_patch`
- role-bound / user-bound context
- non-default depth control

### 3. Wrapper default changed

`skills-src/chatgptrest-call/scripts/chatgptrest_call.py` now defaults to:

- `--agent-surface coding-agent-v1`

The wrapper now:

- rejects `task_intake` / `workspace_request` / `contract_patch` in default mode
- rejects non-default `--depth` in default mode
- rejects `--role-id` / `--user-id` in default mode
- uses `coding_agent_turn/wait/answer/status` by default
- preserves `--agent-surface advisor-agent` as the explicit escape hatch

### 4. CLI default changed

`chatgptrestctl agent *` now defaults to the coding-agent lane on public MCP:

- `agent turn` -> `coding_agent_turn`
- `agent status` -> `coding_agent_status`
- `agent cancel` -> `coding_agent_cancel`

`--agent-surface advisor-agent` preserves the broader path.

## Files changed

Core implementation:

- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py)
- [chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py)
- [cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py)

Acceptance coverage:

- [test_agent_mcp.py](/vol1/1000/projects/ChatgptREST/tests/test_agent_mcp.py)
- [test_skill_chatgptrest_call_coding_agent_v1.py](/vol1/1000/projects/ChatgptREST/tests/test_skill_chatgptrest_call_coding_agent_v1.py)
- [test_cli_improvements.py](/vol1/1000/projects/ChatgptREST/tests/test_cli_improvements.py)
- [test_cli_chatgptrestctl.py](/vol1/1000/projects/ChatgptREST/tests/test_cli_chatgptrestctl.py)

Operational docs:

- [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)
- [contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/contract_v1.md)
- [runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md)
- [SKILL.md](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/SKILL.md)
- [openai.yaml](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/agents/openai.yaml)

## Acceptance

Targeted acceptance for Work Package B passed:

- `coding_agent_turn` projects the narrow contract and keeps project scope
- invalid `execution_profile` is rejected
- provisional finality is not reported as ready
- no-job answer fallback still works
- wrapper defaults to `coding-agent-v1`
- wrapper uses `coding_agent_turn -> coding_agent_wait -> coding_agent_answer`
- wrapper rejects broad advisor payloads in default mode
- CLI defaults to `coding_agent_*`
- CLI can still explicitly request `advisor-agent`

Executed test command:

```bash
./.venv/bin/pytest -q \
  tests/test_agent_mcp.py \
  tests/test_skill_chatgptrest_call_coding_agent_v1.py \
  tests/test_cli_improvements.py \
  tests/test_cli_chatgptrestctl.py
```

## Boundary

This change does not remove `advisor-agent`.

It only redefines the default coding-agent story:

- narrow by default
- broad only by explicit opt-in

This is the intended product boundary for the next stage and should be treated as the new baseline.
