# 2026-03-25 public-agent enforcement followthrough v1

## Goal

Close the remaining gap where coding agents could still reach low-level ChatgptREST ask paths by habit, stale wrapper guidance, or repo-local helper code.

Target policy:

- Coding agents default to the public advisor-agent MCP at `http://127.0.0.1:18712/mcp`
- Coding agents must not treat low-level `/v1/jobs kind=*web.ask` as a normal entrypoint
- Coding agents must not treat direct `/v3/agent/turn` as their default client surface
- Any remaining low-level path must be explicit maintenance or non-agent pipeline usage

## What changed

### ChatgptREST

Commits:

- `97d25a8 guard: block coding-agent low-level web ask paths`
- `78454e9 policy: gate legacy wrapper jobs for maintenance only`

Main changes:

- Added coding-agent low-level ask blocking for `gemini_web.ask` and `qwen_web.ask` in addition to the existing direct live ChatGPT guard.
- Changed the repo wrapper `skills-src/chatgptrest-call/scripts/chatgptrest_call.py` so `--no-agent` is no longer enough by itself.
- Legacy wrapper mode now requires `--maintenance-legacy-jobs`.
- Legacy wrapper mode now stamps `CHATGPTREST_CLIENT_NAME=chatgptrestctl-maint` for auditability.
- Updated wrapper tests and the public-MCP config checker to enforce the maintenance gate.
- Updated `AGENTS.md`, `docs/runbook.md`, `docs/contract_v1.md`, `docs/client_projects_registry.md`, the skill body, and the skill agent metadata so public advisor-agent MCP is the only default agent path taught by repo docs.

### finagent

Commit:

- `eb29766 policy: route finagent agents through public mcp`

Main changes:

- Reworked `finagent/llm_adapter.py` so the `chatgptrest` backend now calls the public advisor-agent MCP tool `advisor_agent_turn` instead of posting directly to `/v3/agent/turn`.
- Added local blocking in `finagent/event_extraction.py` so coding-agent style client names cannot submit low-level `/v1/jobs kind=*web.ask` requests through the extraction client.
- Updated `finagent/graph/discovery.py` to reuse the public-MCP-backed adapter instead of the stale `/api/ask` flow.
- Updated CLI/help text and the extraction runner default client name to keep low-level jobs scoped to non-agent extraction flows.
- Added tests for the public MCP adapter path and the low-level extraction guard.

### openclaw

Commit:

- `c01d655fc docs: align chatgptrest agent entrypoints`

Main changes:

- Updated `AGENTS.md` and `docs/chatgptREST.md` so OpenClaw agents are pointed at the public advisor-agent MCP first.
- Removed stale examples that made low-level wrapper usage look normal.
- Documented that maintenance-only legacy wrapper usage must carry the maintenance gate.

## Verification

### ChatgptREST

- `python3 -m py_compile chatgptrest/api/write_guards.py chatgptrest/api/routes_jobs.py chatgptrest/eval/direct_provider_execution_gate.py`
- `./.venv/bin/pytest -q tests/test_block_smoketest_prefix.py tests/test_direct_provider_execution_gate.py`
- `python3 -m py_compile skills-src/chatgptrest-call/scripts/chatgptrest_call.py ops/check_public_mcp_client_configs.py`
- `./.venv/bin/pytest -q tests/test_skill_chatgptrest_call.py tests/test_check_public_mcp_client_configs.py`
- `gitnexus_detect_changes(scope=\"staged\")` before each ChatgptREST commit

### finagent

- `python3 -m py_compile finagent/llm_adapter.py finagent/event_extraction.py finagent/graph/discovery.py finagent/cli_research.py scripts/run_event_extraction_chatgptrest.py`
- `PYTHONPATH=. pytest -q tests/test_llm_adapter.py tests/test_event_extraction.py`

### openclaw

- `git diff --check -- AGENTS.md docs/chatgptREST.md`
- Narrow search over `src/`, `scripts/`, and `extensions/` found no live OpenClaw code paths directly calling ChatgptREST low-level ask or `/v3/agent/turn`.

## Remaining boundary

- finagent still keeps low-level `/v1/jobs` for the event extraction pipeline, but it is now explicitly non-agent and guarded by client-name policy.
- ChatgptREST still exposes `/v3/agent/*` for backend ingress and internal runtime paths, but repo policy and client-facing docs now keep coding agents on the public MCP surface.
