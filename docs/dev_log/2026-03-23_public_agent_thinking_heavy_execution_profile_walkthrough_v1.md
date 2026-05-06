# 2026-03-23 Public Agent Thinking Heavy Execution Profile Walkthrough v1

## Why This Was The Right Fix

The issue was not that `thinking_heavy` was unsupported. The issue was that public coding-agent ingress had no first-class contract for it, so users were forced toward either:

- `deep_research`, which is too slow and evidence-heavy for many fast analysis asks
- or low-level direct `chatgpt_web.ask`, which is intentionally blocked for coding agents

The fix therefore belongs in the public agent contract and route policy, not in the low-level write guard.

## Implementation Notes

1. Extended canonical front-door intake with `execution_profile`.
2. Added compatibility handling for `depth=heavy`.
3. Routed research packs with `execution_profile=thinking_heavy` into a dedicated high-level route:
   - `analysis_heavy`
4. Mapped `analysis_heavy` to `preset=thinking_heavy` in `/v3/agent/turn`.
5. Forwarded the new field through public MCP so other Codex clients can use it without dropping to REST.

## Result

Coding agents now have a legal, high-level way to say:

“Give me a fast premium analysis lane with some websearch support, but do not send this to long-running deep research.”
