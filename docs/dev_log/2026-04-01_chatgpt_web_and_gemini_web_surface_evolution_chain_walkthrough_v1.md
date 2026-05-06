# 2026-04-01 chatgpt_web/gemini_web surface evolution chain walkthrough v1

## What I checked

- policy/docs
  - `docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md`
  - `docs/2026-03-23_coding_agent_mcp_surface_policy_v4.md`
  - `docs/2026-03-17_mcp_and_api_surface_inventory_v1.md`
  - `docs/client_interactions_v3.md`
  - `docs/contract_v1.md`
  - `docs/runbook.md`
  - `AGENTS.md`
- code
  - `chatgptrest/providers/registry.py`
  - `chatgptrest/mcp/_providers.py`
  - `chatgptrest/mcp/server.py`
  - `chatgptrest/mcp/agent_mcp.py`
  - `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
  - `chatgptrest/cli.py`
  - `chatgptrest/api/routes_advisor.py`
  - `chatgptrest/api/routes_advisor_v3.py`
  - `chatgptrest/api/routes_agent_v3.py`
  - `chatgptrest/api/write_guards.py`
  - `chatgptrest/api/routes_consult.py`
  - `openclaw_extensions/openmind-advisor/index.ts`
- history
  - `git log` across the above files/docs

## What changed in my understanding

The important correction is this:

- `chatgpt_web.ask` and `gemini_web.ask` are not “the current user entrypoints”
- they are “the long-lived provider execution substrate”

The user-facing and coding-agent-facing story later moved upward to:

- advisor routes
- then `/v3/agent/turn`
- then the slim public advisor-agent MCP

## Why the repo feels messy

Because migration was additive:

- new facade added
- old jobs path kept
- broad MCP kept
- bare tool names kept
- wrapper retrofitted instead of replaced
- CLI retrofitted instead of replaced
- OpenClaw compatibility alias kept

So the repo now contains both:

- current canonical path
- old-but-still-working shadow paths

## Most important evidence points

- broad/admin MCP still contains legacy low-level tools and new agent tools side by side:
  - `chatgptrest/mcp/server.py`
- slim public MCP exists specifically to avoid exposing the 51-tool broad surface:
  - `chatgptrest/mcp/agent_mcp.py`
- wrapper is now agent-first by default, but legacy jobs mode still exists behind explicit maintenance gating:
  - `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
- CLI now defaults agent commands to public MCP, but still exposes jobs/advisor/admin surfaces:
  - `chatgptrest/cli.py`
- direct low-level and direct REST use are now actively blocked for normal coding-agent identities:
  - `chatgptrest/api/write_guards.py`
  - `chatgptrest/api/routes_agent_v3.py`
- OpenClaw compatibility name remains, but current code now hits `/v3/agent/turn` directly:
  - `openclaw_extensions/openmind-advisor/index.ts`

## Final takeaway

The repo’s current northbound answer is actually clear:

- coding agents: public advisor-agent MCP
- orchestration facade: `/v3/agent/turn`
- underlying execution: `chatgpt_web.ask` / `gemini_web.ask`

What is unclear is not the new answer itself, but the fact that the old answers still remain visible.
