# 2026-03-20 Front Door Object Contract v1

## 1. 目的

这份文档用于冻结 ChatgptREST 当前前门对象模型。

它回答 3 个问题：

1. 哪个对象是 front door 的 canonical schema
2. 哪些对象只是 adapter / reasoning view
3. `OpenClaw / /v3/agent/turn / /v2/advisor/ask / Feishu WS` 应该如何对齐

这不是运行时实现文档，而是实施阶段的对象契约文档。

## 2. 核心结论

### 2.1 Canonical object

前门 canonical object 冻结为：

- `Task Intake Spec`

它是所有 ask ingress 在进入 route / clarify / planning / execution 之前必须收敛到的统一结构。

### 2.2 非 canonical 对象

以下对象继续存在，但不再与 `Task Intake Spec` 平权：

- `IntentEnvelope`
  - 作用：边缘入口归一化壳
  - 地位：adapter input envelope
- `StandardRequest`
  - 作用：旧 standard-entry pipeline 的 request carrier
  - 地位：legacy adapter object
- `AskContract`
  - 作用：premium ingress 的 reasoning / prompt / clarify view
  - 地位：derived reasoning view

### 2.3 主从关系

- `task_spec.py`
  - 保留为 canonical schema 所在地
- `standard_entry.py`
  - 降级为 adapter / normalizer
- `ask_contract.py`
  - 保留，但只能从 `Task Intake Spec` 派生，不能再作为平行 front-door truth

## 3. 为什么要这样收

当前代码里至少有 4 套近似对象：

- [IntentEnvelope / TaskSpec](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py)
- [StandardRequest](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py)
- [AskContract](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_contract.py)
- `/v3/agent/turn` body 中的 free-form fields
  - [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)

这些对象各自都在携带：

- 用户目标
- 输入材料
- 输出要求
- 缺失信息
- 约束
- route / provider hint

但字段命名、粒度和生命周期都不一致。

如果不先统一对象，后面的 `planning / research scenario pack` 仍会继续在不同入口上长不同语义。

## 4. Canonical Object Chain

前门对象链冻结成 4 层：

1. `IntentEnvelope`
2. `Task Intake Spec`
3. `AskContract`
4. `AskStrategyPlan`

### 4.1 IntentEnvelope

定位：

- 入口适配壳
- 只负责把不同 caller 的原始 payload 包进统一 envelope

边界：

- 允许保留 source-specific metadata
- 不负责最终 route 决策
- 不负责 acceptance 完整定义

### 4.2 Task Intake Spec

定位：

- front door canonical schema
- 所有 ingress 在进入 route / clarify / planning 之前的统一对象

边界：

- 包含 objective / decision / inputs / constraints / evidence / acceptance
- 必须足以支撑 `planning` 和 `research`
- 不直接承担 provider-specific prompt wording

### 4.3 AskContract

定位：

- Task Intake Spec 的 reasoning view
- 给 clarify / strategist / prompt builder / post-review 使用

边界：

- 只保留 premium ingress 需要的收敛字段
- 不能反向定义 canonical schema

### 4.4 AskStrategyPlan

定位：

- Strategist 针对 `AskContract` 产出的执行计划
- 属于 route / execution planning 层

边界：

- 不再直接吃各入口原始 body
- 必须只消费 canonical-derived contract

## 5. Canonical Task Intake Spec

### 5.1 Required core

`Task Intake Spec` 严格必备字段冻结为：

- `source`
- `trace_id`
- `objective`
- `output_shape`
- `scenario`
- `acceptance`

强烈建议字段：

- `session_id`
- `decision_to_support`

原因：

- `session_id` 对 continuity 很重要，但新 session 首次进入时允许为空，由 front door 分配
- `decision_to_support` 对质量至关重要，但当前系统仍保留 clarify gate，允许先进入再补齐

### 5.2 Recommended context

建议字段：

- `user_id`
- `account_id`
- `thread_id`
- `agent_id`
- `audience`
- `constraints`
- `available_inputs`
- `missing_inputs`
- `evidence_required`
- `attachments`
- `context`
- `goal_hint`
- `role_id`
- `priority`

### 5.3 Field semantics

#### `objective`

当前请求要产出的具体东西，不等于完整原话转抄。

#### `decision_to_support`

这份输出将支持哪个决定、动作、评审或下一步。

#### `output_shape`

输出形式，如：

- `brief_answer`
- `markdown_report`
- `planning_memo`
- `research_memo`
- `code_review_summary`
- `meeting_summary`

#### `available_inputs`

已存在的文件、历史背景、上下文和附件引用。

#### `missing_inputs`

当前已知缺的信息。可以为空，但不能为空含混。

#### `evidence_required`

