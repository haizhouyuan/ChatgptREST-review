# 2026-03-10 OpenClaw/OpenMind Verifier Fallback-Aware Round Detection

## Context
- Full `pytest -q -x` passed on current HEAD.
- Live `lean` verifier still reported false negatives for:
  - `openmind_tool_round`
  - `memory_capture_tool_round`
  - `memory_recall_tool_round`
  - negative probes for `sessions_spawn` / `subagents`
- Runtime transcript inspection showed the tool rounds were actually present.

## Root Cause
The OpenClaw live transcript on this host includes provider fallback turns:
1. original probe user message
2. upstream `openai-codex` failure message
3. injected user bridge: `Continue where you left off. The previous model attempt failed or timed out.`
4. `google-gemini-cli` continues and performs the real tool call / tool result / final reply

The verifier previously stopped scanning as soon as it saw the bridge user message, so it never reached the actual tool round. It also assumed the latest matching marker belonged to the desired tool round, which breaks when capture/recall share the same marker.

## What Changed
- `inspect_tool_round()` now:
  - ignores provider-fallback bridge user turns
  - searches multiple matching user anchors from newest to oldest until it finds the round whose `tool_name + assistant_reply` actually match
- `inspect_unavailable_tool_round()` now applies the same fallback-aware anchor logic
- Added regression coverage for:
  - fallback bridge user between failed model and successful tool round
  - repeated marker reuse across capture/recall turns
  - bridge sentence embedded inside `<openmind-context>`

## Validation
- `./.venv/bin/pytest -q tests/test_verify_openclaw_openmind_stack.py`
- `./.venv/bin/python -m py_compile ops/verify_openclaw_openmind_stack.py tests/test_verify_openclaw_openmind_stack.py`
- Manual transcript replay against live state showed all five probes classify correctly after the patch
- live verifier rerun was started after the fix
