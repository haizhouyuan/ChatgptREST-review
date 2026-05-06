# Live Deep Research Finality Gate Duplicate-Guard Fix Walkthrough V1

Date: 2026-04-08

## What changed

This patch corrected a false-failure mode in the live Deep Research finality gate.

Two changes landed together:

1. `coding-agent-v1` now preserves structured duplicate-guard failure details projected from the broad advisor lane.
2. the live gate runner now appends a unique `gate_run_id` suffix to the sample message so it does not collide with other in-flight heavy public-agent turns that reuse the same base prompt.

## Why this was necessary

The first live gate attempts failed for the wrong reason:

- the prompt used by the gate was fixed
- the public agent duplicate guard correctly blocked repeated heavy turns
- `coding_agent_turn` narrowed the payload but dropped `error`, `hint`, and `existing_session_id`
- the gate only saw `ok=false` with an empty status surface and could not distinguish a real contract failure from a duplicate-guard collision

That made the live gate noisy and non-diagnostic.

## Implementation

Updated:

- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py)
- [run_live_deep_research_finality_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_live_deep_research_finality_gate.py)
- [test_agent_mcp.py](/vol1/1000/projects/ChatgptREST/tests/test_agent_mcp.py)
- [test_live_deep_research_finality_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_live_deep_research_finality_gate.py)

The coding-agent projection now carries:

- `error`
- `error_type`
- `hint`
- `reason`
- `status_code`
- `recoverable`
- `detail`
- `existing_session_id`

For `duplicate_public_agent_session_in_progress`, the narrow lane also rewrites the next action to:

- `tool = coding_agent_wait`
- `session_id = existing_session_id`

The live runner now sends:

- the same semantic prompt body
- plus a unique `[gate_run_id: <stamp>]` suffix

This keeps the gate on the intended `deep_research` lane while avoiding false duplicate collisions from earlier runs.

## Validation

Targeted tests now cover:

- coding-agent duplicate-error projection
- unique gate-run tag injection
- existing live-gate happy/provisional/short-answer cases

At the live runtime level, the latest rerun proved that:

- `coding_agent_turn` is accepted
- the session route is `deep_research`
- provisional status remains `answer_ready=false`

The full finality proof remained in progress at the time of this sub-change and is tracked as the remaining part of H.

## Outcome

This patch does not mark H complete by itself.

It removes a false blocker so that the remaining live finality gate now measures the real end-to-end Deep Research behavior instead of duplicate-guard collisions.
