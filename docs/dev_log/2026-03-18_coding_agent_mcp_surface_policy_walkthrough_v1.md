## Summary

This change tightens the coding-agent contract around ChatgptREST MCP usage.

Problem:
- Another Codex session tried to call bare legacy MCP names such as `chatgptrest_consult`.
- The backend API and MCP server were healthy.
- The failure mode came from prompts/workflows assuming unstable bare tool names instead of using the public agent surface or wrapper/REST fallbacks.

What changed:
- Added a dedicated policy document:
  - `docs/2026-03-18_coding_agent_mcp_surface_policy_v1.md`
- Updated `AGENTS.md` to forbid hard-coded legacy bare MCP names for Codex / Claude Code / Antigravity.
- Updated `.agents/workflows/code-review-upload.md` to replace the old `chatgptrest_ask(...)` example with the wrapper command.
- Updated `.agents/workflows/observe-driver.md` to stop telling agents to submit jobs with a legacy MCP bare name.
- Updated `skills-src/chatgptrest-call/SKILL.md` to prefer wrapper/public-agent/REST paths over legacy low-level MCP wait tools.

Why this is the right fix:
- Humans do not use MCP directly here.
- Coding agents are the actual MCP consumers.
- The fix should therefore live in agent-facing policy, prompts, workflows, and skills, not in human-facing explanations alone.
- Bare MCP names are runtime-dependent and not stable across Codex/CC/Antigravity environments.

Scope:
- Documentation and workflow/skill guidance only.
- No product code or runtime behavior changed in this task.

Notes:
- The repo working tree already had unrelated finbot systemd modifications and untracked files before this task.
- Those unrelated changes were left untouched.
