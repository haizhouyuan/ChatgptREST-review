# 2026-04-01 目标方向全量重读后再判断 v1

## 目的

这份文档不是再写一版“大愿景”，而是把以下三类材料压成下一阶段目标讨论可直接使用的口径：

1. 外部 best-practice source pack
2. 你已经写出的 harness 目标与实施计划
3. `ChatgptREST` 当前 repo/代码/运行态边界复盘材料

## 本轮冻结 mouthpiece

`ChatgptREST` 当前已经是多平面集成宿主；如果只谈“下一阶段最值得投资的目标”，最合理的主线不是继续扩 memory、executor 或新支线，而是先冻结 authority，再决定是否把其中一条真实主入口逐步收敛到高可信 `Task Harness Runtime`。在这之前，`opencli / CLI-Anything` 只保留为后置验证支线，不进入 primary milestone。

## 我对这批文档的独立判断

### 1. 目标其实已经很收敛，不是“没有目标”

从 Anthropic source pack 到你自己的 `v5 / v2` 文档，真正稳定收敛的目标只有几条：

- 要有明确任务控制链，而不是靠聊天上下文和随手 memory 推进任务
- durable truth 必须落在数据库/状态机，而不是文件系统
- generator 不能自证完成，必须有 skeptical evaluator/operator gate
- `completion_contract / canonical_answer` 与 durable memory 都必须成为真实 authoritative downstream integration
- 要有能持续运行的 acceptance/eval discipline

所以这轮不是“重新找目标”，而是“把已经很多次写出来的目标做减法”。

## 2. 最大问题不是目标错，而是目标包太大

`planning/docs/2026-03-31_Agent_Harness工程调研_最终综合结论_v5.md` 和 `planning/docs/2026-03-31_Agent_Harness全量实施计划与验收标准_v2.md` 的高层方向是对的，但它们天然会把多个层级的事情打包在一起：

- repo 身份问题
- harness runtime 主线问题
- evaluator / delivery / memory 的承重件
- opencli 硬化
- CLI-Anything 市场治理
- 大规模 acceptance/eval 平台建设

这些东西单看都“想要”，但一起推进就会重演“越做越乱”。

## 3. 当前 repo 现实决定了目标必须先经过边界裁剪

`ChatgptREST` 现在不是一个空白 harness 仓。按 2026-04-01 的现状冻结与代码核验，它已经同时承担：

- execution substrate
- advisor runtime
- public-agent governance facade
- cognitive substrate
- workspace / delivery side-effect plane
- task runtime foundation

见：

- [/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_chatgptrest_current_state_freeze_for_goal_discussion_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_chatgptrest_current_state_freeze_for_goal_discussion_v1.md)
- [/vol1/1000/projects/ChatgptREST/docs/2026-04-01_ChatgptREST_OpenMind_OpenClaw_边界漂移复盘与平台收口建议_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-04-01_ChatgptREST_OpenMind_OpenClaw_边界漂移复盘与平台收口建议_v1.md)

这意味着你后面讨论目标时，不能再默认“Task Harness = repo 唯一主叙事”。更准确的说法只能是：

> Task Harness Runtime 是这个多平面宿主里最值得继续投资的一条主线候选，但它现在还不是默认 northbound，也还不是默认 completion authority。

## 4. 文档里确实存在 overclaim，必须停止沿用

这轮重读后，我认为最该退役的，不是某个目标，而是几类旧说法：

1. `2026-03-31_agent_harness_completion_report_v1.md` 把 delivery/memory/finalization 写成“已完成阶段”，但后续 blueprint、gap review 和代码都显示这些地方仍带明显 scaffold/placeholder 特征。
2. 任何把 task runtime 写成“已接近 Anthropic harness best-practice”的口径都不成立。
3. 任何把 `opencli / CLI-Anything` 写成当前可并列主线的口径都不成立。

代码 spot-check 也支持这个判断：

- [task_initializer.py](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/task_initializer.py#L143) 的 `_generate_context_snapshot()` 仍是最小快照，不是真实 bootstrap/repo context
- [promotion_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/promotion_service.py#L246) 到 [promotion_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/promotion_service.py#L318) 的 grader 与 artifact refs 仍是 placeholder
- [delivery_integration.py](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/delivery_integration.py#L1) 明写自己还不是 authoritative publication
- [memory_distillation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/memory_distillation.py#L1) 明写自己还没接真实 work-memory manager
- [api_routes.py](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/api_routes.py#L29) 仍是独立 `/v1/tasks` surface，不是现网默认主入口

## 5. 现在真正该保留的目标

### A. 必保留

1. repo 级产品句子 + authority matrix
2. front-door / retirement matrix
3. `Task Harness Runtime` 作为 next-stage mainline candidate
4. skeptical evaluator / authoritative delivery / authoritative memory 这三块承重件
5. 小而硬的 acceptance discipline

### B. 必延后

1. `opencli` 高标准 controlled substrate 升级
2. `CLI-Anything` governed intake
3. 大而全的 eval platform / mega-suite 建设
4. 新一轮 repo 大拆仓或多入口扩张

## 6. 如果从现状稳扎稳打，我建议的讨论顺序

### 第一步：先拍板 3 个冻结句

1. `ChatgptREST / OpenMind / OpenClaw` 各自是什么
2. 当前默认 northbound 是什么
3. 当前默认 completion authority 是什么

### 第二步：只回答一个战略问题

`Task Harness Runtime` 到底是：

- `primary next-stage product track`

还是：

- `important incubating subsystem`

不先做这一步，后面任何 tranche 排期都不稳。

### 第三步：如果决定它进主线，只允许先做 Tranche 1-4

也就是先收：

1. truth model
2. task control plane
3. evaluator gate
4. durable execution

`delivery / memory` 可以紧随其后，但 `opencli / CLI-Anything` 不能同时进入主线推进。

### 第四步：acceptance 先做“小而硬”，不要一次造大平台

与 Anthropic 原文一致，先用少量真实任务和最关键 failure modes 建立 capability/regression 基线，再看是否需要扩成更大的 suite。

## 7. 我给你的当前建议句

如果你要一个能直接带去下一轮目标讨论、同时不自相矛盾的口径，我建议先用这句：

> `ChatgptREST` 是共享 AI 控制平面与运行宿主；下一阶段最值得投资的主线，是在不打乱现有 northbound/completion authority 的前提下，把其中一条真实入口逐步收敛到高可信 `Task Harness Runtime`。`OpenClaw` 保持第一类 shell/runtime integration，`opencli / CLI-Anything` 在本轮只保留为后置验证支线。

## 8. 这份重读后的结论意味着什么

它意味着：

- 你不是“啥都想要”本身错了
- 真正的问题是过去没有先做目标分层和边界冻结
- 所以下一阶段不是继续扩愿景包，而是先做目标降维

如果这个判断作为基线成立，后面的目标讨论就不该再问“还要不要更多能力”，而该问：

1. 哪个目标是 repo 级
2. 哪个目标是 next-stage mainline
3. 哪个目标必须延期
4. 哪个目标在没有 authority freeze 前禁止启动
