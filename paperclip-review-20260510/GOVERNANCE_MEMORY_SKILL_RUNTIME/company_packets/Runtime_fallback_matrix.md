# Runtime Fallback Matrix

Generated: `2026-05-10T08:27:22+08:00`

Runtime capability is not proven by `--help`, binary presence, or interpreter version. Valid runtime proof must show task execution, artifact creation, readback, and fail-closed behavior.

| Runtime | Status | Routing rule |
| --- | --- | --- |
| codex2 | active controller lane | Use for current repo execution, validation and final integration. |
| codex1 | controller/architecture candidate | Useful where existing lane has capability; do not assume connector parity with Codex2. |
| claudekimi | bounded orchestration candidate | Use for long-chain research with explicit contracts and evidence artifacts. |
| claudeds | coding fallback | Fallback only after task contract and evidence path are defined. |
| claudeminmax | low-risk automation candidate | Quarantined provider restrictions still apply to MiniMax provider use. |
| Kimi Code ACP | candidate | Read-only/smoke before any production promotion. |
| Pro/Gemini | advisor-only | Second opinion; never final judge and not a blocker for local pass. |
| claudemi/claudegac | out_of_pool | Credits exhausted; not in effective runtime pool. |
| MiniMax/DeepSeek/Tavily/Brave | quarantined_or_no_production_use | Do not call; provider key rotation is not in current goal. |

Fallback policy:

- Controller stays on Codex2 unless a bounded task contract justifies another runtime.
- Runtime lab may test adapters, fixtures and validators, but Governance owns promotion decisions.
- Failed/cancelled runs cannot be accepted evidence.
