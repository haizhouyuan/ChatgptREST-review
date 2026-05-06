# 2026-04-03 Workforce Planning Phase-1 Slice Walkthrough v1

## 1. 为什么这一步现在做

`v8` 的第一个剩余项就是：

1. 把 `meeting_sedimentation` 之外最接近的第二类 planning 任务接入同一 continuity 规则

我没有继续堆第三个特例，而是先挑最接近的：

1. `workforce_planning`

原因：

1. 它已经有 scenario pack
2. 它是 P0 验收场景
3. 它与 phase-1 当前的 `task_id + checkpoint` 目标兼容

## 2. 我怎么做的

### 2.1 不重写平台，只做薄泛化

没有新起一套 task runtime，也没有另建第二套 store。

实际做法是：

1. 保留现有 `meeting_task_store.py`
2. 给它补 `task_type -> spec` 元数据
3. 让 `routes_agent_v3` 先解析 planning task type，再走同一个 sidecar

### 2.2 continuity 规则保持窄

这一步没有引入更激进的自动继续逻辑。

仍然主要靠：

1. 显式 `task_id`
2. 显式 `planning_task_action=continue`
3. 原有的同 identity + 材料重叠

## 3. 我刻意没做的事

1. 没把 `meeting_task_store.py` 大改名
2. 没引入 full `task_runtime`
3. 没让 `publicagentmcp` 长新功能
4. 没发散到第三第四类 planning 任务

## 4. 红队情况

本轮照例发起了 `claudegac` 红队：

1. `ccjob_20260402T183209Z_9b78f074`

但这次仍然被外部资源拦住：

1. `API Error: 402 {"error":"Insufficient credits"}`

所以本轮 red-team 状态应如实写为：

1. 已发起
2. 未拿到有效 verdict
3. 不把它伪装成“已审通过”

## 5. 结果

这一步的结果不是“planning 全做完了”，而是：

1. phase-1 continuity 已从单一会议切片扩到两类 planning task type
2. 下一步终于可以继续做：
   - 更薄的 deep workbench wrapper
   - 第三类 planning 任务
   - 或最终 task runtime 接管方案比较
