# 2026-04-02 Planning Memory Writeback Policy v1

## 1. 目的

这份文档冻结的是 `planning/` 第一阶段的记忆写回规则。

它回答的问题是：

> 一次任务结束或推进之后，哪些内容应该写回记忆，写回到哪一层，哪些内容绝对不能直接升格。

## 2. 冻结 mouthpiece

对 `planning/` 第一阶段，记忆写回的默认原则应该是：

> 先保护任务线程的可恢复性，再保护项目 / 主题的稳定真相；未确认、不可回指、不可复核的信息，不得直接升格成长期记忆。

## 3. 和当前代码现实的关系

当前 repo 里已经有一个 task runtime 的 distillation scaffold：

[memory_distillation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/memory_distillation.py#L1)

它当前会构建：

1. `DecisionLedger`
2. `PostCallTriage`
3. `Handoff`
4. `ActiveProjectMap`

但模块头注释已经写明：

- 这还只是 scaffold
- 尚未真正接通 real work-memory manager

所以这份 policy 不是在说“系统今天已经完整实现了写回”，而是在给第一阶段一个 **不会继续写乱的写回规则**。

## 4. 记忆层级 v1

这份 policy 延续统一逻辑任务层里的 4 层：

1. `L0 Session Scratch`
2. `L1 Task Working Memory`
3. `L2 Project / Topic Durable Memory`
4. `L3 Governance / EvoMap Memory`

## 5. 四层各自该写什么

## 5.1 L0 Session Scratch

### 适合放什么

1. 临时试探
2. 未确认猜测
3. 中间推演
4. 草稿式措辞
5. 一次性判断分支

### 规则

1. 默认不写回长期记忆
2. 默认不升格到 L2/L3
3. 可以在会话结束后清空

## 5.2 L1 Task Working Memory

### 适合放什么

1. 当前 objective
2. 当前输出形态
3. 已确认边界
4. 当前结论
5. 未解决问题
6. 当前 next actions
7. 本次任务相关的中短期上下文

### 规则

1. 跟着 `task_id` 走
2. 可跨端恢复
3. 可在任务完成后归档
4. 允许包含尚未最终升格的中间判断，但必须标注状态

## 5.3 L2 Project / Topic Durable Memory

### 适合放什么

1. 项目阶段变化
2. 下一里程碑
3. 风险变化
4. 稳定结论
5. 负责人变化
6. 唯一口径入口
7. 已确认的研究结论入口

### 规则

1. 必须是稳定信息
2. 必须能回指 canonical entry
3. 必须区分“事实 / 判断 / 待确认”
4. 默认只接收经过确认的 writeback

## 5.4 L3 Governance / EvoMap Memory

### 适合放什么

1. 哪类任务经常理解偏
2. 哪类入口最容易找错材料
3. 哪类 checkpoint 字段不够
4. 哪类写回规则经常被误用
5. 哪类任务适合哪个 surface/lane

### 规则

1. 这层服务方法改进
2. 不直接服务当前单个任务
3. 不应混入项目事实

## 6. 写回前必须过的 5 个 gate

## 6.1 确认性 gate

先问：

1. 这是确认后的事实吗
2. 这是明确标注为判断的结论吗
3. 还是只是猜测 / 临时意见

规则：

- 猜测和临时意见不得直接升格到 L2/L3

## 6.2 可回指 gate

先问：

1. 是否有 `planning/` 里的入口或产物可回指
2. 是否能定位到源文件、报告、纪要、台账

规则：

- 不能回指的内容，不得写成 durable memory

## 6.3 敏感性 gate

先问：

1. 这是不是受控资料
2. 这是不是只适合内部使用
3. 这是不是需要脱敏后才能进入更广协作面

规则：

- 敏感内容默认不直接进入公开协作层

## 6.4 范围 gate

先问：

1. 这条信息属于当前 task，还是属于 project/topic
2. 它会不会污染其他任务

规则：

- task 级内容优先留在 L1
- 只有真正稳定、可复用的内容才进 L2

## 6.5 价值 gate

先问：

1. 这条信息以后会被重复用到吗
2. 它值不值得占用长期记忆位

规则：

- 低价值一次性内容不升格

## 7. 写回对象分类 v1

## 7.1 `task_progress_update`

### 去向

- `L1`

### 适用内容

1. 当前已完成步骤
2. 当前结论
3. 当前 next actions

## 7.2 `project_state_update`

### 去向

- `L2`

### 适用内容

1. 项目阶段更新
2. 主要风险变化
3. 下一里程碑变化

### 前提

1. 有证据
2. 已确认

## 7.3 `research_conclusion_update`

### 去向

- `L2`

### 适用内容

1. 研究主结论
2. claim ledger 入口
3. gap note 入口
4. second-check 结论

### 前提

1. 有 report / ledger / note 的明确入口

## 7.4 `meeting_action_update`

### 去向

- `L1` 或 `L2`

### 适用内容

1. 行动项
2. 责任人
3. 待确认事项

### 规则

1. 仅属于当前任务的，进 `L1`
2. 已成为项目稳定行动项的，进 `L2`

## 7.5 `governance_learning`

### 去向

- `L3`

### 适用内容

1. 入口误判教训
2. 写回误判教训
3. surface/lane 最佳实践

## 8. 最小 writeback candidate schema

每个 checkpoint 里的写回候选，至少建议长这样：

```json
{
  "candidate_id": "mwc_001",
  "type": "project_state_update",
  "summary": "当前阶段更接近导入准备期，需先补责任人和时间表",
  "source_refs": [
    "/abs/path/to/meeting_summary.md",
    "/abs/path/to/current_draft.md"
  ],
  "target_scope": "L2",
  "sensitivity": "internal_only",
  "verification_status": "confirmed",
  "writeback_reason": "stable project state change"
}
```

## 9. 第一阶段默认写回规则

## 9.1 默认允许写回到 L1

只要有明确 `task_id`，下面内容一般可写回 `L1`：

1. 当前 objective
2. 当前结论摘要
3. 当前未解决问题
4. 当前 next actions

## 9.2 默认谨慎写回到 L2

只有同时满足下面条件，才建议写回 `L2`：

1. 内容已经确认
2. 有可回指入口
3. 对项目/主题有长期价值
4. 不是一次性中间推演

## 9.3 默认不要直接写回到 L3

只有满足下面条件，才建议写回 `L3`：

1. 这不是单个项目事实
2. 这对后续方法改进有稳定价值
3. 它属于“做事方式”的学习，不属于“项目内容”本身

## 10. 3 类常见误写回

## 10.1 把未确认判断写成项目事实

这是最危险的一类。

例如：

- “我猜客户会在本月下单”

这种内容最多只能停在：

- `L0`
- 或带状态标记后进入 `L1`

不能直接进 `L2`。

## 10.2 把所有会议内容一股脑升格

会议转写里大量内容只是：

1. 口头讨论
2. 临时意见
3. 反复修正中的说法

这些不应整包写入 durable memory。

## 10.3 把任务总结误写成治理经验

并不是每次任务总结都值得进 `L3`。

只有涉及：

1. 入口治理
2. checkpoint 设计
3. 写回规则
4. surface/lane 使用法

这类可复用方法，才值得进 `L3`。

## 11. 一句话结论

`planning` 第一阶段的写回纪律应是：

> L1 负责任务可恢复，L2 负责项目真相，L3 负责方法进化；未确认、不可回指、低价值的内容，不得直接升格。
