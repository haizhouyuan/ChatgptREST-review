---
name: planning-openmind-bridge
description: Legacy bridge skill kept for historical compatibility. Hermes-native workbench is now the default front surface; do not treat this bridge as the canonical path for new work.
version: 1.0.0
author: Codex
platforms: [linux]
required_environment_variables:
  - name: OPENMIND_API_KEY
    prompt: OpenMind API key
    help: Inject from the current runtime secret source; do not hardcode into the repo.
    required_for: hot-path HTTP calls and fail-closed memory capture
metadata:
  hermes:
    category: planning
    tags: [planning, chatgptrest, bridge, memory, mcp]
    requires_toolsets: [terminal]
    gateway_direct_handler_script: scripts/direct_gateway_bridge.py
---

# planning-openmind-bridge

## When to Use

This skill is now **legacy-only**.

Use it only when you are explicitly auditing or replaying historical bridge behavior.

For new work:

- use `hermes-workbench` as the front surface
- use ChatgptREST only as automation backend
- do not reintroduce `advisor_agent_turn` as the default front-door

Typical triggers:

- planning memo
- report rewrite
- research diagnosis
- tasks that need planning shared cognition before drafting
- tasks that must write memory only after a completed, high-reuse result

Do not use this skill for generic chatting, casual coding, or any task outside the three fixed first-stage templates.

## Purpose

This skill standardizes the bridge between `Hermesagent` and `ChatgptREST` for planning-class tasks.

It remains a repo-managed historical bridge package, but it is **not** the primary path anymore.

## Frozen Boundaries

1. Hot path uses `HTTP` against `127.0.0.1:18711`
2. Historical slow path used `MCP` against `127.0.0.1:18712/mcp`
3. First stage only allowed three fixed `TaskIntake` templates:
   - `planning_memo`
   - `report_rewrite`
   - `research_diagnosis`
4. `memory.capture` is fail-closed
5. Secrets must come from runtime environment only

## Package Layout

This skill is backed by repo-managed scripts and templates.

Use the bundled files under:

- `scripts/validate_bridge_env.py`
- `scripts/pre_task_context_resolve.py`
- `scripts/pre_task_graph_query.py`
- `scripts/slow_path_advisor_turn.py`
- `scripts/post_task_memory_capture.py`
- `templates/task_intake_examples.json`
- `templates/acceptance_cases.md`

Do not replace them with ad hoc inline curl unless a script is clearly broken and you are explicitly diagnosing that script.

## Procedure

Do **not** treat this as the default planning workflow anymore.

Only run the bridge workflow when the task explicitly says to inspect or replay legacy bridge behavior.

1. Run `scripts/validate_bridge_env.py`.
   If it fails, stop and surface the exact missing runtime fact. Do not continue with a native-Hermes-only answer.
2. Classify the request into exactly one fixed template:
   - `planning_memo`
   - `report_rewrite`
   - `research_diagnosis`
3. Run `scripts/pre_task_context_resolve.py` to fetch planning shared cognition over the hot path.
4. If you need graph lineage or repo/issue context, run `scripts/pre_task_graph_query.py` over the hot path.
5. Run `scripts/slow_path_advisor_turn.py` with the chosen template to execute the heavy planning turn over MCP.
6. Draft the answer from the bridge output, not from free-form local tool use alone.
7. Only consider `scripts/post_task_memory_capture.py` after the task is both:
   - completed
   - high-reuse

If those gates are not satisfied, keep capture closed.

For ordinary planning-family tasks, prefer Hermes-native workbench and local task-state handling instead of reviving this bridge.

## Runtime Inputs

Expected environment variables:

- `CHATGPTREST_API_BASE` (default: `http://127.0.0.1:18711`)
- `CHATGPTREST_MCP_BASE` (default: `http://127.0.0.1:18712`)
- `OPENMIND_API_KEY` (required for hot-path `/v2/*` calls)

Hot-path endpoints:

- `POST /v2/context/resolve`
- `POST /v2/graph/query`

port `18711`, auth: `X-Api-Key`
Historical MCP endpoint: `http://127.0.0.1:18712/mcp`

Note:

- shared public MCP has since been narrowed to automation-only
- `advisor_agent_turn/status/wait/answer/cancel` are no longer the canonical public tool surface

## Implementation Rules

1. Do not hardcode any secret
2. Do not broaden `TaskIntake` dynamically in phase 2-3
3. Do not merge hot-path and slow-path logic into one script
4. Do not silently downgrade capture policy from fail-closed
5. Do not treat bridge-level success as Hermes end-to-end success

## Verification

Minimum acceptable verification:

1. `scripts/validate_bridge_env.py` passes
2. `scripts/pre_task_context_resolve.py` returns `200`
3. `scripts/pre_task_graph_query.py` returns `200` when graph lineage is requested
4. if you are explicitly replaying old bridge behavior, `scripts/slow_path_advisor_turn.py` can still produce evidence
5. `scripts/post_task_memory_capture.py` refuses write-back unless both gating flags are present

If any of the first four steps fail, report the bridge failure explicitly. Do not present a native-Hermes answer as if the bridge had succeeded.
