# OpenMind Telemetry

Telemetry bridge for OpenClaw lifecycle and tool events.

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
