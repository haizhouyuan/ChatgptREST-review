# 2026-03-20 Entry Adapter Matrix v1

## 1. 目的

这份矩阵定义各入口如何映射到 canonical `Task Intake Spec`。

它不是入口 inventory 文档，而是 adapter contract 文档。

## 2. Canonical target

所有入口最终都必须归一到：

- [2026-03-20_task_intake_spec_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_task_intake_spec_v1.json)

## 3. Adapter matrix

| Entry | Current endpoint / code | Current payload shape | Adapter output | 现状判断 | 下一步 |
|---|---|---|---|---|---|
| OpenClaw plugin | [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts) | `question, goalHint, roleId, sessionId, context, depth` | `Task Intake Spec` with `source=openclaw`, `ingress_lane=agent_v3` | live, but still thin | 明确构造 `task_intake` |
| Public agent facade | [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py) | `message + session/context + scattered contract fields` | `Task Intake Spec` then derived `AskContract` | live primary front door | 限制顶层散字段继续增长 |
| Internal advisor ask | [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py) | `question, intent_hint, context, file_paths` | `Task Intake Spec` with adapter-derived `scenario/evidence/acceptance` | live internal ingress | 和 `agent_v3` 共享同一 normalizer |
| Feishu WS | [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py) | event/callback payload, then `/v2/advisor/advise` | `Task Intake Spec` with `source=feishu`, `ingress_lane=advisor_advise_v2` | live, but not yet canonical ask lane | 保 route，先补 adapter |
| MCP tooling | [mcp/server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py) | tool-specific params | `Task Intake Spec` via `question/message -> objective` | mixed internal callers | 统一经 same intake normalizer |
| CLI | [cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py) | command flags + message | `Task Intake Spec` | mixed internal callers | 限定新实现走 shared adapter |
| Legacy advise v1 | [routes_advisor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py) | legacy body | compatibility-only mapping | residual lane | 禁止新 caller 扩张 |

## 4. Field-level mapping

### 4.1 OpenClaw plugin

Current:

- `question` -> raw user task
- `goalHint` -> route hint
- `roleId` -> target role pack
- `sessionId` -> continuity
- `context` -> merged runtime context

Required mapping:

- `question` -> `objective` candidate
- `goalHint` -> `goal_hint`
- `roleId` -> `role_id`
- `sessionId` -> `session_id`
- `context.files` -> `available_inputs.files` and `attachments`
- `context.session_key` -> `context.session_key`

### 4.2 `/v3/agent/turn`

Current:

- `message`
- `session_id`
- `trace_id`
- `goal_hint`
- `context`
- optional free-form contract-like top-level fields

Required mapping:

- `message` -> raw user request
- `task_intake.objective` -> canonical objective
- `task_intake.*` -> canonical intake
- `contract` -> optional override / derived compatibility view only

### 4.3 `/v2/advisor/ask`

Current:

- `question`
- `intent_hint`
- `context`
- `file_paths`
- `session_id`
- `role_id`

Required mapping:

- `question` -> `objective`
- `intent_hint` -> `scenario` candidate
- `file_paths` -> `attachments` and `available_inputs.files`
- `context` -> `context`

## 5. Derived object rules

### 5.1 `AskContract`

Must be derived from `Task Intake Spec` with this minimum mapping:

- `objective` <- `objective`
- `decision_to_support` <- `decision_to_support`
- `audience` <- `audience`
- `constraints` <- `constraints`
- `available_inputs` <- summarized `available_inputs`
- `missing_inputs` <- summarized `missing_inputs`
- `output_shape` <- `output_shape`

### 5.2 `AskStrategyPlan`

Must not consume raw ingress body directly.

Allowed input:

- `AskContract`
- selected route / goal hint
- normalized context

## 6. Freeze decisions

### 6.1 Allowed

- adapter-specific metadata in `context`
- compatibility adapters that continue to accept old payloads
- temporary top-level compatibility fields in `/v3/agent/turn`

### 6.2 Not allowed

- new ingress inventing a parallel task schema
- adding more contract-like top-level fields to `/v3/agent/turn`
- `standard_entry.py` growing into a second canonical object system

## 7. Implementation order

1. shared intake normalizer
2. `agent_v3` adapter path
3. `advisor_ask_v2` adapter path
4. OpenClaw plugin payload upgrade
5. Feishu WS adapter alignment

## 8. Exit criteria

- Same user request entering through OpenClaw and `/v3/agent/turn` yields semantically equivalent `Task Intake Spec`
- `AskContract` no longer needs caller-specific rescue synthesis outside the shared normalizer
- legacy lanes remain compatible but stop defining new semantics
