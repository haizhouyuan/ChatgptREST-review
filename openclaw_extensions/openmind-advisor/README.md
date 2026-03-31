# OpenMind Advisor

Slow-path OpenClaw plugin for OpenMind advisor tasks.

Primary tool:

- `openmind_advisor_ask`

Recommended use:

- research
- report drafting
- funnel critique
- structured planning
- code review

This plugin calls the public agent facade endpoint:

- `POST /v3/agent/turn`

The plugin handles the complete agent turn lifecycle internally, including:

- Session continuity via `session_id`
- Automatic answer delivery (no manual wait/answer pagination needed)
- Provenance tracking (route, job_id, status)

Default behavior:

- plugin config uses `defaultGoalHint` for goal hint (code_review, research, image, report, repair)
- runtime `session_id` / `account_id` / `thread_id` / `agent_id` / `user_id`
  are forwarded to agent requests
- runtime identity is also merged into `context` so downstream routing can keep
  stable business context while ignoring volatile tracing fields

Tool parameters:

- `question`: Advisor question or task (required)
- `goalHint`: Goal hint - code_review, research, image, report, repair (optional)
- `roleId`: Explicit role pack (optional, e.g. devops or research)
- `sessionId`: Session ID for continuity (optional)
- `depth`: Execution depth - light, standard, deep (optional, default: standard)
- `timeoutSeconds`: Timeout in seconds (optional, default: 300)
- `context`: Additional context dictionary (optional)

Response format:

The plugin returns agent-style responses with:

- `answer`: Final answer text
- `status`: Controller status (completed, in_progress, etc.)
- `route`: Selected execution route
- `provenance.job_id`: Underlying job ID
- `delivery.answer_chars`: Answer character count
- `next_action`: Recommended next action
- `recovery_status`: Recovery state if applicable

Backward compatibility:

- Tool name `openmind_advisor_ask` is preserved for compatibility
- Old `mode=ask/advise` parameters are deprecated; use `goalHint` instead

Role forwarding:

- tool calls accept optional `roleId`
- plugin config accepts optional `defaultRoleId`

When provided, `roleId` is forwarded as `role_id` so agent routing and
execution can run inside an explicit `devops` / `research` role context instead
of relying on implicit route hints.
