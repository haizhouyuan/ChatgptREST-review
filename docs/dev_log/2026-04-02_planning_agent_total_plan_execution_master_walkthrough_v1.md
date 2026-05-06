# 2026-04-02 Planning Agent Total Plan Execution Master Walkthrough v1

## 1. 这轮为什么要写 master plan

到上一轮为止，仓里已经有：

1. 目标和效果要求
2. surface authority
3. 统一逻辑任务层定义
4. knowledge 主线判断
5. 双审综合裁决
6. 红队原子审核
7. `Feishu -> OpenClawBot` owner 约束

但这些东西还没有压成一个真正可实施的主控稿。

如果不做这一步，后面仍然会反复在：

1. 概念
2. 目标
3. 边界
4. 反对意见

之间来回切换，很难进入实际实施。

## 2. 这版 master plan 解决的核心问题

这版主控稿主要做了 4 个收口：

1. 把“知识层补齐”和“任务层首次实现”彻底拆成两条工作线
2. 把第一阶段任务类型收窄成 `会议沉淀`
3. 把 `Feishu` owner 正式写成 `OpenClaw/OpenClawBot`
4. 把 `publicagentmcp` 暂时降成“边界受控、先不扩张”的状态

## 3. 这版最关键的决定

### 3.1 第一条切片只做会议沉淀

这不是因为其他任务不重要，而是因为：

1. 它最适合从 Feishu 发起
2. 它最适合材料输入
3. 它最适合跨端 handoff
4. 它最容易人工验收

### 3.2 checkpoint 第一版只留 6 字段

这是对红队批评的直接回应。

如果第一条切片还抱着 14 字段 checkpoint 不放，任务层又会继续停留在 paper design。

### 3.3 三份 policy 先降成“后续收敛方向”

这也是为了避免新一轮过度架构化。

这轮不再把：

1. `Lane Policy`
2. `Attachment Preflight`
3. `Fast vs Deep Delivery`

当成必须先建好的独立系统，而只要求第一条切片各落一个最小版本。

## 4. 这轮没有做什么

这轮没有做：

1. 产品代码改动
2. `task_runtime` 接线
3. `OpenClawBot` 桥接实现
4. knowledge 自动化实现

这轮只做了一件事：

1. 把当前分散的冻结口径压成一份可真正进入实施期的主控稿

## 5. 这轮输出

新增：

1. [2026-04-02_planning_agent_total_plan_execution_master_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_agent_total_plan_execution_master_v1.md)
2. [2026-04-02_planning_agent_total_plan_execution_master_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-02_planning_agent_total_plan_execution_master_walkthrough_v1.md)

## 6. 下一步

下一步不是继续补讨论文档，而是：

1. 立刻用 `claudegac` 对这份 master plan 做红队审核
2. 根据红队结果决定是否要改成 `v2`
3. 再进入第一条生产切片实施规格
