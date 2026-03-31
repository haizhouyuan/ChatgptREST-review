# 2026-03-25 Public Agent MCP Client Surface Fixup v1

## Summary

This change closes the most actionable service-side gaps from the 2026-03-25 public advisor-agent MCP client experience pack:

1. single-file `attachments` no longer require list-only transport at the public MCP boundary
2. long-running sync turns now expose a clearer deferred/background handoff contract
3. public MCP now exposes a first-class `advisor_agent_wait(session_id, timeout_seconds)` primitive
4. long-running status responses now include explicit `recommended_client_action`, `wait_tool`, and `progress`
5. auto-derived attachment grounding no longer leaks local absolute file paths into prompt-visible `available_inputs`

## What Changed

### 1. Attachment prompt sanitization

Canonical `task_intake` auto-derivation now builds an `attachment_inventory` summary from attached files:

- `available_inputs.files` uses sanitized display labels instead of raw local absolute paths
- repo context is inferred from git when possible and emitted as prompt-visible notes
- repo URL and branch metadata are carried in `task_intake.context.attachment_inventory`
- an explicit note now tells the downstream model that files were provided via service-side upload, not readable local links

This keeps provider-owned uploads on `input.file_paths`, while stopping prompt-visible local workstation paths from misleading ChatGPT Web.

### 2. Public MCP handoff and wait

The public MCP surface now:

- accepts `attachments` as either `string` or `list[string]`
- returns `accepted_for_background`, `why_sync_was_not_possible`, `recommended_client_action`, `wait_supported`, `wait_tool`, and `progress`
- exposes `advisor_agent_wait(session_id, timeout_seconds)` for terminal-result waiting without ad hoc polling loops

### 3. Docs and skill alignment

Updated docs:

- `docs/contract_v1.md`
- `docs/runbook.md`
- `skills-src/chatgptrest-call/SKILL.md`

These now document the canonical public MCP tool set and the new attachment/wait semantics.

## Validation

Targeted tests passed:

- `tests/test_task_intake.py`
- `tests/test_routes_agent_v3.py`
- `tests/test_agent_mcp.py`
- `tests/test_public_agent_mcp_validation.py`

## Scope Notes

- This change intentionally avoided altering low-level job transport semantics.
- The main behavior change is northbound: prompt-visible attachment summaries, public MCP ergonomics, and explicit long-turn handoff.
