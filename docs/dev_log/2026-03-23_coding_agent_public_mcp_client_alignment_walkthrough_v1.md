# 2026-03-23 Coding Agent Public MCP Client Alignment Walkthrough v1

## Why this package existed

The public advisor-agent MCP was already the intended northbound surface, but the surrounding client guidance was still uneven:

- Codex docs were closer to current policy than Claude Code and Antigravity docs.
- The repo governance checker only verified Codex TOML configs plus the wrapper.
- Antigravity had one real config aligned to `http://127.0.0.1:18712/mcp`, but the official home profile did not yet have an `mcp_config.json`.

That meant the runtime could be correct while the client estate could still drift.

## What was checked first

1. Repo docs and wrapper skill were reviewed:
   - `AGENTS.md`
   - `CLAUDE.md`
   - `GEMINI.md`
   - `skills-src/chatgptrest-call/SKILL.md`
   - `docs/client_projects_registry.md`
2. Actual Claude Code and Antigravity config files were inspected.
3. The existing checker implementation and tests were reviewed to confirm that only Codex + wrapper were covered.

## What was changed

### 1. Repo-level policy alignment

The repo docs now tell the same story:

- public advisor-agent MCP is the default coding-agent surface
- default tools are `advisor_agent_turn`, `advisor_agent_status`, `advisor_agent_cancel`
- canonical northbound objects are `message`, `goal_hint`, `execution_profile`, `task_intake`, `contract_patch`, and `workspace_request`
- coding agents should not default to `/v3/agent/*` REST or legacy bare MCP names

### 2. Skill alignment

The `chatgptrest-call` skill was rewritten so that:

- agent/public MCP mode is the default
- legacy queued-job mode is clearly labeled as expert-only
- examples now include `thinking_heavy`, `contract_patch`, and `workspace_request`

### 3. Governance checker expansion

The checker now covers three client families instead of one:

- Codex TOML configs
- Claude Code JSON configs
- Antigravity JSON configs

It still checks the wrapper default path, so drift is caught in both client config and wrapper guidance.

### 4. External client config alignment

The official Antigravity profile was missing a config file, so a matching `mcp_config.json` was created under:

- `/vol1/1000/home-yuanhaizhou/.home-codex-official/.antigravity/mcp_config.json`

This mirrors the already-working public MCP setup used by the existing Antigravity profile under `/home/yuanhaizhou/.gemini/antigravity/`.

## Validation

The package should be validated with:

```bash
./.venv/bin/pytest -q tests/test_check_public_mcp_client_configs.py
python3 -m py_compile ops/check_public_mcp_client_configs.py tests/test_check_public_mcp_client_configs.py
PYTHONPATH=. ./.venv/bin/python ops/check_public_mcp_client_configs.py
```

Expected success state:

- all Codex configs point at `http://127.0.0.1:18712/mcp`
- all Claude Code configs point at `http://127.0.0.1:18712/mcp`
- both Antigravity configs point at `http://127.0.0.1:18712/mcp`
- wrapper agent mode still routes via the public advisor-agent MCP

## Final operational rule

For coding agents, the stable northbound entry is:

- `http://127.0.0.1:18712/mcp`

Anything else should now be treated as internal runtime plumbing or expert-only maintenance surface, not default client guidance.

