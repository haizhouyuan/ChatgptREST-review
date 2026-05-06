# 2026-04-03 OpenClawBot Continue/Retrieve Surface Walkthrough v1

## 1. 为什么现在做这一步

到 `master v6` 为止，phase-1 的 gap 已经只剩一层窗户纸：

1. `meeting_sedimentation` 已经有 `task_id + checkpoint`
2. 但 `OpenClawBot` 还没有一个明确的“继续某个 task / 读回某个 task”面

如果这一步不做，`task_id` 就还是更像内部实现细节，而不是 `Feishu -> OpenClawBot` 可见能力。

## 2. 这一步怎么收窄范围

这次故意没有做下面这些：

1. 不接 full `task_runtime`
2. 不扩 `publicagentmcp`
3. 不做 session/task 总统一大层
4. 不补所有 planning 任务类型

只做：

1. `meeting task retrieve`
2. `openclaw advisor explicit continue`

## 3. 代码层面怎么落

### 3.1 MeetingTaskStore

加了：

1. `get_public(task_id)`

同时把公共投影补到更可读：

1. `status`
2. `objective`
3. `latest_session_id`

### 3.2 agent_v3

加了只读 route：

1. `GET /v3/agent/planning/task/{task_id}`

这一步保持了只读，不碰更大的 controller / run / session 生命周期。

### 3.3 openmind-advisor plugin

加了两块：

1. `openmind_advisor_ask` 的显式 `taskId/taskAction`
2. `openmind_advisor_task_get`

这样 `OpenClawBot` 至少有了：

1. 显式继续
2. 显式取回

而不是只能赌“模型会不会自己把这次输入认成继续旧任务”。

## 4. 为什么不只做 session status

因为这一步要解决的是：

1. `task continue`
2. `task retrieve`

不是：

1. session transport 还活不活

只加 `session status` 会把问题又拉回会话层。当前这一步更需要的是：

1. 按 `task_id` 读 sidecar truth
2. 按 `task_id` 显式继续

## 5. 本轮最大风险点

最大风险不是功能做不出来，而是说重：

1. 容易把这一步说成“统一逻辑任务层已完成”
2. 或者把它说成“full task runtime 已接进 OpenClawBot”

这两句都不对。

更准确的口径是：

1. `meeting_sedimentation` 这条 phase-1 切片现在已经有可见的 continue / retrieve surface
2. 但它仍然是 sidecar truth，不是 final task platform

## 6. 验证策略

本轮验证重点就是 4 条：

1. store 投影可读
2. API retrieve 可用
3. 显式 task_id continue 可用
4. 旧动态 replay gate 不被破坏

## 7. 这一步之后的主计划变化

完成这一步后，`master plan` 的下一项就不再是 “让 OpenClawBot 看见 task_id”，而是：

1. 深度工作台侧显式 checkpoint writeback helper 要不要做
2. 然后才是继续往其它 planning 任务类型推广
