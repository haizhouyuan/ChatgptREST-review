# 2026-04-02 Planning Agent Total Plan Execution Master v2

## 1. 这份 v2 相比 v1 改了什么

这一版不是重写方向，而是把 v1 里被红队指出“说得太轻、太像线框图”的地方改成更工程化的版本。

主要改了 6 件事：

1. 不再把 `OpenClawBot -> canonical task plane` 写成“收敛”，改成“建设”
2. 增加 `Step 0`：先做 `OpenClawBot` 材料链 smoke test
3. 不再把 6 字段 checkpoint 说成像成品，而只当 phase-1 baseline
4. 红队 gate 从“每步”改成“每切片 / 每里程碑”
5. `publicagentmcp` 不再写成绝对不增长，而改成“不做大杂烩扩张，但允许 MVP 最小增量”
6. phase-1 MVP 不把 full `task_runtime` 当作前置，优先考虑更轻的 continuity carrier

## 2. 当前总判断

当前最准确的综合口径是：

1. `planning` 第一阶段主线成立
2. `知识层` 以补齐优先
3. `任务层` 仍属于首次生产实现
4. `Feishu` 是重要人类入口，但 owner 是 `OpenClaw/OpenClawBot`
5. `Codex / Claude Code / Antigravity` 仍然是深度工作台
6. `publicagentmcp` 现状很厚，但 phase-1 不再继续机会主义扩张

## 3. phase-1 只做一个最窄生产切片

### 3.1 任务类型

phase-1 第一条生产切片只做：

1. `会议沉淀`

### 3.2 为什么还是选它

1. 它最适合从 `Feishu/OpenClawBot` 发起
2. 它天然依赖材料输入
3. 它最适合跨端 handoff
4. 它最容易人工验收

### 3.3 phase-1 明确不做

1. 8 类 planning 工作全覆盖
2. 多入口全打通
3. 全 policy 系统
4. 完整 evaluator/harness 平台
5. 完整 `task_runtime` 首次生产落地

## 4. 先加一个 Step 0

在任何实施规格之前，必须先做：

> `OpenClawBot` 会议沉淀材料链 smoke test

### 4.1 这个 smoke test 只验证 4 件事

1. `Feishu -> OpenClawBot` 是否能接住会议沉淀消息
2. 音频/转写/文件这类材料能否作为上下文或附件进入 bridge
3. `OpenClawBot -> /v3/agent/turn` 时，`attachments` 实际长什么样
4. 当前链路在哪一跳断开

### 4.2 现在为什么必须先做它

因为从代码上，我已经能证明：

1. `openmind-advisor` 会从 `context.files / context.attachments` 取文件
2. 它会把这些文件放到 `task_intake.attachments` 和 `body.attachments`

但我还不能只靠当前仓里的代码证明：

1. `Feishu` 侧现在是否真的把会议沉淀材料稳定送进 `OpenClawBot` 运行上下文

所以这件事必须先 smoke，而不是靠推测推进。

## 5. phase-1 目标链路改成 baseline，不再叫 freeze

phase-1 的目标链路 baseline 是：

1. `Feishu -> OpenClawBot`
2. `OpenClawBot -> canonical task plane`
3. 分配 `task_id`
4. 在深度工作台推进一轮
5. 写入最小 checkpoint
6. 从 `OpenClawBot` 查状态或继续

这里的关键改动是：

1. 这不是“已冻结成品链路”
2. 这是 phase-1 的 **实施 baseline**

## 6. `task_id` 和 checkpoint 的 phase-1 实现路径

### 6.1 不再把 full `task_runtime` 当 phase-1 前置

目前不把下面这条当 phase-1 前置：

1. `task_runtime` 全接入 `/v3/agent/turn`

原因很明确：

1. `task_runtime_v1` 仍是 `core=False`
2. 生产 caller 为 0
3. 这条线目前更像首次大接线工程

### 6.2 phase-1 允许的更轻实现路径

phase-1 更现实的 continuity path baseline 是：

1. 在 `/v3/agent/turn` 侧引入 `task_id`
2. 如果 caller 没给，就分配一个稳定 `task_id`
3. 把它挂到当前可工作的 session persistence 上
4. 用一个最小 checkpoint sidecar 保存 6 字段 handoff 工件

