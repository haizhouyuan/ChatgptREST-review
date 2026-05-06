# 2026-04-03 Planning Agent Total Plan Execution Master v13

## 1. v13 相比 v12 的关键变化

`v13` 的核心变化是：

1. phase-1 continuity sidecar 已从 3 类 slice 扩成一个更完整的 `planning task plane`
2. acceptance pack 也同步从 3 个 scenario 扩到 7 个 scenario
3. task plane 现在不仅有 `retrieve + explicit continue`，也有：
   - `identity continue`
   - `branch`
   - `list/query`
   - richer checkpoint writeback

## 2. 到 v13 为止的总判断

当前更准确的口径是：

1. `planning` 第一阶段主线不变
2. `知识层` 继续并行补齐
3. `任务层` 在 ChatgptREST 内部已经不再只是三条 continuity slice，而是一个更完整的 phase-1 planning task plane
4. 这个 task plane 当前覆盖 7 类 planning 任务：
   - `meeting_sedimentation`
   - `workforce_planning`
   - `implementation_plan`
   - `project_diagnosis`
   - `research_decision`
   - `leadership_report`
   - `planning_general`
5. 这仍不是 full `task_runtime`

## 3. 已完成阶段

### 3.1 Step 0

已完成：

1. `transport`
2. `bridge contract`
3. `canonical main path`

### 3.2 Step 1

已完成：

1. `meeting_sedimentation` continuity slice
2. `workforce_planning` continuity slice
3. `implementation_plan` continuity slice
4. failure hardening
5. `OpenClawBot` 显式 `continue / retrieve`
6. 深度工作台显式 checkpoint writeback helper
7. 深度工作台完成态薄 wrapper
8. phase-1 continuity acceptance pack

### 3.3 Step 1.5

本轮新增并完成：

1. `project_diagnosis` task type
2. `research_decision` task type
3. `leadership_report` task type
4. `planning_general` task type
5. identity-based continue
6. `branch`
7. `/v3/agent/planning/tasks`
8. richer checkpoint schema / richer writeback validation
9. planning task plane acceptance pack（7 scenario）

## 4. v13 的当前能力

现在应准确写成：

1. 7 类 planning 任务已有 `task_id + retrieve + identity continue + explicit continue + writeback`
2. `branch` 可把同一 planning thread 分成不同下游任务
3. `list/query` 已可用于同 identity 下的任务管理
4. richer checkpoint schema 已可承载：
   - `task_title`
   - `project_or_topic_ref`
   - `current_output_target`
   - `decision_summary`
   - `confirmed_scope`
   - `open_questions`
   - `next_actions`
   - `memory_writeback_candidates`
5. 这些能力已有统一 acceptance pack，而不是只靠零散单测证明

## 5. 当前仍未完成

当前仍未完成：

1. `Feishu/OpenClawBot` 主链真实 acceptance
2. full `task_runtime` integration
3. `planning` knowledge freshness / promotion / writeback 闭环全补齐
4. Claude strict sign-off 最终 verdict

## 6. Claude 红队状态

到 `v13` 为止，正确动作应是：

1. 用本轮已提交版本做一次严格 Claude red-team
2. 让它审：
   - task store 扩面
   - route 接线
   - acceptance pack
   - 本地 evidence bundle
3. 再决定下一轮是否修 bug 或继续扩面

## 7. v13 的 Next 3

### 7.1 Next 1

对 `v13` 已提交版本做一次严格 `claudegac` 红队审查。

### 7.2 Next 2

若红队指出真实缺陷，则优先修真实缺陷，而不是继续盲目扩大 task type 数量。

### 7.3 Next 3

在 red-team 收敛后，把 acceptance 继续往更贴近 `OpenClawBot` 主链的证据推进。

## 8. 一句话结论

`v13` 的核心变化是：

> ChatgptREST 内部的 phase-1 continuity 现在已经扩成一个更完整的 planning task plane；它仍不是 full task runtime，但已明显超出“三条最小 slice”的范围。
