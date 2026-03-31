# Public Agent Facade Takeover And CCrunner Walkthrough v1

Date: 2026-03-17

## Why This Takeover Happened

The `feat/public-advisor-agent-facade` branch had moved past the first review round, but it still had structural gaps:

- `/v3/agent/turn` behaved like a thin controller submit wrapper for normal paths
- OpenClaw convergence was partially landed in source, but config and rebuild outputs were drifting
- direct tests for `/v3/agent/*` and public `agent_mcp` were still missing
- the agent-first skill wrapper still silently dropped important legacy context

The goal of this takeover was to make the public facade usable as a real client-facing agent surface and to close the OpenClaw/OpenMind convergence loop end to end.

## What Was Changed

### 1. `/v3/agent` now waits and finalizes instead of just submitting

File:

- `chatgptrest/api/routes_agent_v3.py`

Key changes:

- normal controller-backed turns now wait for controller delivery snapshots before returning
- `image` requests bypass controller route aliases and submit `gemini_web.generate_image` directly
- `consult` / `dual_review` requests create a consultation and return a combined multi-model delivery
- `gemini_research` / `gemini_deep_research` requests submit direct Gemini jobs instead of hoping planner route aliases will hit Gemini
- session records now persist `job_id` or `consultation_id`, and status refresh reconciles live job / consultation state
- cancel now propagates to underlying job ids instead of only flipping facade session state

### 2. Public MCP became attachment-capable

File:

- `chatgptrest/mcp/agent_mcp.py`

Key changes:

- `advisor_agent_turn` now accepts `attachments`, `role_id`, `user_id`, `trace_id`
- tool payload now forwards those fields to `/v3/agent/turn`
- direct test coverage for public MCP was added

### 3. Agent-first wrapper no longer drops repo / follow-up context

File:

- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`

Key changes:

- agent-first mode still forwards `--file-path`, `--role-id`, `--user-id`, `--trace-id`
- now also preserves legacy context in `--context-json`, including:
  - `github_repo`
  - `conversation_url`
  - `parent_job_id`
  - legacy provider / preset hints
  - selected legacy flags such as `deep_research`, `web_search`, `allow_queue`

### 4. OpenClaw plugin config drift was fixed

Files:

- `openclaw_extensions/openmind-advisor/openclaw.plugin.json`
- `scripts/rebuild_openclaw_openmind_stack.py`

Key changes:

- plugin manifest now exposes `defaultGoalHint` instead of stale `defaultMode/defaultIntentHint`
- rebuild script now emits converged `defaultGoalHint` config
- OpenClaw cognitive plugin tests and rebuild tests were updated accordingly

### 5. Direct coverage was added where the previous branch was blind

Files:

- `tests/test_agent_v3_routes.py`
- `tests/test_agent_mcp.py`
- `tests/test_skill_chatgptrest_call.py`
- `tests/test_openclaw_cognitive_plugins.py`
- `tests/test_rebuild_openclaw_openmind_stack.py`

What is now directly covered:

- `/v3/agent` auth semantics for 401 vs 503
- bearer token success path
- controller-backed wait/finalize path
- direct image substrate path
- direct consultation path
- cancel propagation for multi-job sessions
- MCP forwarding of attachments and identity fields
- agent-first wrapper forwarding of files and legacy context
- OpenClaw plugin source and rebuild config convergence

## CCrunner Handling

During takeover, the shared Claude Code runner was not reliably writing results when launched detached. The worker command would exit without a final `result.json`.

I fixed the shared skill script here:

- `/vol1/1000/home-yuanhaizhou/.codex-shared/skills/claudecode-agent-runner/scripts/claude_job_start.sh`

Fix summary:

- detached worker launch now prefers `setsid`
- stdin is explicitly redirected from `/dev/null`
- fallback launch path is preserved

After the fix, a smoke run completed successfully and produced a terminal result record. I then used the runner for a broad branch task once, confirmed the runner itself was stable, and canceled that broad job after it became clear the prompt scope was too wide for an efficient repair loop.

## Validation Run

Targeted validation:

- `tests/test_agent_v3_routes.py`
- `tests/test_agent_mcp.py`
- `tests/test_skill_chatgptrest_call.py`
- `tests/test_openclaw_cognitive_plugins.py`
- `tests/test_rebuild_openclaw_openmind_stack.py`

Broader regression validation:

- `tests/test_mcp_advisor_tool.py`
- `tests/test_advisor_v3_end_to_end.py`
- `tests/test_openclaw_cognitive_plugins.py`
- `tests/test_skill_chatgptrest_call.py`
- `tests/test_cli_improvements.py`
- `tests/test_rebuild_openclaw_openmind_stack.py`
- `tests/test_agent_v3_routes.py`
- `tests/test_agent_mcp.py`
- `tests/test_routes_advisor_v3_security.py`

## Commit Trail

Code/test takeover commit:

- `d221cbc fix(agent): finish public facade routing and coverage`

This walkthrough and the business integration plan are intended to be committed separately so the behavioral change and the rollout/testing documentation remain easy to audit.

## Notes

- GitNexus indexing on the main repo did not reflect the worktree diff accurately, so pre-commit scope verification used both GitNexus spot checks and plain `git diff --name-only` against the worktree.
- I also re-checked the dashboard `master` line while taking over. No dashboard code changes were made in this batch.
