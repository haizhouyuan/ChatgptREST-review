# 2026-03-23 Public Agent Thinking Heavy Execution Profile v1

## Summary

Added a high-level `execution_profile=thinking_heavy` path to the public agent surface so coding agents can request faster premium analysis without bypassing the low-level `/v1/jobs chatgpt_web.ask` guard.

## Why

`thinking_heavy` is a supported ChatgptREST preset, but public `/v3/agent/turn` previously only mapped:

- `deep_research` → `deep_research`
- `report` → `pro_extended`
- `funnel/build_feature` → `thinking_heavy`

That left no legal high-level path for “fast premium analysis with some websearch support, but not deep research.” The wrong workaround would have been to allow low-level direct live `chatgpt_web.ask` submission for coding agents.

## What Changed

- `TaskIntakeSpec` now accepts `execution_profile`
- `build_task_intake_spec(...)` accepts:
  - explicit `execution_profile`
  - compatibility alias `depth=heavy|thinking_heavy`
- research scenario packs now respect `execution_profile=thinking_heavy`
  - `topic_research` / `comparative_research` switch from `deep_research` to `analysis_heavy`
- strategist now treats `analysis_heavy` as a premium reasoning lane
- `/v3/agent/turn` route mapping now includes:
  - `analysis_heavy` → `preset=thinking_heavy`
- public MCP `advisor_agent_turn` now forwards `execution_profile`

## Boundary

- This does **not** open low-level `/v1/jobs chatgpt_web.ask` direct submission.
- This does **not** redefine `thinking_heavy` as a `deep_research` substitute.
- This does **not** convert `research_report` into a `thinking_heavy` route by default.

## Verification

- `./.venv/bin/pytest -q tests/test_task_intake.py tests/test_ask_strategist.py tests/test_routes_agent_v3.py tests/test_agent_mcp.py`
- `python3 -m py_compile chatgptrest/advisor/task_intake.py chatgptrest/advisor/scenario_packs.py chatgptrest/advisor/ask_strategist.py chatgptrest/api/routes_agent_v3.py chatgptrest/mcp/agent_mcp.py chatgptrest/mcp/server.py`
- `PYTHONPATH=. ./.venv/bin/python ops/run_public_agent_mcp_validation.py`
