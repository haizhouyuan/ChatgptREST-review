# 2026-04-03 Meeting Sedimentation Phase-1 Slice Implementation Spec v1

## 1. 目标

在 `planning` 第一阶段，只实现一条最小但真实可用的任务链：

> `Feishu/OpenClawBot` 发起或继续 `会议沉淀` 任务，并能在深度工作台推进后写回 checkpoint。

这条切片不追求全场景统一，只追求：

1. 有唯一任务线程
2. 有最小 handoff artifact
3. 能跨 `OpenClawBot` 与深度工作台继续

## 2. 本阶段只做什么

只做：

1. `会议录音/转写/会议材料` intake
2. 任务级 `task_id`
3. 最小 `checkpoint`
4. `new / continue` 判定
5. 一次深度执行后的 checkpoint 回写

## 3. 本阶段明确不做什么

暂时不做：

1. 通用多任务大平台
2. full `task_runtime`
3. 自动复杂 branch 策略
4. `Feishu` 全面替代 `Codex / Claude Code / Antigravity`
5. 全自动 `consult / dual-review`

## 4. 最小数据对象

### 4.1 task_id

必须有一个稳定 `task_id`，它表示：

1. 这是哪一个会议沉淀任务
2. 以后从飞书或深度工作台回来，都继续这条线程

### 4.2 checkpoint

最小 checkpoint 只要求这些字段：

1. `task_id`
2. `task_type=meeting_sedimentation`
3. `source_materials`
4. `current_state`
5. `latest_output`
6. `next_step`

## 5. new / continue 规则

第一阶段先用最简单规则：

### 5.1 new

满足任一情况就新开：

1. 明显是另一场会议
2. 主材料集合明显不同
3. 主交付物已经变成另一份独立产出

### 5.2 continue

满足下面条件就继续：

1. 还是同一场会议
2. 还是同一份会议沉淀主交付物
3. 用户是在补充材料、补充要求、追改结果

## 6. 入口与执行分工

### 6.1 OpenClawBot

负责：

1. 接住消息和材料
2. 判断 `new / continue`
3. 找到或分配 `task_id`
4. 展示当前状态
5. 把任务推给深度工作台或继续已有工作

### 6.2 深度工作台

仍然是：

1. `Codex`
2. `Claude Code`
3. `Antigravity`

负责：

1. 读材料
2. 产出会议沉淀结果
3. 回写 checkpoint

## 7. 最小通过标准

这条切片算通过，至少要满足：

1. 同一会议在第二次补材料时不会被错误当成新任务
2. 深度工作台完成一轮后，`OpenClawBot` 能看到可读 checkpoint
3. 用户回来继续时，不需要靠找旧窗口才能恢复上下文

## 8. 第一批代码实现建议

先做最窄版本：

1. 只支持 `meeting_sedimentation`
2. 只支持 `new / continue`
3. checkpoint 先做 sidecar，不引 full `task_runtime`
4. 先写 file-backed 或 sqlite-backed 最小真相层

## 9. 实施后必须验证

### 9.1 功能验证

1. 新会议材料发起
2. 同会议补材料继续
3. 一轮深度执行后可回写 checkpoint
4. 回到 `OpenClawBot` 能查状态并继续

### 9.2 红队验证

实现后必须让 `claudegac` 做严格代码审核，不以顺从为目标，而以找断点为目标。
