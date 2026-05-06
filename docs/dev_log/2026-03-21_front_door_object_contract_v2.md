# 2026-03-21 Front Door Object Contract v2

## 1. 为什么要出 v2

[2026-03-20_front_door_object_contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_object_contract_v1.md)
的主方向是对的，但在进入实现前还差 3 个 precision gap：

1. canonical `Task Intake Spec` 没强制 `spec_version`
2. `task_spec.py` 被写得像“已经是 live canonical schema”，但当前代码还没升级到该状态
3. source taxonomy 只收到了 enum，没把 legacy carrier 值映射冻结

这版只修精度，不推翻 v1 的主模型。

## 2. v2 主判断

以下判断继续成立：

- canonical front-door object 仍然是 `Task Intake Spec`
- `IntentEnvelope` 仍然是 ingress adapter envelope
- `StandardRequest` 仍然是 legacy adapter carrier
- `AskContract` 仍然是 derived reasoning view
- `AskStrategyPlan` 仍然是 downstream planning object

## 3. 关键修正

### 3.1 Canonical object 必须带版本号

从 v2 开始，canonical `Task Intake Spec` 必须显式带：

- `spec_version`

而且它不是建议字段，而是 required field。

原因：

- schema 演进需要可审计
- adapter 对账需要知道它产出的到底是哪一版 canonical object
- 后续 intake normalizer 落代码时，需要有稳定版本锚点

### 3.2 `task_spec.py` 的正确定位

v1 在表述上有点过强。更准确的口径是：

- [task_spec.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py)
  当前还不是 live canonical schema truth
- 它是 **Phase 1 目标 canonical schema module**
- 当前 live 代码里：
  - `AcceptanceSpec` 仍是旧三档
  - `TaskSpec` 字段集仍偏 runtime dispatch object

所以从现在开始，`task_spec.py` 的正确描述应该是：

- 目标承载 canonical front-door schema 的模块
- 但在代码实现完成前，不能把它表述成已经对齐 `Task Intake Spec v2`

### 3.3 Source taxonomy 必须补映射决议

v1 只给了 canonical enum：

- `openclaw`
- `feishu`
- `rest`
- `mcp`
- `cli`
- `cron`
- `repair`
- `unknown`

但当前 live carrier 里仍有 legacy 值：

- `codex`
- `api`
- `direct`

如果不冻结映射规则，adapter 层仍然会各自理解这些旧值。

## 4. Freeze 模型

前门对象链继续冻结为：

1. `IntentEnvelope`
2. `Task Intake Spec`
3. `AskContract`
4. `AskStrategyPlan`

但这里要加一条精确限制：

- 只有 `Task Intake Spec` 是 versioned canonical object
- 其他对象都不是 schema authority

## 5. `Task Intake Spec v2` 决议

### 5.1 Required fields

`Task Intake Spec v2` 严格 required：

- `spec_version`
- `source`
- `trace_id`
- `objective`
- `scenario`
- `output_shape`
- `acceptance`

### 5.2 Strongly preferred fields

- `session_id`
- `decision_to_support`
- `evidence_required`

### 5.3 解释

- `session_id`
  - continuity 很重要
  - 但允许首次进入时为空，由 front door 分配
- `decision_to_support`
  - 质量关键字段
  - 但当前仍允许通过 clarify gate 补齐
- `evidence_required`
  - `planning / research` 强依赖
  - 但 `quick_ask` 允许走轻量默认值

## 6. `task_spec.py` / `standard_entry.py` / `ask_contract.py` 的新口径

### 6.1 `task_spec.py`

正确口径：

- future canonical schema module
- not yet live-equivalent to `Task Intake Spec v2`

### 6.2 `standard_entry.py`

正确口径：

- legacy adapter / normalizer
- not canonical schema
- not to be expanded into a parallel object system

### 6.3 `ask_contract.py`

正确口径：

- derived reasoning view
- consumes `Task Intake Spec`
- cannot define front-door truth

## 7. Source taxonomy freeze

### 7.1 Canonical enum

canonical source enum 冻结为：

- `openclaw`
- `feishu`
- `rest`
- `mcp`
- `cli`
- `cron`
- `repair`
- `unknown`

### 7.2 Legacy-to-canonical mapping

| Legacy carrier value | Adapter decision rule | Canonical source |
|---|---|---|
| `feishu` | direct preserve | `feishu` |
| `mcp` | direct preserve | `mcp` |
| `rest` | direct preserve | `rest` |
| `cron` | direct preserve | `cron` |
| `repair` | direct preserve | `repair` |
| `codex` | if request arrived via OpenClaw runtime bridge / plugin context | `openclaw` |
| `codex` | otherwise local Codex / repo CLI invocation | `cli` |
| `api` | REST caller without stronger channel identity | `rest` |
| `direct` | unresolved direct caller without stronger identity | `unknown` |

### 7.3 Rule of precedence

当 legacy source 和 runtime context 冲突时，优先级冻结为：

1. explicit runtime channel identity
2. ingress lane identity
3. legacy source fallback

例如：

- source=`codex` + OpenClaw plugin/session context 存在 -> `openclaw`
- source=`codex` + 本地 CLI/agent task -> `cli`

## 8. Ingress precision

### 8.1 `/v3/agent/turn`

- 仍是 public live ask 正门
- 应逐步从 `message + top-level scattered fields` 收敛到 `task_intake`

### 8.2 `/v2/advisor/ask`

- 仍是 internal smart-execution ingress
- 必须通过同一 intake normalizer 产出 `Task Intake Spec v2`

### 8.3 OpenClaw bridge

- 当前 payload 仍保持兼容
- 但 adapter 产物必须是 versioned `Task Intake Spec`

## 9. 不接受的过度表述

从 v2 开始，不应再这样写：

1. “`task_spec.py` 已经是 canonical schema truth”
2. “canonical spec 可以没有 `spec_version`”
3. “source enum 只要列出来，legacy 值以后再说”

## 10. Freeze 决议

这版冻结以下精确口径：

- canonical object = versioned `Task Intake Spec`
- `spec_version` required
- `task_spec.py` = target canonical schema module, not current live-equivalent truth
- source taxonomy must include explicit legacy-to-canonical mapping

后续如需修订，必须出 `v3`，不能覆盖本文件。
