# 2026-04-03 Planning Agent Total Plan Execution Master v4

## 1. 这份 v4 相比 v3 改了什么

`v4` 只做一个关键更新：

> `Step 0A / B1 / B2` 已完成，并已由代码与 smoke 证据冻结为 PASS。

因此计划从“先证明入口链是否成立”进入：

> `会议沉淀` phase-1 最小生产切片实施。

## 2. 当前总判断

当前最准确的综合口径是：

1. `planning` 第一阶段主线不变
2. `会议沉淀` 仍然是 phase-1 第一条生产切片
3. `知识层` 仍然并行做补齐
4. `任务层` 仍属于首次生产实现
5. `Feishu` 入口 owner 仍然是 `OpenClaw/OpenClawBot`
6. `Codex / Claude Code / Antigravity` 仍然是深度工作台
7. `Feishu/OpenClawBot -> openmind-advisor -> /v3/agent/turn` 已通过入口链 gate

## 3. Step 0 的状态

### 3.1 已完成

1. `Gate A: transport`
2. `Gate B1: bridge contract`
3. `Gate B2: canonical main path`

### 3.2 当前证据

1. [execution review](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-03_openclawbot_meeting_intake_smoke_execution_review_v1.md)
2. [artifact report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_meeting_intake_smoke_20260403/report_v1.md)
3. [artifact report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_meeting_intake_smoke_20260403/report_v1.json)

## 4. v4 的入口结论

从 `v4` 起，入口相关结论收口成：

1. `Feishu` 继续归 `OpenClawBot`
2. `openmind-advisor` 仍然作为 `OpenClawBot -> ChatgptREST canonical task plane` 的 bridge
3. `publicagentmcp` 仍按 `ask wrapper` 收口，不回头长成大总控
4. 第一阶段不追求 `Feishu = Codex/CC/Antigravity`
5. 第一阶段追求的是：
   - `Feishu/OpenClawBot` 能稳定接住任务与材料
   - 深度执行仍交给 `Codex / Claude Code / Antigravity`
   - 两端通过最小 `task_id + checkpoint` 连起来

## 5. v4 的第一条实施切片

phase-1 第一条生产切片继续只做：

1. `会议沉淀`

它的最小目标链是：

1. 从 `Feishu/OpenClawBot` 发起或继续会议沉淀任务
2. 由 bridge 进入 canonical task plane
3. 为任务分配稳定 `task_id`
4. 在深度工作台推进
5. 写回最小 checkpoint
6. 再从 `OpenClawBot` 查状态或继续

## 6. v4 的 Next 4

### 6.1 Step 1

写 `会议沉淀` phase-1 最小生产切片实施规格。

### 6.2 Step 2

实现最小 `task_id + checkpoint sidecar`，先不引 full `task_runtime`。

### 6.3 Step 3

把 `Feishu/OpenClawBot -> continue existing meeting task` 做成第一条真实 continuity 证明链。

### 6.4 Step 4

在代码实现后跑 `claudegac` 严格红队审核。

## 7. 一句话结论

`v4` 的核心改写是：

> 入口链验证阶段已经完成，planning 第一阶段现在正式进入 `会议沉淀` 最小生产切片实施阶段。
