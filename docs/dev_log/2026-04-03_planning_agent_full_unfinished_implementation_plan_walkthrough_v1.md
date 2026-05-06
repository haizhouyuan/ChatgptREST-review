# 2026-04-03 Planning Agent 未完成部分全量实施计划 Walkthrough v1

## 本次做了什么

新增一份全量实施计划：

- `docs/reviews/2026-04-03_planning_agent_full_unfinished_implementation_plan_v1.md`

## 为什么要做这份计划

到 `v19` 为止，已有 master plan 更像“当前状态 + next 3”。

但用户这轮要求的是：

1. 把整个未完成部分一次梳理出来
2. 讲清楚哪些已经完成、哪些没有完成
3. 给出完整步骤、效果目标、验收标准与 red-team gate
4. 后续按这份计划继续做代码与测试，而不是继续边聊边散开

所以这次没有重复写大而化之的蓝图，而是把未完成工作按：

1. `OpenClawBot 主链`
2. `统一任务线程`
3. `policy layer`
4. `planning 知识主线`
5. `P0 场景验收`
6. `边界裁剪与技术债`

六个工作包重新排列。

## 这份计划相对于现有 master plan 的新增价值

### 1. 明确了“第一阶段完成”到底是什么意思

不是“看起来系统更完整了”，而是：

- `OpenClawBot` 主链 live green
- 统一任务线程最小闭环成立
- 至少 3 类高频任务可跨端 continue
- 知识主线在真实任务里起作用
- 至少 1 套 policy 进入真实执行

### 2. 把任务层和知识层拆开排

之前容易混成一条线，现在明确成：

- 任务层先打通 live 主链和 task truth
- 知识层补 freshness / promotion / writeback / acceptance

### 3. 把后续顺序冻结成 Phase A-E

- Phase A：先拿下 live 主链
- Phase B：再把 task truth 收口
- Phase C：再把 policy 变成真实执行
- Phase D：再补知识闭环
- Phase E：最后做 P0 验收与边界裁剪

### 4. 收紧了 red-team 的使用方式

不再要求“每个微小改动都跑一次”，改成：

1. 每阶段至少一次
2. 每个高风险边界变更一次
3. live gate 修复后一次

## 当前下一步

按计划，下一步不再扩文档和 task type，直接进入：

1. `W1-S1`
2. 针对 `OpenClaw dynamic replay harness fetch failed` 做定向排障
3. 产出最小复现、修复点、回归与 live evidence
