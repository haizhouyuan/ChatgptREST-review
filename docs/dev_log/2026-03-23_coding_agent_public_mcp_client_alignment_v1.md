# 2026-03-23 Coding Agent Public MCP Client Alignment v1

## Summary

This package aligns the coding-agent northbound surface around the systemd-managed public advisor-agent MCP at `http://127.0.0.1:18712/mcp`.

The goal is not to introduce a new execution lane. The goal is to make Codex, Claude Code, and Antigravity converge on the same public northbound surface, the same tool names, and the same wrapper skill guidance.

## What Changed

### Repo docs and skill guidance

- Updated [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md) with a dedicated `Coding Agent 默认入口（2026-03-23）` section.
- Updated [CLAUDE.md](/vol1/1000/projects/ChatgptREST/CLAUDE.md) to document the public advisor-agent MCP as the default Claude Code surface.
- Updated [GEMINI.md](/vol1/1000/projects/ChatgptREST/GEMINI.md) to document the same northbound default for Codex / Claude Code / Antigravity tasks.
- Updated [skills-src/chatgptrest-call/SKILL.md](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/SKILL.md) so the wrapper skill is public-MCP-first, with legacy queued-job mode explicitly downgraded to an expert fallback.
- Updated [docs/client_projects_registry.md](/vol1/1000/projects/ChatgptREST/docs/client_projects_registry.md) so the registry now records the March 23 coding-agent northbound cutover.

### Governance checker

- Extended [ops/check_public_mcp_client_configs.py](/vol1/1000/projects/ChatgptREST/ops/check_public_mcp_client_configs.py) so drift checks now cover:
  - Codex TOML configs
  - Claude Code JSON configs
  - Antigravity `mcp_config.json`
  - the repo wrapper default path
- Added targeted regression coverage in [tests/test_check_public_mcp_client_configs.py](/vol1/1000/projects/ChatgptREST/tests/test_check_public_mcp_client_configs.py).

### External client alignment

The following non-repo client-side files were aligned to the same public MCP URL:

- `/home/yuanhaizhou/.gemini/GEMINI.md`
- `/home/yuanhaizhou/.gemini/antigravity/mcp_config.json`
- `/vol1/1000/home-yuanhaizhou/.home-codex-official/.antigravity/mcp_config.json`

Claude Code configs were already pointing at the public MCP and did not require a behavior change:

- `/home/yuanhaizhou/.claude.json`
- `/vol1/1000/home-yuanhaizhou/.home-codex-official/.claude.json`
- `/vol1/1000/home-yuanhaizhou/.claude-minimax/.claude.json`

## Outcome

The intended operating mode is now:

- Codex uses public advisor-agent MCP by default.
- Claude Code uses public advisor-agent MCP by default.
- Antigravity uses public advisor-agent MCP by default.
- The wrapper skill teaches the same northbound contract and no longer treats low-level provider paths as the default.

The governance checker now verifies that these client configs continue to point at the systemd-managed public MCP instead of drifting back to local `stdio` servers.

## Scope Boundary

This package aligns docs, wrapper guidance, and client config governance.

It does not:

- hard-disable all other internal REST surfaces
- change the live public agent contract itself
- replace the existing public-agent validation packs

