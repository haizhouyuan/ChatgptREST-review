## Walkthrough

### Why a separate validation pack was added

The earlier validation layers already covered:

- public MCP transport
- public auth / trace gate
- scoped release / launch candidate gates

What was still missing was a dedicated pack for the new contract-first behavior itself:

- structured `task_intake`
- same-session `contract_patch`
- parser fallback
- clarify diagnostics
- northbound observability

### Why this pack is route-level, not provider-level

The purpose here is to validate public-agent control-plane semantics. External provider health is already covered elsewhere and is intentionally not a dependency for this pack.

That is why the runner uses a fake controller with the real `/v3/agent/turn` route logic.

### Why parser fallback is still included

Explicit `task_intake` is now the preferred path, but coding-agent clients will still send message-heavy requests. The parser is a fallback, so it needs its own regression guard.

### Why observability is part of validation

Northbound observability is not just telemetry. It is part of the contract for coding agents:

- what execution profile was requested
- what actually ran
- why clarify triggered
- what contract patch should be sent next

Without validating these fields, the surface is still not reliable enough to act as a single northbound interface.
