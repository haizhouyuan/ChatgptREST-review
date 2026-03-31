# 2026-03-21 Public vs Internal Ingress Payload Diff v1

## 1. 为什么单独写这份

`Phase 2` 最容易再次漂的地方，不是 route 名字，而是不同 ingress 继续偷偷长不同 payload 语义。

这份文档只冻结两件事：

1. public live ask front door 应该长什么样
2. internal graph/controller lanes 允许保留哪些差异

## 2. Public live ask

public live ask 正门仍然是：

- `/v3/agent/turn`

它现在接受的 canonicalized payload 口径是：

| Field group | Public ask expectation |
| --- | --- |
| transport | `message`, `session_id`, `user_id`, `trace_id`, `depth`, `timeout_seconds` |
| identity | `account_id`, `thread_id`, `agent_id`, `role_id` |
| payload carrier | optional `task_intake` |
| compatibility | optional top-level contract scatter fields |
| files | `attachments` |
| context | `context` |

本轮新增的关键点是：

- OpenClaw plugin 现在不再只发 thin body
- 它会显式带 versioned `task_intake`

## 3. Internal smart-execution ask

internal smart-execution lane 仍是：

- `/v2/advisor/ask`

它与 public ask 的差异是：

| Aspect | `/v3/agent/turn` | `/v2/advisor/ask` |
| --- | --- | --- |
| primary text field | `message` | `question` |
| route semantics | public live ask dispatch | internal smart-execution |
| canonical intake | yes | yes |
| top-level hints | `goal_hint` | `intent_hint` |
| contract derivation | `AskContract / strategist / prompt compile` | route mapping + controller ask |

这条 lane 在 payload 层已经能和 public ask 对齐到同一份 `Task Intake Spec v2`。

## 4. Internal graph/controller lane

internal graph/controller lane 仍是：

- `/v2/advisor/advise`

它和 public ask 的核心区别不是“有没有 canonical intake”，而是 execution semantics：

| Aspect | `/v3/agent/turn` | `/v2/advisor/advise` |
| --- | --- | --- |
| role | public ask front door | graph/controller ingress |
| primary text field | `message` | `message` |
| canonical intake | yes | yes after Phase 2 |
| downstream | ask strategist / direct dispatch / controller | controller.advise graph path |
| channel caller | OpenClaw/public agent callers | Feishu WS |

本轮之后，`/v2/advisor/advise` 虽然没迁路由，但 payload 已经补齐：

- `source`
- `task_intake`
- `request_metadata.task_intake`
- `context.task_intake`

## 5. Feishu WS 的特殊性

Feishu WS 现在是 internal controller lane，不是 public ask lane。

因此它允许保留这些差异：

- route 仍然是 `/v2/advisor/advise`
- top-level body 仍保留 chat/channel 身份字段
- graph/controller 行为仍归 `advise`

但它不再允许的事是：

- 不带 `source`
- 不带 versioned `task_intake`
- 只靠 server 从 `message/thread_id/agent_id` 猜完整任务语义

## 6. OpenClaw plugin 的特殊性

OpenClaw plugin 已经固定到 public front door：

- route = `/v3/agent/turn`

它现在保留的特性是 OpenClaw runtime identity：

- `session_key`
- `account_id`
- `thread_id`
- `agent_id`

但它不再只是一个 thin bridge；这轮后它已经是 canonical payload adapter。

## 7. 冻结结论

从现在开始，payload 层的正式分工应写成：

- public ask:
  - route = `/v3/agent/turn`
  - contract = transport fields + optional explicit `task_intake`
- internal smart-execution:
  - route = `/v2/advisor/ask`
  - contract = question-based body + optional explicit `task_intake`
- internal graph/controller:
  - route = `/v2/advisor/advise`
  - contract = message-based body + explicit `task_intake` for aligned callers

legacy 差异仍然存在，但不再允许继续扩大成新的 canonical surface。
