# 2026-03-17 Unified Advisor Agent Surface CC AgentTeams Prompt v3

```text
You are Claude Code working on ChatgptREST.

Repo:
- /vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317

Branch:
- feat/public-advisor-agent-facade

This task MUST use Claude Code official Agent Teams.

First verify:
- Claude Code version is compatible with Agent Teams
- Agent Teams is enabled in this environment

If Agent Teams cannot be enabled, stop and return JSON with status=blocked and the exact blocker.

Read these first, in order:
- /vol1/1000/projects/ChatgptREST/docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v2.md
- /vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-17_unified_advisor_agent_surface_cc_task_spec_v3.md
- /vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317/docs/dev_log/2026-03-17_public_advisor_agent_partial_implementation_gap_review_v1.md
- /vol1/1000/projects/ChatgptREST/AGENTS.md

Important branch context:
- this branch already contains first-pass scaffold commits for:
  - /v3/agent/*
  - public MCP module
  - chatgptrest agent CLI commands
- those commits are NOT the final design
- treat them as scaffolding only
- keep the useful namespace/surface shape where reasonable
- but rework internals to match the quality-first blueprint

This is a quality-first task.

Do NOT optimize the public agent layer for saving LLM calls if that makes it dumber, more brittle, or more error-prone.

Required outcome:
- fully complete the public advisor-agent convergence scope
- implement planner + judge + recovery-aware finalization
- finish the missing OpenClaw/plugin/MCP runtime wiring/test/doc work
- fully test it
- prepare a PR for review
- return JSON only

You must deliver all of the following:

1. Public HTTP facade
   - POST /v3/agent/turn
   - GET /v3/agent/session/{session_id}
   - POST /v3/agent/cancel

2. Planner
   - facade-level plan generation
   - strong-model planning allowed when tasks are ambiguous, attachment-heavy, review-like, research-heavy, or recovery-touched

3. Judge
   - deterministic quality gate
   - semantic/LLM judge for complex or high-risk tasks
   - must decide retry / escalate / replan when needed

4. Recovery-aware finalization
   - after retry/recovery, do not deliver blindly
   - re-run judge before final delivery

5. Public MCP facade
   - separate public MCP server
   - tools:
     - advisor_agent_turn
     - advisor_agent_cancel
     - optional advisor_agent_status
   - include runtime wiring:
     - server entrypoint
     - start script
     - systemd unit template

6. OpenClaw convergence
   - keep tool name openmind_advisor_ask
   - internally route it to /v3/agent/turn
   - remove ask|advise split and manual jobs wait/answer stitching

7. CLI convergence
   - add chatgptrest agent turn|status|cancel
   - make skills-src/chatgptrest-call/scripts/chatgptrest_call.py agent-first by default
   - ensure it is truly end-to-end agent-first, not just parser-level

8. Docs and compatibility
   - keep /v1/jobs/*, /v2/advisor/ask, /v2/advisor/advise, and chatgptrest-mcp working
   - update runbook / registry / contracts / relevant integration docs

Agent Teams structure:
- teammate 1: http-facade
- teammate 2: planner-judge
- teammate 3: public-mcp
- teammate 4: openclaw-adapter
- teammate 5: cli-wrapper
- teammate 6: integrator-review

Rules:
- split by disjoint write scope
- do not stop at partial implementation
- use stronger model assistance when it materially improves route quality, judging quality, or final review quality
- do not make the facade rule-only just to save calls
- integrator-review must run final tests, final doc sync, and PR prep

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
