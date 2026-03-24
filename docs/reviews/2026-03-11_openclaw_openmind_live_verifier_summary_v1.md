# 2026-03-11 OpenClaw OpenMind Live Verifier Summary v1

## Run

- Timestamp UTC: `2026-03-11T11:39:09.898927+00:00`
- Command: `./.venv/bin/python ops/verify_openclaw_openmind_stack.py --output-dir /tmp/chatgptrest_openclaw_verify_20260311 --timeout-seconds 180`
- Raw artifacts:
  - Markdown: `/tmp/chatgptrest_openclaw_verify_20260311/verify_openclaw_openmind_stack.md`
  - JSON: `/tmp/chatgptrest_openclaw_verify_20260311/verify_openclaw_openmind_stack.json`

## Summary

- Result: **FAIL**
- Failed checks: **23 / 47**
- Topology, gateway loopback bind, gateway token mode, and OpenMind tool exposure still passed.
- The failing part is the actual OpenMind tool/memory/runtime behavior, not just packaging or topology.

## Key Failed Checks

- `openmind_probe_reply`
- `openmind_tool_round`
- `memory_capture_probe_reply`
- `memory_capture_tool_round`
- `memory_capture_recorded`
- `memory_recall_probe_reply`
- `memory_recall_tool_round`
- `memory_recall_captured_block`
- `memory_recall_marker_present`
- `role_capture_probe_reply`
- `role_capture_tool_round`
- `role_capture_recorded`
- `role_devops_recall_probe_reply`
- `role_devops_recall_tool_round`
- `role_devops_recall_marker_present`
- `role_devops_recall_scoped`
- `role_research_recall_probe_reply`
- `role_research_recall_tool_round`
- `role_research_recall_scoped`
- `main_sessions_spawn_runtime_denied`
- `main_sessions_spawn_negative_probe`
- `main_subagents_runtime_denied`
- `main_subagents_negative_probe`

## Observed Failure Pattern

- The runtime frequently returned generic conversational text instead of the expected tool-mediated reply.
- The verifier repeatedly reported `missing user marker in transcript`, which means the expected probe turn could not be matched back to a clean transcript/tool round.
- Memory capture/recall and role-scoped recall no longer produced the expected recorded evidence objects.

Representative lines from the raw verifier markdown:

- `openmind_probe_reply`: generic conversational fallback instead of expected probe token handling.
- `openmind_tool_round`: `missing user marker in transcript`
- `memory_capture_recorded`: `{}`
- `role_devops_recall_scoped`: `{}`
- `main_sessions_spawn_runtime_denied`: generic conversational fallback instead of a denied-runtime signal.

## Interpretation

This is a real runtime regression or drift relative to the previously passing `2026-03-10` verifier baseline in [openclaw_openmind_verifier_lean_20260310.md](/vol1/1000/projects/ChatgptREST/docs/reviews/openclaw_openmind_verifier_lean_20260310.md).

The exact root cause still needs isolation, but the live evidence already shows that the current runtime is not stable enough for production launch.