证据要求，不再只靠 route 或 preset 猜。

建议最少包含：

- `level`
- `require_sources`
- `prefer_primary_sources`
- `ground_in_attached_files`
- `require_traceable_claims`

#### `acceptance`

验收定义。必须是结构化对象，而不是 prompt 附言。

最少包含：

- `profile`
- `required_sections`
- `required_artifacts`
- `min_evidence_items`
- `require_traceability`

## 6. 现有对象如何映射

### 6.1 IntentEnvelope → Task Intake Spec

[task_spec.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py) 里的 `IntentEnvelope` 应保留这些职责：

- `source`
- `user_id`
- `session_id`
- `raw_text`
- `attachments`
- source-specific metadata

但以下字段不该继续只停留在 envelope 层：

- `objective`
- `decision_to_support`
- `output_shape`
- `acceptance`

### 6.2 StandardRequest → adapter only

[standard_entry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py) 当前 `StandardRequest` 只够做轻量 request normalization：

- `question`
- `source`
- `trace_id`
- `target_agent`
- `preset`
- `file_paths`

它不具备：

- decision semantics
- acceptance semantics
- evidence semantics

所以它不能升级成 canonical schema，只能作为 adapter carrier。

### 6.3 AskContract ← derived view

[ask_contract.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_contract.py) 当前字段：

- `objective`
- `decision_to_support`
- `audience`
- `constraints`
- `available_inputs`
- `missing_inputs`
- `output_shape`
- `risk_class`
- `opportunity_cost`
- `task_template`

这些字段对 strategist/prompt/review 非常合适，但它缺：

- caller/session identity
- attachments / context shape
- structured acceptance
- structured evidence contract

所以它必须被定义成 `Task Intake Spec` 的 derived reasoning view。

## 7. Ingress contract decisions

### 7.1 `/v3/agent/turn`

当前事实：

- 公开 live ask 正门
- 实际直接接收 free-form body
- 还允许 body 顶层散落 `objective / decision_to_support / missing_inputs / output_shape`
  - [routes_agent_v3.py:1200+](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)

决策：

- `v3` 继续做公开正门
- 但其 request body 必须逐步收成：
  - `message`
  - `session_id`
  - `trace_id`
  - `context`
  - `task_intake`
  - `contract` 可保兼容，但降级成 derived override lane

### 7.2 `/v2/advisor/ask`

当前事实：

- internal smart-execution ingress
- 主要收 `question / intent_hint / context / file_paths`
  - [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)

决策：

- `v2/advisor/ask` 不另长自己的 schema
- 继续保 internal ingress 身份
- 内部归一时必须产出同一份 `Task Intake Spec`

### 7.3 OpenClaw bridge

当前事实：

- [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
  现在传的是：
  - `question`
  - `goalHint`
  - `roleId`
  - `sessionId`
  - `context`
  - `depth`

决策：

- OpenClaw 插件当前 payload 先保持兼容
- 下一阶段 adapter 输出必须显式构造 `task_intake`
- `question` 继续作为用户原始话术
- `task_intake.objective` 不再隐含等于 `question`

### 7.4 Feishu WS

当前事实：

- 仍通过 `/v2/advisor/advise`
- 当前更多是 graph/controller ingress，不是本轮 canonical ask object 主载体

决策：

- 本轮先不改路由
- 但 Feishu WS 产物在 ingress adapter 层必须能映射进同一份 `Task Intake Spec`

## 8. 反向约束

从这版开始，以下做法视为反模式：

1. 新入口直接发 free-form body 到 strategist，不经过 canonical object。
2. 继续在 `routes_agent_v3.py` 顶层新增更多 contract-like 散字段。
3. 把 `StandardRequest` 或 `AskContract` 当成 front-door truth。
4. 把 acceptance / evidence 继续写成 prompt 文本而不是结构化字段。

## 9. Phase 1 实施要求

### 9.1 代码收敛方向

- `task_spec.py`
  - 升级为 canonical schema module
- `standard_entry.py`
  - 改成 adapter/normalizer module
- `routes_agent_v3.py`
  - 增加 `task_intake` 消费路径
- `routes_advisor_v3.py`
  - 统一产出 canonical intake object

### 9.2 顺序

1. 先冻结 `task_intake_spec_v1.json`
2. 再做 `entry_adapter_matrix_v1`
3. 然后才进代码实现

## 10. Freeze 决议

这版冻结以下口径：

- canonical front-door object = `Task Intake Spec`
- `IntentEnvelope` = ingress adapter envelope
- `StandardRequest` = legacy adapter carrier
- `AskContract` = derived reasoning view
- `AskStrategyPlan` = downstream planning object

后续如需修订，必须出 `v2`，不能覆盖本文件。
