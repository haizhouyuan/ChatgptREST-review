# OpenMind Telemetry

Telemetry bridge plugin for OpenClaw lifecycle and tool events.

Canonical current-state docs:

- `docs/contracts/ADR-005-openmind-openclaw-chatgptrest-authority-boundary-v1.md`
- `docs/integrations/2026-04-09_openclaw_cognitive_substrate_runtime_contract_v4.md`
- `docs/contracts/2026-04-09_openmind_scope_surface_inventory_v2.md`

Hooks:

- `before_agent_start`
- `after_tool_call`
- `agent_end`
- `message_sent`

API target:

- `POST /v2/telemetry/ingest`

Notes:

- Emits `team.run.created` on agent start and keeps `tool.completed` / `tool.failed`
  plus `workflow.completed` / `workflow.failed` for run outcomes.
- Carries stable `run_id` / `task_ref` plus repo and agent identity into the
  existing OpenMind telemetry contract.
- `defaultRoleId` is optional and only decorates telemetry payloads; it does not
  auto-route runtime role selection.