### 6.3 这不等于把 session store 升格成最终 task truth

必须明确：

1. `AgentSessionStore sidecar` 只是 phase-1 continuity carrier 候选
2. 不等于最终的 task truth layer 就等于 session store
3. 后续是否升到独立 task layer，要等第一条生产切片跑通后再决定

## 7. 6 字段 checkpoint 现在的定义

phase-1 的 6 字段 checkpoint 现在只当 baseline：

1. `task_id`
2. `task_title`
3. `current_objective`
4. `current_status`
5. `current_artifact_refs`
6. `next_actions`

这 6 字段的意义只有一个：

1. 证明跨端 handoff 能成立

不是：

1. 证明最终 checkpoint 设计已经稳定

## 8. `OpenClawBot` 需要补的最小能力

基于当前代码现实，phase-1 至少要补下面这些能力中的一部分：

1. `task_id` 透传或回显
2. 查询当前任务状态的能力
3. 恢复或继续某个任务的能力

当前已经确定不存在的，是：

1. `openmind_advisor_status`
2. `openmind_advisor_resume`
3. `task_id` 参数

所以这不是“桥已经有一半”，而是至少还缺任务连续性的下半条链。

## 9. `publicagentmcp` 在 phase-1 的更准确口径

### 9.1 仍然不做 opportunistic sprawl

phase-1 仍然不允许：

1. 再往 `publicagentmcp` 塞新的大而全策略分支
2. 再把复杂模型选择、附件判断、快慢交付全堆进去

### 9.2 但允许 MVP 最小增量

如果 phase-1 continuity path 需要它承接最小增量，则允许：

1. `task_id` 透传
2. checkpoint 查询所需最小能力
3. 与现有 session persistence 对齐的最小扩展

所以这阶段真正的口径不是：

1. 一点都不能长

而是：

1. 只允许为 MVP 连续性长最小承重件

## 10. 知识层仍然并行补齐

knowledge 线不变，仍然只并行做 3 件事：

1. runtime pack freshness
2. active atom promotion
3. acceptance coverage

这 3 件事仍然是：

1. 补齐
2. 自动化
3. 活化

不是：

1. 重构知识架构

## 11. Red-Team Gate 改成切片级

从这一版起，red-team gate 的正确口径改成：

> 每个切片 / 每个里程碑做一次 `claudegac` 红队审核，而不是每个小步骤都做。

每次红队最少审这 4 个问题：

1. 这一步是不是把 paper design 说成了 running code
2. 这一步是不是偷偷扩大了第一阶段 scope
3. 这一步是不是把复杂度从一个地方平移到了两个地方
4. 这一步是不是绕开了 `OpenClawBot` owner 边界

## 12. phase-1 通过标准

phase-1 第一条切片通过标准仍然只有 5 条：

1. 能从 `OpenClawBot` 发起会议沉淀任务
2. 能落一个稳定 `task_id`
3. 能在深度工作台推进并写回 checkpoint baseline
4. 能再次从 `OpenClawBot` 找回并继续
5. 产出的纪要/行动项对真实工作可直接使用

## 13. 新的 Next 4

### 13.1 Step 0

先做 `OpenClawBot` 会议沉淀材料链 smoke test。

### 13.2 Step 1

基于 smoke test 结果，写第一条切片实施规格。

实施规格最少要覆盖：

1. `task_id` 分配落点
2. checkpoint 写路径
3. checkpoint 读路径
4. `OpenClawBot` 的 status/resume 能力

### 13.3 Step 2

写 6 字段 checkpoint baseline schema。

### 13.4 Step 3

决定 phase-1 continuity carrier 的具体实现：

1. `/v3/agent/turn + AgentSessionStore sidecar`
2. 还是别的更轻路径

但这一步不默认要求 full `task_runtime` 接线。

## 14. 一句话结论

v2 的核心改写是：

> planning 第一阶段继续走 `会议沉淀` 最小生产切片，但不再把它说成“收口后的自然接线”；更准确的做法是，先 smoke `OpenClawBot` 材料链，再用一个更轻的 continuity carrier 跑通 `task_id + checkpoint baseline`，同时并行补知识层自动化。
