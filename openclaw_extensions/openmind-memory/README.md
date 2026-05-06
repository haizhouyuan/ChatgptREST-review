# OpenMind Memory

OpenClaw memory-slot bridge plugin backed by ChatgptREST memory services.

Canonical current-state docs:

- `docs/contracts/ADR-005-openmind-openclaw-chatgptrest-authority-boundary-v1.md`
- `docs/integrations/2026-04-09_openclaw_cognitive_substrate_runtime_contract_v4.md`
- `docs/contracts/2026-04-09_openmind_scope_surface_inventory_v2.md`

The memory slot is intentionally hot-path oriented:

- recall defaults to `memory + knowledge + graph + policy`
- durable capture goes to `POST /v2/memory/capture`
- graph detail still respects `graphScopes`

Lifecycle hooks:

- `before_agent_start` -> `POST /v2/context/resolve`
- `agent_end` -> `POST /v2/memory/capture`

Manual tools:

- `openmind_memory_recall`
- `openmind_memory_capture`
- `openmind_memory_status`

Identity forwarding:

- `sessionKey -> session_key`
- `sessionId -> thread_id`
- `agentId -> agent_id`
- `agentAccountId -> account_id`

When OpenClaw runtime context provides these fields, the plugin forwards them to
`/v2/context/resolve` and `/v2/memory/capture` so recall and capture stay tied to
the active conversation identity instead of degrading to anonymous substrate reads.

Hot-path recall behavior:

- default context resolve requests `memory`, `knowledge`, `graph`, and `policy`
- `graph_scopes` is only sent when graph retrieval is requested
- degraded repo/personal graph semantics are still surfaced by `/v2/context/resolve`

Role forwarding:

- manual tools accept optional `roleId`
- plugin config accepts optional `defaultRoleId`

`roleId` is forwarded as `role_id` so `devops` / `research` role packs can
start accumulating isolated memory from day 1 without changing component
identity (`source.agent` stays as the emitter such as `openclaw` or `advisor`).
