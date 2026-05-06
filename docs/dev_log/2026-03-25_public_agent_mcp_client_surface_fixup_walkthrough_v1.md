# 2026-03-25 Public Agent MCP Client Surface Fixup Walkthrough v1

## Why this package existed

The earlier issue pack correctly identified a client-usage problem, but two of the most damaging symptoms were service-side:

1. prompt-visible grounding still showed local file paths that ChatGPT Web cannot dereference
2. long-running public MCP turns still forced clients to infer wait/handoff semantics

This package fixes those at the server/public-MCP layer instead of pushing more normalization into individual coding-agent clients.

## What I changed

### 1. Stopped prompt-visible local path leakage

Changed:

- `chatgptrest/advisor/task_intake.py`

Implementation:

- added git-aware attachment inventory derivation
- reduced prompt-visible file references to sanitized labels such as repo-relative paths or basenames
- injected repo URL + branch notes when the attachment sits inside a git repo
- preserved the real attachment transport on `file_paths`

Effect:

- the provider still receives the real server-local attachment path for upload
- the model-facing contract sees a repo-aware summary instead of `/tmp/...` or `/vol1/...`

### 2. Made public MCP long-turn handoff explicit

Changed:

- `chatgptrest/mcp/agent_mcp.py`

Implementation:

- `advisor_agent_turn.attachments` now accepts scalar or list input
- sync-to-deferred auto-background now returns explicit handoff fields
- added `recommended_client_action`, `wait_tool`, and `progress`
- added `advisor_agent_wait(...)`

Effect:

- coding agents can attach one file naturally
- long-running report/research turns no longer require custom polling loops
- status responses carry enough machine-readable hints to decide whether to wait, patch, or retry

### 3. Documented the new contract

Changed:

- `docs/contract_v1.md`
- `docs/runbook.md`
- `skills-src/chatgptrest-call/SKILL.md`

Effect:

- the canonical public MCP tool set is now documented as:
  - `advisor_agent_turn`
  - `advisor_agent_status`
  - `advisor_agent_cancel`
  - `advisor_agent_wait`

## Test path

Ran:

```bash
./.venv/bin/pytest -q tests/test_task_intake.py tests/test_routes_agent_v3.py
./.venv/bin/pytest -q tests/test_agent_mcp.py tests/test_public_agent_mcp_validation.py
./.venv/bin/pytest -q tests/test_task_intake.py tests/test_routes_agent_v3.py tests/test_agent_mcp.py tests/test_public_agent_mcp_validation.py
```

## Residual risk

- `task_intake` is a high-blast-radius normalizer, so the fix stayed narrow: attachment summary and repo-note derivation only.
- Existing caller-supplied raw `task_intake.available_inputs` is still respected. This package only changes the auto-derived path.
