# 2026-04-02 Planning Task Layer Policy Pack Walkthrough v1

## 本轮做了什么

在统一逻辑任务层 v1 的基础上，继续冻结了 3 份下游政策文档：

1. [2026-04-02_planning_task_new_continue_branch_policy_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_task_new_continue_branch_policy_v1.md)
2. [2026-04-02_planning_checkpoint_schema_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_checkpoint_schema_v1.md)
3. [2026-04-02_planning_memory_writeback_policy_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_memory_writeback_policy_v1.md)

并新增本 walkthrough。

## 为什么做

上一轮已经把“统一入口”的真正目标纠正成：

- 统一逻辑任务层
- 不统一成唯一界面

但如果只停在抽象层，后面依然会卡在 3 个最实际的问题：

1. 什么时候继续旧任务，什么时候新开
2. checkpoint 到底应该长什么样
3. 哪些内容该进记忆，哪些不该进

所以这轮直接把这 3 件事冻结成独立口径。

## 这轮参考了什么

### 1. 统一逻辑任务层文档

- [2026-04-02_planning_unified_logical_task_layer_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_unified_logical_task_layer_v1.md)

### 2. task runtime 现实

- [task_workspace.py](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/task_workspace.py)
- [memory_distillation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/memory_distillation.py)

### 3. knowledge / memory 边界旧文档

- [2026-03-20_knowledge_authority_decision_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_knowledge_authority_decision_v2.md)

## 这轮具体冻结了什么

### A. `new / continue / branch`

最核心的收口是：

1. 同一目标、同一对象、同一主交付物，默认 `continue`
2. 同源但交付物或作用对象明显分叉，判 `branch`
3. 目标和对象都已经换了，才 `new`

### B. checkpoint schema

最核心的收口是：

1. checkpoint 是 handoff artifact
2. 不是 transcript
3. 不是长期记忆库
4. 必须让另一个 surface 在不翻旧窗口的情况下继续工作

### C. memory writeback

最核心的收口是：

1. `L1` 负责任务可恢复
2. `L2` 负责项目/主题稳定真相
3. `L3` 负责方法与治理改进
4. 未确认、不可回指、低价值内容不得直接升格

## 对后续实现意味着什么

如果后面真要往产品侧做，最自然的实现顺序会是：

1. 入口侧先支持 `new / continue / branch` 判断对象
2. 任务线程里引入 planning-friendly checkpoint 文件或 API 对象
3. 记忆写回不再“任务结束后一锅炖”，而是分层过 gate

## 一句话总结

这轮不是又加了三篇抽象文档，而是把 `planning` 第一阶段最关键的 3 条治理规则定死了：

- 任务怎么分线程
- 线程怎么做 handoff
- handoff 里哪些内容值得升格成记忆
