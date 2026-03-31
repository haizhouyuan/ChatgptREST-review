# 2026-03-17 Unified Advisor Agent Surface CC AgentTeams Prompt v1

```text
You are Claude Code working on ChatgptREST.

Repo:
- /vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317

Branch:
- feat/public-advisor-agent-facade

This task MUST use Claude Code official Agent Teams, not a single-session workflow.

First verify:
- Claude Code version is >= 2.1.32
- CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 is enabled

If Agent Teams cannot be enabled, stop and return JSON with status=blocked and the exact blocker.

Read these first:
- /vol1/1000/projects/ChatgptREST/docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md
- /vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-17_unified_advisor_agent_surface_cc_task_spec_v2.md
- /vol1/1000/projects/ChatgptREST/AGENTS.md

Required outcome:
- fully complete the public advisor-agent convergence scope
- fully test it
- prepare a PR for review
- return JSON only

You must deliver all of the following:

1. Public HTTP facade
   - POST /v3/agent/turn
   - GET /v3/agent/session/{session_id}
   - POST /v3/agent/cancel

2. Public MCP facade
   - separate public MCP server
   - tools:
     - advisor_agent_turn
     - advisor_agent_cancel
     - optional advisor_agent_status

3. OpenClaw convergence
   - keep tool name openmind_advisor_ask
   - internally route it to /v3/agent/turn
   - remove ask|advise split and manual jobs wait/answer stitching

4. CLI convergence
   - add chatgptrest agent turn|status|cancel
   - make skills-src/chatgptrest-call/scripts/chatgptrest_call.py agent-first by default

5. Docs and compatibility
   - keep /v1/jobs/*, /v2/advisor/ask, /v2/advisor/advise, and chatgptrest-mcp working
   - update runbook / registry / contracts / relevant integration docs

Agent Teams structure:
- teammate 1: http-facade
- teammate 2: public-mcp
- teammate 3: openclaw-adapter
- teammate 4: cli-wrapper
- teammate 5: integrator

Rules:
- split work by disjoint write scope
- teammates should not overlap files unless integrator is reconciling
- do not stop at partial implementation
- integrator must run final tests, final doc sync, and PR prep

Minimum tests that must actually pass:
- ./.venv/bin/pytest -q tests/test_mcp_advisor_tool.py tests/test_advisor_v3_end_to_end.py
- ./.venv/bin/pytest -q tests/test_openclaw_cognitive_plugins.py
- ./.venv/bin/pytest -q tests/test_skill_chatgptrest_call.py tests/test_cli_improvements.py
- all new agent API / MCP tests you add
- if router/security changed:
  - ./.venv/bin/pytest -q tests/test_routes_advisor_v3_security.py

Hard requirements:
- follow AGENTS.md
- commit every meaningful change
- do not touch unrelated dirty files
- write a walkthrough doc with _v1.md suffix
- run closeout before finishing
- if gh auth permits, open a PR; otherwise report the exact blocker

When finished, return JSON only with this shape:
{
  "status": "succeeded" | "blocked" | "failed",
  "branch": "feat/public-advisor-agent-facade",
  "summary": "short summary",
  "commits": ["sha subject", "..."],
  "tests": [
    {"command": "pytest ...", "status": "passed|failed|not_run", "details": "short note"}
  ],
  "pull_request": {
    "status": "opened|ready_local|blocked",
    "url": "string or empty",
    "branch": "string",
    "base": "string",
    "blocker": "string or empty"
  },
  "walkthrough_path": "absolute path or empty string",
  "changed_files": ["path", "..."],
  "residual_risks": ["...", "..."],
  "notes": ["...", "..."]
}
```
